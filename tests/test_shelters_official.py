"""공식 대피소 원천 파일 회귀 (python-knps-api#17).

fixture는 data.go.kr 2982556에서 받은 원본 그대로다(크기가 작아 자르지 않았다).

- ``knps_shelters_20230928_FILE_000000003681543.zip`` — 현재 배포본(2026-11-09 수신,
  SHA256 3c73d523…cdfc9, 4,820 bytes). 평면 SHP 1개, CPG UTF-8, PRJ KGD2002 Central
  Belt 2010. DBF 필드명이 10 bytes에서 잘려 UTF-8 다중 바이트 문자가 반쯤 남아 있다.
- ``knps_shelters_20131102_FILE_000000000377005.zip`` — 이전 카탈로그 URL의 2013년
  배포본(SHA256 7be2d907…8b0ac, 18,845 bytes). 중첩 SHP ZIP, CPG 없음(CP949).
"""

import io
import math
import struct
import zipfile
from pathlib import Path

import httpx
import pytest
import shapefile
from pyproj import CRS

from knps import KnpsClient
from knps.catalog import file_dataset
from knps.exceptions import KnpsParseError

FIXTURES = Path(__file__).parent / "fixtures" / "shelters"
CURRENT = FIXTURES / "knps_shelters_20230928_FILE_000000003681543.zip"
LEGACY = FIXTURES / "knps_shelters_20131102_FILE_000000000377005.zip"


async def _read(payload: bytes):
    def respond(request):
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        async with KnpsClient(session=session, max_rps=None) as client:
            return await client.files.read_place_records("knps_shelters")


def _zip(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return stream.getvalue()


async def test_current_official_archive_yields_all_named_shelters():
    rows = await _read(CURRENT.read_bytes())
    assert len(rows) == 22
    assert len({row.source_id for row in rows}) == 22
    names = {row.name for row in rows}
    assert {"중청대피소", "장터목대피소", "세석대피소", "희운각대피소"} <= names
    assert all(row.name for row in rows)
    for row in rows:
        # PRJ 재투영 결과가 DBF에 함께 실린 경도/위도와 맞아야 한다(소수 6자리 반올림).
        assert math.isclose(row.longitude, float(row.raw["경도"]), abs_tol=2e-4)
        assert math.isclose(row.latitude, float(row.raw["위도"]), abs_tol=2e-4)
        assert row.jibun_address
        assert row.source_id.startswith("shp:")
    jangteomok = next(row for row in rows if row.name == "장터목대피소")
    assert jangteomok.jibun_address == "경남 함양군 마천면 백무동로 373"
    # 잘린 필드명은 디코딩 가능한 접두부로 보존한다(원본 provenance).
    assert jangteomok.raw["시설물"] == "장터목대피소"
    assert jangteomok.raw["순번"] == "421"
    assert jangteomok.raw["사무소"] == "지리산경남"
    # PRJ(KGD2002 Central Belt 2010)는 EPSG:5186으로 해석된다. 동봉 .qmd의 5179는 틀렸다.
    assert jangteomok.raw["__knps_source_crs__"] == "EPSG:5186"


async def test_current_official_identity_is_local_sequence_not_coordinates():
    rows = await _read(CURRENT.read_bytes())
    again = await _read(CURRENT.read_bytes())
    assert [row.source_id for row in rows] == [row.source_id for row in again]


async def test_legacy_2013_archive_keeps_global_id_cd():
    rows = await _read(LEGACY.read_bytes())
    assert len(rows) == 8
    assert {row.source_id for row in rows} >= {"200101050002", "090101050001"}
    assert all(row.name for row in rows)


def _utf8_layer(field_name: bytes, value: str = "대피소") -> dict[str, bytes]:
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, encoding="utf-8") as writer:
        writer.field("PLACEHOLD", "C", size=40)
        writer.point(127.5, 37.5)
        writer.record(value)
    raw = bytearray(dbf.getvalue())
    raw[32:43] = field_name.ljust(11, b"\0")[:11]
    return {
        "p.shp": shp.getvalue(),
        "p.dbf": bytes(raw),
        "p.cpg": b"UTF-8",
        "p.prj": CRS.from_epsg(4326).to_wkt().encode(),
    }


async def test_only_a_trailing_incomplete_field_name_sequence_is_trimmed():
    # "시설물명"(12 bytes)이 10 bytes에서 잘린 형태.
    truncated = "시설물명".encode()[:10]
    rows = await _read(_zip(_utf8_layer(truncated)))
    assert rows[0].name == "대피소"
    assert set(rows[0].raw) >= {"시설물"}


async def test_invalid_bytes_inside_a_field_name_still_fail():
    broken = b"\xff" + "시설".encode()
    with pytest.raises(KnpsParseError, match="encoding"):
        await _read(_zip(_utf8_layer(broken)))


async def test_unrecognized_shelter_schema_fails_loudly_with_field_names():
    entries = _utf8_layer(b"NOTANAME")
    with pytest.raises(KnpsParseError, match=r"no recognizable shelter name.*NOTANAME"):
        await _read(_zip(entries))


def test_catalog_points_at_current_verified_shp_release():
    dataset = file_dataset("knps_shelters")
    assert dataset.formats == ("SHP",)
    assert "FILE_000000003681543" in (dataset.download_url or "")
    assert dataset.title.endswith("_20230928")
    assert dataset.verification_status == "verified"


def test_fixture_bytes_are_the_recorded_official_files():
    import hashlib

    assert hashlib.sha256(CURRENT.read_bytes()).hexdigest().startswith("3c73d523d53e0892")
    assert hashlib.sha256(LEGACY.read_bytes()).hexdigest().startswith("7be2d9075c881864")
    assert struct.unpack_from("<I", CURRENT.read_bytes(), 0)[0] == 0x04034B50
