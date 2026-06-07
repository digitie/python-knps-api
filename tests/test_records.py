"""typed·정규화 record(normalizer / WKT / 전체행 reader) 단위 테스트.

fixture는 2026-06-07 live 다운로드에서 확인한 **실제 header** 3종(표준 point,
weather_stations, trails)을 그대로 사용한다.
"""

from __future__ import annotations

import io
import zipfile

from knps.artifacts import read_all_csv_rows
from knps.models import Geometry
from knps.records import (
    geometry_to_wkt,
    normalize_geo_record,
    normalize_place_record,
    representative_point,
)

# --- 실제 header fixture -----------------------------------------------------

# 표준 point (visitor_centers/restrooms/campgrounds/cultural_resources)
STANDARD_POINT_ROW: dict[str, str | None] = {
    "관리번호(OBJECTID)": "1",
    "국립공원관리번호(ID_CD)": "20101030001",
    "공원사무소코드(PO_CD)": "201",
    "분류코드(CLASS_CD)": "103",
    "일련번호(SEQNO)": "1",
    "명칭_한글(KOR_NM)": "동학사탐방안내소",
    "명칭_영어(ENG_NM)": "Donghaksa Park Information Center",
    "주소_지번(LNM_ADRES)": "충청남도 공주시 반포면 학봉리 794-1",
    "주소_새주소(RDNMADR)": "충청남도 공주시 반포면 동학사1로 295",
    "사용여부(USE_YN)": "1",
    "전화번호(TELNO)": "042-825-3002",
    "고도(ELEVATION)": "170",
    "경도(LONGITUDE)": "127.2325631",
    "위도(LATITUDE)": "36.3569579",
    "심볼코드(SYMBOL_CD)": "C",
}

# weather_stations (다른 코드 체계)
WEATHER_STATION_ROW: dict[str, str | None] = {
    "번호(NO)": "22",
    "소속위치(STN_NAME)": "청주",
    "아이디(STN_ID)": "131",
    "위도(LAT)": "36.6392",
    "경도(LON)": "127.4407",
    "높이(HT)": "57.2",
    "주소(ADDRESS)": "충청북도 청주시 흥덕구 공단로76 청주기상지청",
}

# trails (순한글, 대부분 코드 없음; (한글)/(영문) 괄호는 영문 코드가 아님)
TRAIL_ROW: dict[str, str | None] = {
    "구분": "1",
    "국립공원관리번호": "20105010001",
    "공원사무소코드": "201",
    "분류코드": "501",
    "일련번호": "1",
    "코스ID": "11",
    "탐방코스(한글)": "수통골 2코스",
    "탐방코스(영문)": "Sutonggol 2 COURSE",
    "난이도": "2.33",
    "경도": "127.2808145",
    "위도": "36.32900318",
}


def test_normalize_standard_point_uses_embedded_codes() -> None:
    rec = normalize_place_record("knps_visitor_centers", STANDARD_POINT_ROW)

    assert rec.dataset_key == "knps_visitor_centers"
    # ID_CD가 OBJECTID/SEQNO보다 우선되는 안정 식별자다.
    assert rec.source_id == "20101030001"
    assert rec.name == "동학사탐방안내소"
    assert rec.name_en == "Donghaksa Park Information Center"
    assert rec.longitude == 127.2325631
    assert rec.latitude == 36.3569579
    assert rec.road_address == "충청남도 공주시 반포면 동학사1로 295"
    assert rec.jibun_address == "충청남도 공주시 반포면 학봉리 794-1"
    assert rec.tel == "042-825-3002"
    assert rec.elevation == 170.0
    assert rec.raw == STANDARD_POINT_ROW


def test_normalize_weather_station_codes() -> None:
    rec = normalize_place_record("knps_weather_stations", WEATHER_STATION_ROW)

    assert rec.source_id == "131"  # STN_ID
    assert rec.name == "청주"  # STN_NAME
    assert rec.name_en is None
    assert rec.longitude == 127.4407  # LON
    assert rec.latitude == 36.6392  # LAT
    assert rec.jibun_address == "충청북도 청주시 흥덕구 공단로76 청주기상지청"  # ADDRESS
    assert rec.road_address is None
    assert rec.tel is None
    assert rec.elevation == 57.2  # HT


def test_normalize_trail_korean_fallback() -> None:
    rec = normalize_place_record("knps_trails", TRAIL_ROW)

    # 코드 없는 순한글 header로 fallback. 국립공원관리번호가 source_id.
    assert rec.source_id == "20105010001"
    # (한글)/(영문) 괄호는 영문 코드로 오인되지 않고 full header로 매칭된다.
    assert rec.name == "수통골 2코스"
    assert rec.name_en == "Sutonggol 2 COURSE"
    assert rec.longitude == 127.2808145
    assert rec.latitude == 36.32900318
    assert rec.road_address is None
    assert rec.tel is None


def test_code_match_is_case_insensitive() -> None:
    rec = normalize_place_record(
        "k", {"이름(kor_nm)": "치악산", "경도(longitude)": "128.0", "위도(latitude)": "37.0"}
    )
    assert rec.name == "치악산"
    assert rec.longitude == 128.0
    assert rec.latitude == 37.0


def test_source_id_priority_prefers_id_cd_over_objectid() -> None:
    rec = normalize_place_record(
        "k", {"관리번호(OBJECTID)": "99", "국립공원관리번호(ID_CD)": "ABC"}
    )
    assert rec.source_id == "ABC"


def test_numeric_parse_failure_yields_none() -> None:
    rec = normalize_place_record(
        "k", {"국립공원관리번호(ID_CD)": "1", "경도(LONGITUDE)": "없음", "고도(ELEVATION)": ""}
    )
    assert rec.longitude is None
    assert rec.elevation is None


def test_missing_id_synthesizes_deterministic_hash() -> None:
    row = {"명칭": "이름만있음"}
    rec1 = normalize_place_record("k", row)
    rec2 = normalize_place_record("k", dict(row))

    assert rec1.source_id.startswith("row:")
    assert rec1.source_id == rec2.source_id  # 결정적
    assert rec1.name == "이름만있음"


def test_missing_fields_are_none() -> None:
    rec = normalize_place_record("k", {"국립공원관리번호(ID_CD)": "1"})
    assert rec.name is None
    assert rec.name_en is None
    assert rec.longitude is None
    assert rec.latitude is None
    assert rec.jibun_address is None


def test_empty_code_value_falls_through_to_next_candidate() -> None:
    # ID_CD가 비면 다음 후보(OBJECTID)로 넘어간다.
    rec = normalize_place_record(
        "k", {"국립공원관리번호(ID_CD)": "", "관리번호(OBJECTID)": "7"}
    )
    assert rec.source_id == "7"


# --- geometry → WKT / 대표점 -------------------------------------------------


def test_geometry_to_wkt_point() -> None:
    geom = Geometry(type="Point", coordinates=(127.5, 37.5))
    assert geometry_to_wkt(geom) == "POINT (127.5 37.5)"


def test_geometry_to_wkt_linestring_and_polygon() -> None:
    line = Geometry(type="LineString", coordinates=((127.0, 37.0), (128.0, 38.0)))
    assert geometry_to_wkt(line) == "LINESTRING (127 37, 128 38)"

    poly = Geometry(
        type="Polygon",
        coordinates=(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),
    )
    assert geometry_to_wkt(poly) == "POLYGON ((0 0, 1 0, 1 1, 0 0))"


def test_geometry_to_wkt_multipolygon() -> None:
    geom = Geometry(
        type="MultiPolygon",
        coordinates=(
            (((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),
            (((2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 2.0)),),
        ),
    )
    assert geometry_to_wkt(geom) == (
        "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))"
    )


def test_representative_point_for_point_and_polygon() -> None:
    point = Geometry(type="Point", coordinates=(127.5, 37.5))
    assert representative_point(point) == (127.5, 37.5)

    line = Geometry(type="LineString", coordinates=((0.0, 0.0), (2.0, 4.0)))
    assert representative_point(line) == (1.0, 2.0)


def test_normalize_geo_record_uses_centroid_then_falls_back() -> None:
    rec = normalize_geo_record(
        "knps_trails",
        "POINT (127.28 36.33)",
        TRAIL_ROW,
        centroid=(127.28, 36.33),
    )
    assert rec.geom_wkt == "POINT (127.28 36.33)"
    assert rec.source_id == "20105010001"
    assert rec.name == "수통골 2코스"
    assert rec.longitude == 127.28
    assert rec.latitude == 36.33

    # centroid가 없으면 속성의 경도/위도로 fallback.
    rec2 = normalize_geo_record("knps_trails", "POINT (1 2)", TRAIL_ROW, centroid=None)
    assert rec2.longitude == 127.2808145
    assert rec2.latitude == 36.32900318


# --- 전체행 reader ----------------------------------------------------------


def test_read_all_csv_rows_reads_every_row_not_just_preview() -> None:
    lines = ["이름,경도,위도"] + [f"p{i},127.{i},37.{i}" for i in range(20)]
    payload = ("\n".join(lines) + "\n").encode("cp949")

    member, rows = read_all_csv_rows(payload)

    assert member is None
    assert len(rows) == 20  # 5행 preview cap이 아니라 전부
    assert rows[0] == {"이름": "p0", "경도": "127.0", "위도": "37.0"}
    assert rows[19]["이름"] == "p19"


def test_read_all_csv_rows_from_zip_first_member() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("data.csv", "이름,값\n지리산,1\n설악산,2\n")
        archive.writestr("readme.hwp", b"binary")

    member, rows = read_all_csv_rows(buffer.getvalue())

    assert member == "data.csv"
    assert len(rows) == 2
    assert rows[1] == {"이름": "설악산", "값": "2"}


def test_read_all_csv_rows_preserves_trailing_extra_columns() -> None:
    payload = "이름,값\n지리산,1,추가1,추가2\n".encode()

    _member, rows = read_all_csv_rows(payload)

    assert rows[0]["이름"] == "지리산"
    assert rows[0]["__extra_1__"] == "추가1"
    assert rows[0]["__extra_2__"] == "추가2"


def test_read_all_csv_rows_pads_short_rows_with_none() -> None:
    payload = "이름,경도,위도\n지리산\n".encode()

    _member, rows = read_all_csv_rows(payload)

    assert rows[0] == {"이름": "지리산", "경도": None, "위도": None}
