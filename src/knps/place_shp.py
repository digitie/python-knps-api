"""대피소 ZIP의 실제 Point 레이어만 읽는다. 파일을 디스크에 추출하지 않는다."""

from __future__ import annotations

import codecs
import hashlib
import io
import json
import math
import struct
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from .artifacts import _decode_zip_member_name
from .exceptions import KnpsParseError
from .geometry import _build_transform, _crs_from_prj, _import_pyshp, _stringify
from .models import FileDataset, KnpsPlaceRecord
from .records import normalize_place_record

# 중첩 ZIP 자체와 그 내용은 각각 누적 계산한다.
_MAX_DEPTH = 3
_MAX_MEMBERS = 10_000
_MAX_MEMBER_BYTES = 256 * 1024 * 1024
_MAX_TOTAL_BYTES = 512 * 1024 * 1024


def _error(dataset: FileDataset, message: str) -> KnpsParseError:
    return KnpsParseError(
        message, provider=dataset.provider, endpoint=dataset.key, failure_kind="geometry"
    )


@dataclass
class _Budget:
    members: int = 0
    unpacked: int = 0

    def include(self, dataset: FileDataset, infos: list[zipfile.ZipInfo]) -> None:
        self.members += len(infos)
        self.unpacked += sum(info.file_size for info in infos)
        if self.members > _MAX_MEMBERS or self.unpacked > _MAX_TOTAL_BYTES:
            raise _error(dataset, "shelter archive exceeds cumulative member/byte limit")
        if any(info.file_size > _MAX_MEMBER_BYTES for info in infos):
            raise _error(dataset, "shelter archive member exceeds byte limit")


def _member_name(dataset: FileDataset, info: zipfile.ZipInfo) -> str:
    name = unicodedata.normalize("NFC", _decode_zip_member_name(info).replace("\\", "/"))
    parts = name.split("/")
    if (
        not name
        or name.startswith("/")
        or any(part in ("", ".", "..") for part in parts)
        or ":" in parts[0]
        or "!/" in name
    ):
        raise _error(dataset, "unsafe or ambiguous shelter archive member path")
    return str(PurePosixPath(name))


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    # 크기 제한은 호출 전 전체 directory에 적용한다. 실제 바이트도 다시 확인한다.
    with archive.open(info) as stream:
        data = stream.read(info.file_size + 1)
    if len(data) != info.file_size:
        raise ValueError("archive member size mismatch")
    return data


def read_shelter_shp(
    dataset: FileDataset, data: bytes, *, source_crs: str | None = None
) -> tuple[KnpsPlaceRecord, ...] | None:
    """SHP가 없으면 None(CSV 기존 경로), 있으면 모든 중첩 Point를 반환한다.

    Point/PointZ/PointM의 XY만 허용하고 polygon 대표점을 만들지 않는다.
    CRS가 없거나 해석 불가하면 원본 수치를 경위도로 포장하지 않고 전체를 거부한다.
    """
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return None
    budget = _Budget()
    records: list[KnpsPlaceRecord] = []
    identities: set[str] = set()
    found_shp = False

    def visit(payload: bytes, parents: tuple[str, ...], depth: int) -> None:
        nonlocal found_shp
        if depth > _MAX_DEPTH:
            raise _error(dataset, "shelter archive exceeds nested ZIP depth limit")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            budget.include(dataset, infos)
            names: dict[str, zipfile.ZipInfo] = {}
            for info in infos:
                if info.is_dir():
                    continue
                name = _member_name(dataset, info)
                if name.casefold() in names:
                    raise _error(dataset, "duplicate shelter archive member name")
                names[name.casefold()] = info
            for folded in sorted(names):
                info = names[folded]
                name = _member_name(dataset, info)
                if folded.endswith(".zip"):
                    visit(_read_member(archive, info), (*parents, name), depth + 1)
                elif folded.endswith(".shp"):
                    found_shp = True
                    layer = _read_layer(
                        dataset, archive, names, name, parents, source_crs=source_crs
                    )
                    for record in layer:
                        if record.source_id in identities:
                            raise _error(dataset, "duplicate shelter Point identity")
                        identities.add(record.source_id)
                        records.append(record)

    try:
        visit(data, (), 0)
    except KnpsParseError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, EOFError, struct.error) as exc:
        raise _error(dataset, "invalid shelter SHP/ZIP data") from exc
    if not found_shp:
        return None
    if not records:
        raise _error(dataset, "no usable Point shelter records in SHP archive")
    return tuple(records)


def _read_layer(
    dataset: FileDataset,
    archive: zipfile.ZipFile,
    names: dict[str, zipfile.ZipInfo],
    name: str,
    parents: tuple[str, ...],
    *,
    source_crs: str | None,
) -> list[KnpsPlaceRecord]:
    shapefile = _import_pyshp(dataset)
    shp = _read_member(archive, names[name.casefold()])
    try:
        # 부지 Polygon에는 DBF/CRS가 없어도 된다. Point에만 아래 계약을 요구한다.
        with shapefile.Reader(shp=io.BytesIO(shp)) as header:
            if header.shapeType not in (shapefile.POINT, shapefile.POINTZ, shapefile.POINTM):
                return []

        stem = name[:-4]

        def sibling(suffix: str) -> bytes | None:
            info = names.get((stem + suffix).casefold())
            return None if info is None else _read_member(archive, info)

        dbf = sibling(".dbf")
        if dbf is None:
            raise _error(dataset, "Point shelter layer requires a DBF sidecar")
        resolved = source_crs or _crs_from_prj(sibling(".prj"))
        if resolved is None:
            raise _error(dataset, "Point shelter layer requires valid PRJ or source_crs")
        transform = _build_transform(dataset, resolved, "EPSG:4326")
        cpg = sibling(".cpg")
        encoding = "cp949"
        if cpg is not None:
            label = cpg.decode("utf-8-sig").strip()
            encoding = {"65001": "utf-8", "949": "cp949", "1252": "cp1252"}.get(label, label)
            codecs.lookup(encoding)
        shx = sibling(".shx")
        with shapefile.Reader(
            shp=io.BytesIO(shp),
            dbf=io.BytesIO(dbf),
            shx=None if shx is None else io.BytesIO(shx),
            encoding=encoding,
            encodingErrors="strict",
        ) as reader:
            fields = [field[0] for field in reader.fields[1:]]
            if len({field.casefold() for field in fields}) != len(fields):
                raise _error(dataset, "duplicate shelter DBF field names")
            records: list[KnpsPlaceRecord] = []
            shape_count = 0
            for index, shape in enumerate(reader.iterShapes()):
                shape_count += 1
                if index >= reader.numRecords:
                    raise _error(dataset, "shelter SHP/DBF record count mismatch")
                values = reader.record(index)
                # dBASE 삭제 행은 같은 행 번호의 Point와 함께 제외한다.
                if values is None:
                    continue
                if shape.shapeType == shapefile.NULL:
                    raise _error(dataset, "null geometry in Point shelter layer")
                if shape.shapeType not in (shapefile.POINT, shapefile.POINTZ, shapefile.POINTM):
                    raise _error(dataset, "non-Point geometry in Point shelter layer")
                x, y = float(shape.points[0][0]), float(shape.points[0][1])
                if transform is not None:
                    x, y = transform(x, y)
                if not (
                    math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90
                ):
                    raise _error(dataset, "invalid WGS84 shelter Point")
                raw = dict(zip(fields, (_stringify(value) for value in values), strict=True))
                # DBF 영문 코드 해석만 명시적으로 활성화한다. 원본 key는 보존한다.
                record = normalize_place_record(dataset.key, raw, bare_codes=True)
                identity: list[object] = [*parents, name, record.source_id]
                if record.source_id.startswith("row:"):
                    identity.extend([x, y])
                digest = hashlib.sha256(
                    json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()
                ).hexdigest()
                source_member = "!/".join((*parents, name))
                # DBF 원본 필드는 유지하고 geometry-only 변경도 소비자의 raw hash에 반영한다.
                provenance = {
                    "__knps_point_wgs84__": json.dumps([x, y], separators=(",", ":")),
                    "__knps_source_member__": source_member,
                    "__knps_source_crs__": resolved,
                }
                if raw.keys() & provenance.keys():
                    raise _error(dataset, "reserved shelter provenance field collision")
                raw.update(provenance)
                records.append(
                    record.model_copy(
                        update={
                            "source_id": f"shp:{digest}",
                            "source_member": source_member,
                            "longitude": x,
                            "latitude": y,
                            "raw": raw,
                        }
                    )
                )
            if shape_count != reader.numRecords:
                raise _error(dataset, "shelter SHP/DBF record count mismatch")
            return records
    except KnpsParseError:
        raise
    except (
        shapefile.ShapefileException,
        ValueError,
        LookupError,
        OSError,
        EOFError,
        struct.error,
        IndexError,
    ) as exc:
        raise _error(dataset, "invalid Point shelter layer or encoding/CRS") from exc
