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
        # PRJ 재투영 결과는 DBF에 함께 실린 경도/위도와 사실상 같다(실측 차 1.4e-14°).
        # 1e-6°(약 0.1 m)는 원점·투영 parameter의 수 m 오차도 잡는다.
        assert math.isclose(row.longitude, float(row.raw["경도"]), abs_tol=1e-6)
        assert math.isclose(row.latitude, float(row.raw["위도"]), abs_tol=1e-6)
        assert (row.road_address is None) != (row.jibun_address is None)
        assert row.source_id.startswith("shp:")
    by_name = {row.name: row for row in rows}
    jangteomok = by_name["장터목대피소"]
    assert jangteomok.road_address == "경남 함양군 마천면 백무동로 373"
    assert jangteomok.jibun_address is None
    assert by_name["세석대피소"].jibun_address == "경남 산청군시천면 내대리 산325"
    assert by_name["중청대피소"].road_address == "강원도 양양군 대청봉길 1"
    assert by_name["노인봉무인대피소"].jibun_address == "강릉시 연곡면 삼산리 산1-12"
    # 잘린 필드명은 디코딩 가능한 접두부로 보존한다(원본 provenance).
    assert jangteomok.raw["시설물"] == "장터목대피소"
    assert jangteomok.raw["순번"] == "421"
    assert jangteomok.raw["사무소"] == "지리산경남"
    # PRJ(KGD2002 Central Belt 2010)는 EPSG:5186으로 해석된다. 동봉 .qmd의 5179는 틀렸다.
    assert jangteomok.raw["__knps_source_crs__"] == "EPSG:5186"


async def test_current_official_name_drops_leading_hyeon_marker_but_raw_keeps_it():
    # 원천은 이전 대피소와 구분하려고 '現노고단대피소'로 적었다(python-knps-api#17 후속).
    rows = await _read(CURRENT.read_bytes())
    names = {row.name for row in rows}
    assert "노고단대피소" in names
    assert not any(name and name[0] in "現舊" for name in names)
    nogodan = next(row for row in rows if row.name == "노고단대피소")
    assert nogodan.raw["시설물"] == "現노고단대피소"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("現노고단대피소", "노고단대피소"),
        ("舊 노고단대피소", "노고단대피소"),
        ("(現)노고단대피소", "노고단대피소"),
        ("（舊） 노고단대피소", "노고단대피소"),
        ("노고단대피소(現)", "노고단대피소(現)"),
        ("현노고단대피소", "현노고단대피소"),
        ("現", "現"),
    ],
)
async def test_leading_status_marker_is_stripped_only_as_a_prefix(value, expected):
    # 공식 DBF처럼 10 bytes에서 잘린 "시설물명" 필드 → raw key "시설물".
    rows = await _read(_zip(_utf8_layer("시설물명".encode()[:10], value)))
    assert rows[0].name == expected
    assert rows[0].raw["시설물"] == value


def _current_with_first_point_moved(dx: float) -> bytes:
    with zipfile.ZipFile(CURRENT) as archive:
        entries = {info.filename: archive.read(info) for info in archive.infolist()}
    shp_name = next(name for name in entries if name.endswith(".shp"))
    shp = bytearray(entries[shp_name])
    # 첫 record: header 100 + record header 8 + shape type 4 → X(double, little-endian).
    (x,) = struct.unpack_from("<d", shp, 112)
    struct.pack_into("<d", shp, 112, x + dx)
    entries[shp_name] = bytes(shp)
    return _zip(entries)


async def test_current_official_identity_is_local_sequence_not_coordinates():
    rows = await _read(CURRENT.read_bytes())
    moved = await _read(_current_with_first_point_moved(30.0))
    assert [row.source_id for row in rows] == [row.source_id for row in moved]
    assert rows[0].longitude != moved[0].longitude
    # 좌표만 바뀐 갱신도 raw hash로 감지된다.
    assert rows[0].raw != moved[0].raw
    assert rows[1:] == moved[1:]


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
