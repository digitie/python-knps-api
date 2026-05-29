"""다운로드 파일 bytes에서 geometry feature를 추출하는 helper.

SHP 파싱(``pyshp``)과 좌표 재투영(``pyproj``)은 선택 의존성(``geo`` extra)이다.
설치되지 않은 경로를 타면 설치 방법을 안내하는 :class:`KnpsParseError`를 던진다.
WKT/위경도 컬럼만 쓰는 CSV 추출은 재투영이 필요 없으면 선택 의존성 없이도 동작한다.
"""

from __future__ import annotations

import csv
import io
import os
import re
import tempfile
import zipfile
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .artifacts import _clean_header, _decode_text, _decode_zip_member_name
from .exceptions import KnpsParseError
from .models import (
    FileDataset,
    GeoFeature,
    GeoFeatureCollection,
    Geometry,
    GeometryType,
)

if TYPE_CHECKING:
    import geopandas

WGS84 = "EPSG:4326"

# CSV에서 geometry를 담는 컬럼 후보. lowercase/strip 후 비교한다.
_WKT_HEADERS = ("wkt", "geom", "geometry", "the_geom", "shape", "geom_wkt", "wkt_geom")
_LON_HEADERS = ("lon", "lng", "long", "longitude", "x", "경도", "tm_x", "gis_x", "x좌표")
_LAT_HEADERS = ("lat", "latitude", "y", "위도", "tm_y", "gis_y", "y좌표")

_SHP_SUFFIX = ".shp"
_CSV_SUFFIXES = (".csv", ".txt")


def extract_geometries(
    dataset: FileDataset,
    data: bytes,
    *,
    source_crs: str | None = None,
    target_crs: str | None = WGS84,
    max_features: int | None = None,
) -> GeoFeatureCollection:
    """다운로드 파일에서 geometry feature를 추출한다.

    - ZIP 안에 shapefile(``.shp``)이 있으면 ``pyshp``로 읽고 ``.prj``에서
      원본 좌표계를 감지한다.
    - 그 외에는 CSV의 WKT 컬럼 또는 위경도 컬럼에서 geometry를 만든다.

    ``source_crs``가 명시되거나 ``.prj``에서 감지되고, ``target_crs``와 다르면
    ``pyproj``로 좌표를 재투영한다. 좌표계를 알 수 없으면 원본 좌표를 그대로 둔다.
    """

    if zipfile.is_zipfile(io.BytesIO(data)):
        return _extract_from_zip(
            dataset,
            data,
            source_crs=source_crs,
            target_crs=target_crs,
            max_features=max_features,
        )
    return _extract_from_csv_bytes(
        dataset,
        None,
        data,
        source_crs=source_crs,
        target_crs=target_crs,
        max_features=max_features,
    )


def read_shapefile_geodataframe(
    dataset: FileDataset,
    data: bytes,
    *,
    source_crs: str | None = None,
    target_crs: str | None = None,
    encoding: str | None = "cp949",
) -> geopandas.GeoDataFrame:
    """ZIP shapefile 번들을 ``geopandas.GeoDataFrame``으로 로드해 돌려준다.

    ``geopandas``는 선택 의존성(``geo`` extra)이다. 설치되지 않으면 설치
    방법을 안내하는 :class:`KnpsParseError`를 던진다.

    - ``data``는 shapefile 구성요소(``.shp``/``.dbf``/``.shx``/``.prj`` 등)를
      담은 ZIP bytes여야 한다.
    - 한글 속성은 기본 ``encoding="cp949"``로 디코드한다. ``.cpg``/UTF-8
      shapefile이면 ``encoding=None``으로 GDAL 기본값에 맡길 수 있다.
    - ``source_crs``를 주면 (``.prj`` 유무와 무관하게) 좌표계를 그 값으로
      덮어쓴다. ``target_crs``를 주면 그 좌표계로 재투영한다. 원본 좌표계를
      알 수 없는데 ``target_crs``만 주면 :class:`KnpsParseError`를 던진다.
    """

    gpd = _import_geopandas(dataset)

    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise KnpsParseError(
            f"geopandas shapefile loading expects a ZIP shapefile bundle for "
            f"dataset {dataset.key}",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="geometry",
        )

    read_kwargs: dict[str, object] = {}
    if encoding is not None:
        read_kwargs["encoding"] = encoding

    with (
        zipfile.ZipFile(io.BytesIO(data)) as archive,
        tempfile.TemporaryDirectory() as work_dir,
    ):
        shp_path: str | None = None
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = os.path.basename(_decode_zip_member_name(info))
            if not basename:
                continue
            member_path = os.path.join(work_dir, basename)
            with open(member_path, "wb") as handle:
                handle.write(archive.read(info))
            if shp_path is None and basename.lower().endswith(_SHP_SUFFIX):
                shp_path = member_path

        if shp_path is None:
            raise KnpsParseError(
                f"no shapefile (.shp) member found in ZIP for dataset {dataset.key}",
                provider=dataset.provider,
                endpoint=dataset.key,
                failure_kind="geometry",
            )

        geodataframe = gpd.read_file(shp_path, **read_kwargs)

    if source_crs is not None:
        geodataframe = geodataframe.set_crs(source_crs, allow_override=True)

    if target_crs is not None:
        if geodataframe.crs is None:
            raise KnpsParseError(
                f"cannot reproject dataset {dataset.key} to {target_crs}: source CRS is "
                "unknown (no .prj in ZIP); pass source_crs to declare it",
                provider=dataset.provider,
                endpoint=dataset.key,
                failure_kind="geometry",
            )
        geodataframe = geodataframe.to_crs(target_crs)

    return geodataframe


def _extract_from_zip(
    dataset: FileDataset,
    data: bytes,
    *,
    source_crs: str | None,
    target_crs: str | None,
    max_features: int | None,
) -> GeoFeatureCollection:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = {
            _decode_zip_member_name(info): info
            for info in archive.infolist()
            if not info.is_dir()
        }
        shp_name = next(
            (name for name in names if name.lower().endswith(_SHP_SUFFIX)),
            None,
        )
        if shp_name is not None:
            return _extract_from_shapefile(
                dataset,
                archive,
                names,
                shp_name,
                source_crs=source_crs,
                target_crs=target_crs,
                max_features=max_features,
            )

        csv_name = next(
            (name for name in names if name.lower().endswith(_CSV_SUFFIXES)),
            None,
        )
        if csv_name is not None:
            return _extract_from_csv_bytes(
                dataset,
                csv_name,
                archive.read(names[csv_name]),
                source_crs=source_crs,
                target_crs=target_crs,
                max_features=max_features,
            )

    raise KnpsParseError(
        f"no shapefile or CSV geometry source found in ZIP for dataset {dataset.key}",
        provider=dataset.provider,
        endpoint=dataset.key,
        failure_kind="geometry",
    )


# ---------------------------------------------------------------------------
# Shapefile (pyshp)
# ---------------------------------------------------------------------------


def _extract_from_shapefile(
    dataset: FileDataset,
    archive: zipfile.ZipFile,
    names: dict[str, zipfile.ZipInfo],
    shp_name: str,
    *,
    source_crs: str | None,
    target_crs: str | None,
    max_features: int | None,
) -> GeoFeatureCollection:
    shapefile = _import_pyshp(dataset)

    stem = shp_name[: -len(_SHP_SUFFIX)]

    def _sibling(suffix: str) -> io.BytesIO | None:
        for candidate in (stem + suffix, stem + suffix.upper()):
            info = names.get(candidate)
            if info is not None:
                return io.BytesIO(archive.read(info))
        return None

    prj_bytes = None
    prj_io = _sibling(".prj")
    if prj_io is not None:
        prj_bytes = prj_io.getvalue()

    resolved_source = source_crs or _crs_from_prj(prj_bytes)

    reader_kwargs: dict[str, object] = {
        "shp": io.BytesIO(archive.read(names[shp_name])),
        "encoding": "cp949",
        "encodingErrors": "replace",
    }
    dbf_io = _sibling(".dbf")
    if dbf_io is not None:
        reader_kwargs["dbf"] = dbf_io
    shx_io = _sibling(".shx")
    if shx_io is not None:
        reader_kwargs["shx"] = shx_io

    transform = _build_transform(dataset, resolved_source, target_crs)
    crs = resolved_source if transform is None else target_crs

    features: list[GeoFeature] = []
    geometry_type: str | None = None
    with shapefile.Reader(**reader_kwargs) as reader:
        field_names = [field[0] for field in reader.fields[1:]]  # [0]은 DeletionFlag
        for index, shape_record in enumerate(reader.iterShapeRecords()):
            if max_features is not None and index >= max_features:
                break
            geometry = _geometry_from_geo_interface(shape_record.shape.__geo_interface__)
            if geometry is not None:
                if transform is not None:
                    geometry = _reproject_geometry(geometry, transform)
                if geometry_type is None:
                    geometry_type = geometry.type
            properties = tuple(
                (name, _stringify(value))
                for name, value in zip(field_names, shape_record.record, strict=False)
            )
            features.append(GeoFeature(geometry=geometry, properties=properties))

    return GeoFeatureCollection(
        dataset_key=dataset.key,
        data_go_id=dataset.data_go_id,
        member_name=shp_name,
        geometry_type=geometry_type or dataset.geometry_type,
        source_crs=resolved_source,
        crs=crs,
        features=tuple(features),
    )


def _geometry_from_geo_interface(geo: object) -> Geometry | None:
    if not isinstance(geo, dict):
        return None
    geo_type = geo.get("type")
    coordinates = geo.get("coordinates")
    if geo_type not in _GEOMETRY_TYPES or coordinates is None:
        return None
    return Geometry(type=geo_type, coordinates=_to_tuples(coordinates))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CSV (WKT / 위경도 컬럼)
# ---------------------------------------------------------------------------


def _extract_from_csv_bytes(
    dataset: FileDataset,
    member_name: str | None,
    data: bytes,
    *,
    source_crs: str | None,
    target_crs: str | None,
    max_features: int | None,
) -> GeoFeatureCollection:
    decoded = _decode_text(data)
    if decoded is None:
        raise KnpsParseError(
            f"could not decode CSV geometry source for dataset {dataset.key}",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="geometry",
        )
    text, _encoding = decoded
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise KnpsParseError(
            f"empty CSV geometry source for dataset {dataset.key}",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="geometry",
        )

    headers = [_clean_header(value, index) for index, value in enumerate(rows[0])]
    lowered = [header.strip().lower() for header in headers]
    wkt_index = _first_index(lowered, _WKT_HEADERS)
    lon_index = _first_index(lowered, _LON_HEADERS)
    lat_index = _first_index(lowered, _LAT_HEADERS)

    if wkt_index is None and (lon_index is None or lat_index is None):
        raise KnpsParseError(
            f"no WKT or lon/lat columns found in CSV for dataset {dataset.key} "
            f"(headers={headers})",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="geometry",
        )

    transform = _build_transform(dataset, source_crs, target_crs)
    crs = source_crs if transform is None else target_crs

    features: list[GeoFeature] = []
    geometry_type: str | None = None
    for raw_row in rows[1:]:
        if max_features is not None and len(features) >= max_features:
            break
        geometry = _csv_row_geometry(raw_row, wkt_index, lon_index, lat_index)
        if geometry is not None:
            if transform is not None:
                geometry = _reproject_geometry(geometry, transform)
            if geometry_type is None:
                geometry_type = geometry.type
        properties = tuple(
            (header, _stringify(raw_row[index]) if index < len(raw_row) else None)
            for index, header in enumerate(headers)
        )
        features.append(GeoFeature(geometry=geometry, properties=properties))

    return GeoFeatureCollection(
        dataset_key=dataset.key,
        data_go_id=dataset.data_go_id,
        member_name=member_name,
        geometry_type=geometry_type or dataset.geometry_type,
        source_crs=source_crs,
        crs=crs,
        features=tuple(features),
    )


def _csv_row_geometry(
    row: list[str],
    wkt_index: int | None,
    lon_index: int | None,
    lat_index: int | None,
) -> Geometry | None:
    if wkt_index is not None and wkt_index < len(row):
        value = row[wkt_index].strip()
        if value:
            return parse_wkt(value)
    if lon_index is not None and lat_index is not None:
        if lon_index < len(row) and lat_index < len(row):
            lon = _maybe_float(row[lon_index])
            lat = _maybe_float(row[lat_index])
            if lon is not None and lat is not None:
                return Geometry(type="Point", coordinates=(lon, lat))
    return None


# ---------------------------------------------------------------------------
# WKT 파서 (순수 Python)
# ---------------------------------------------------------------------------

_WKT_KEYWORDS: dict[str, GeometryType] = {
    "POINT": "Point",
    "MULTIPOINT": "MultiPoint",
    "LINESTRING": "LineString",
    "MULTILINESTRING": "MultiLineString",
    "POLYGON": "Polygon",
    "MULTIPOLYGON": "MultiPolygon",
}
_WKT_HEAD = re.compile(r"^\s*([A-Za-z]+)\s*(?:ZM?|M)?\s*(\(.*\)|EMPTY)\s*$", re.DOTALL)


def parse_wkt(text: str) -> Geometry | None:
    """WKT 문자열을 :class:`Geometry`로 파싱한다. 인식 못하면 ``None``."""

    match = _WKT_HEAD.match(text)
    if match is None:
        return None
    keyword = match.group(1).upper()
    geometry_type = _WKT_KEYWORDS.get(keyword)
    if geometry_type is None:
        return None
    body = match.group(2)
    if body == "EMPTY":
        return None

    node = _parse_group(body)
    if geometry_type == "Point":
        position = _first_position(node)
        if position is None:
            return None
        return Geometry(type="Point", coordinates=position)
    if geometry_type in ("MultiPoint", "LineString"):
        positions = tuple(_flatten_positions(node))
        if not positions:
            return None
        return Geometry(type=geometry_type, coordinates=positions)
    return Geometry(type=geometry_type, coordinates=node)  # type: ignore[arg-type]


def _parse_group(text: str) -> object:
    """괄호 구조를 중첩 tuple로 파싱한다. 잎(leaf)은 위치 tuple이다."""

    stripped = text.strip()
    if stripped.startswith("("):
        inner = stripped[1:-1]
        parts = _split_top_level(inner)
        if any("(" in part for part in parts):
            return tuple(_parse_group(part) for part in parts)
        positions = [_parse_position(part) for part in parts]
        return tuple(position for position in positions if position is not None)
    return _parse_position(stripped)


def _split_top_level(text: str) -> list[str]:
    """괄호 깊이 0의 콤마를 기준으로 분리한다."""

    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def _parse_position(token: str) -> tuple[float, ...] | None:
    numbers = token.split()
    if len(numbers) < 2:
        return None
    try:
        return (float(numbers[0]), float(numbers[1]))
    except ValueError:
        return None


def _flatten_positions(node: object) -> list[tuple[float, ...]]:
    if _is_position(node):
        return [node]  # type: ignore[list-item]
    if isinstance(node, tuple):
        result: list[tuple[float, ...]] = []
        for child in node:
            result.extend(_flatten_positions(child))
        return result
    return []


def _first_position(node: object) -> tuple[float, ...] | None:
    positions = _flatten_positions(node)
    return positions[0] if positions else None


def _is_position(node: object) -> bool:
    return (
        isinstance(node, tuple)
        and bool(node)
        and all(isinstance(item, (int, float)) for item in node)
    )


# ---------------------------------------------------------------------------
# CRS / 재투영 (pyproj)
# ---------------------------------------------------------------------------


def _build_transform(
    dataset: FileDataset,
    source_crs: str | None,
    target_crs: str | None,
) -> Callable[[float, float], tuple[float, float]] | None:
    if source_crs is None or target_crs is None or source_crs == target_crs:
        return None
    pyproj = _import_pyproj(dataset)
    transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

    def _transform(x: float, y: float) -> tuple[float, float]:
        new_x, new_y = transformer.transform(x, y)
        return (float(new_x), float(new_y))

    return _transform


def _reproject_geometry(
    geometry: Geometry,
    transform: Callable[[float, float], tuple[float, float]],
) -> Geometry:
    coordinates = _transform_coordinates(geometry.coordinates, transform)
    return Geometry(type=geometry.type, coordinates=coordinates)  # type: ignore[arg-type]


def _transform_coordinates(
    node: object,
    transform: Callable[[float, float], tuple[float, float]],
) -> object:
    if _is_position(node):
        position: tuple[float, ...] = node  # type: ignore[assignment]
        return transform(position[0], position[1])
    if isinstance(node, tuple):
        return tuple(_transform_coordinates(child, transform) for child in node)
    return node


def _crs_from_prj(prj_bytes: bytes | None) -> str | None:
    if not prj_bytes:
        return None
    try:
        from pyproj import CRS
    except ModuleNotFoundError:
        return None
    text = prj_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        crs = CRS.from_wkt(text)
    except Exception:
        return None
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg is not None else text


# ---------------------------------------------------------------------------
# 공통 helper
# ---------------------------------------------------------------------------

_GEOMETRY_TYPES = frozenset(_WKT_KEYWORDS.values())


def _to_tuples(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return tuple(_to_tuples(item) for item in value)
    return value


def _first_index(lowered: list[str], candidates: tuple[str, ...]) -> int | None:
    for candidate in candidates:
        if candidate in lowered:
            return lowered.index(candidate)
    return None


def _maybe_float(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _stringify(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("cp949", errors="replace")
    return str(value)


def _import_pyshp(dataset: FileDataset) -> Any:
    try:
        import shapefile  # type: ignore[import-untyped]
    except ModuleNotFoundError as error:
        raise KnpsParseError(
            "shapefile parsing requires the optional 'geo' extra "
            "(pip install python-knps-api[geo])",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="dependency",
        ) from error
    return shapefile


def _import_geopandas(dataset: FileDataset) -> Any:
    try:
        import geopandas
    except ModuleNotFoundError as error:
        raise KnpsParseError(
            "geopandas shapefile loading requires the optional 'geo' extra "
            "(pip install python-knps-api[geo])",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="dependency",
        ) from error
    return geopandas


def _import_pyproj(dataset: FileDataset) -> Any:
    try:
        import pyproj
    except ModuleNotFoundError as error:
        raise KnpsParseError(
            "coordinate reprojection requires the optional 'geo' extra "
            "(pip install python-knps-api[geo])",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="dependency",
        ) from error
    return pyproj
