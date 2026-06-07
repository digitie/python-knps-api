"""KNPS 파일 dataset을 typed·정규화 record로 변환하는 normalizer.

KNPS CSV header는 기관/연식에 따라 형식이 제각각이다(:mod:`knps.records` docstring
하단 "관찰된 header 변종" 참고). 이 모듈은 header→value 매핑을 받아서

- ``(CODE)`` 접미사에 임베디드된 영문 코드를 우선 추출하고,
- 코드가 없으면 순한글 header 이름으로 fallback

하여 공통 필드(:class:`KnpsPlaceRecord` / :class:`KnpsGeoRecord`)로 정규화한다.
header best-guess의 1차 책임을 provider 라이브러리(이 곳)가 지도록 해서,
downstream(``python-krtour-map`` 등)이 raw header를 추측하지 않게 한다.

관찰된 header 변종 (2026-06-07 live 다운로드 확인):

- 표준 point (visitor_centers/restrooms/campgrounds/cultural_resources):
  ``관리번호(OBJECTID)`` · ``국립공원관리번호(ID_CD)`` · ``일련번호(SEQNO)`` ·
  ``명칭_한글(KOR_NM)`` · ``명칭_영어(ENG_NM)`` · ``주소_지번(LNM_ADRES)`` ·
  ``주소_새주소(RDNMADR)`` · ``전화번호(TELNO)`` · ``고도(ELEVATION)`` ·
  ``경도(LONGITUDE)`` · ``위도(LATITUDE)``.
- weather_stations: ``번호(NO)`` · ``소속위치(STN_NAME)`` · ``아이디(STN_ID)`` ·
  ``위도(LAT)`` · ``경도(LON)`` · ``높이(HT)`` · ``주소(ADDRESS)``.
- trails: 대부분 순한글, 코드 없음 — ``국립공원관리번호`` · ``탐방코스(한글)`` ·
  ``탐방코스(영문)`` · ``경도`` · ``위도`` · ``난이도`` …
  (``(한글)``/``(영문)`` 괄호는 영문 코드가 아니므로 코드 추출에서 제외된다.)
- hazard_zones: 순한글 — ``고유번호`` · ``GIS위치``(POINT WKT) · ``국립공원명`` ·
  ``명칭`` …
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

from .models import Geometry, KnpsGeoRecord, KnpsPlaceRecord

# header 끝의 ``(영문코드)`` 접미사. 첫 글자는 ASCII 영문이어야 해서
# ``(한글)``/``(영문)`` 같은 순한글 괄호는 코드로 오인하지 않는다.
_CODE_SUFFIX = re.compile(r"\(([A-Za-z][A-Za-z0-9_ ]*)\)\s*$")

# 필드별 후보. 코드(대문자, 대소문자 무시 매칭) 우선 → 순한글 header fallback.
# live 데이터로 확정한 우선순위다. source_id는 가장 안정적인 전역 식별자를
# 선호한다: ID_CD(국립공원관리번호)는 전국 단위 안정 id라 OBJECTID/SEQNO(파일
# 로컬 일련번호)보다 우선한다.
_SOURCE_ID_CODES = ("ID_CD", "STN_ID", "OBJECTID", "SEQNO", "NO")
_SOURCE_ID_KOREAN = ("국립공원관리번호", "고유번호")

_NAME_CODES = ("KOR_NM", "STN_NAME")
_NAME_KOREAN = ("명칭_한글", "탐방코스(한글)", "소속위치", "명칭", "국립공원명")

_NAME_EN_CODES = ("ENG_NM",)
_NAME_EN_KOREAN = ("탐방코스(영문)", "명칭_영어")

_LONGITUDE_CODES = ("LONGITUDE", "LON")
_LONGITUDE_KOREAN = ("경도",)

_LATITUDE_CODES = ("LATITUDE", "LAT")
_LATITUDE_KOREAN = ("위도",)

_ROAD_ADDRESS_CODES = ("RDNMADR",)
_ROAD_ADDRESS_KOREAN = ("주소_새주소",)

_JIBUN_ADDRESS_CODES = ("LNM_ADRES", "ADDRESS")
_JIBUN_ADDRESS_KOREAN = ("주소_지번", "주소")

_TEL_CODES = ("TELNO",)
_TEL_KOREAN = ("전화번호",)

_ELEVATION_CODES = ("ELEVATION", "HT")
_ELEVATION_KOREAN = ("고도", "높이")


class HeaderIndex:
    """header→value 매핑을 코드/순한글 lookup용으로 색인한다."""

    __slots__ = ("by_code", "by_full", "by_base")

    def __init__(self, raw: Mapping[str, str | None]) -> None:
        # 코드(대문자) → value, 순한글 full header → value,
        # 코드 접미사를 떼어낸 base header → value.
        self.by_code: dict[str, str | None] = {}
        self.by_full: dict[str, str | None] = {}
        self.by_base: dict[str, str | None] = {}
        for header, value in raw.items():
            stripped = header.strip()
            self.by_full.setdefault(stripped, value)
            match = _CODE_SUFFIX.search(stripped)
            if match is not None:
                code = match.group(1).strip().upper()
                self.by_code.setdefault(code, value)
                base = stripped[: match.start()].strip()
                if base:
                    self.by_base.setdefault(base, value)
            else:
                self.by_base.setdefault(stripped, value)

    def lookup(self, codes: tuple[str, ...], korean: tuple[str, ...]) -> str | None:
        """코드 우선 → 순한글(full → base) 순으로 첫 비어있지 않은 값을 찾는다."""

        for code in codes:
            value = self.by_code.get(code.upper())
            if value is not None and value != "":
                return value
        for name in korean:
            for table in (self.by_full, self.by_base):
                value = table.get(name)
                if value is not None and value != "":
                    return value
        return None


def _maybe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _synth_source_id(raw: Mapping[str, str | None]) -> str:
    """실제 식별자가 없을 때 행 내용으로 결정적 fallback id를 만든다."""

    payload = "".join(
        f"{key}{'' if value is None else value}"
        for key, value in sorted(raw.items())
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"row:{digest[:16]}"


def _resolve_source_id(index: HeaderIndex, raw: Mapping[str, str | None]) -> str:
    resolved = index.lookup(_SOURCE_ID_CODES, _SOURCE_ID_KOREAN)
    if resolved is not None and resolved.strip():
        return resolved.strip()
    return _synth_source_id(raw)


def normalize_place_record(
    dataset_key: str,
    raw: Mapping[str, str | None],
) -> KnpsPlaceRecord:
    """header→value 매핑을 :class:`KnpsPlaceRecord`로 정규화한다.

    실제 식별자가 없는 행도 버리지 않고 행 내용 해시(``row:...``)를
    ``source_id``로 채워서 보존한다.
    """

    index = HeaderIndex(raw)
    return KnpsPlaceRecord(
        dataset_key=dataset_key,
        source_id=_resolve_source_id(index, raw),
        name=index.lookup(_NAME_CODES, _NAME_KOREAN),
        name_en=index.lookup(_NAME_EN_CODES, _NAME_EN_KOREAN),
        longitude=_maybe_float(index.lookup(_LONGITUDE_CODES, _LONGITUDE_KOREAN)),
        latitude=_maybe_float(index.lookup(_LATITUDE_CODES, _LATITUDE_KOREAN)),
        road_address=index.lookup(_ROAD_ADDRESS_CODES, _ROAD_ADDRESS_KOREAN),
        jibun_address=index.lookup(_JIBUN_ADDRESS_CODES, _JIBUN_ADDRESS_KOREAN),
        tel=index.lookup(_TEL_CODES, _TEL_KOREAN),
        elevation=_maybe_float(index.lookup(_ELEVATION_CODES, _ELEVATION_KOREAN)),
        raw=dict(raw),
    )


def normalize_geo_record(
    dataset_key: str,
    geom_wkt: str,
    raw: Mapping[str, str | None],
    *,
    centroid: tuple[float | None, float | None] | None = None,
) -> KnpsGeoRecord:
    """geometry WKT와 header→value 매핑을 :class:`KnpsGeoRecord`로 정규화한다.

    ``centroid``(대표점 lon/lat)가 주어지면 그것을 좌표로 쓰고, 없으면 속성에서
    경도/위도를 정규화해 채운다.
    """

    index = HeaderIndex(raw)
    if centroid is not None and centroid[0] is not None and centroid[1] is not None:
        longitude, latitude = centroid
    else:
        longitude = _maybe_float(index.lookup(_LONGITUDE_CODES, _LONGITUDE_KOREAN))
        latitude = _maybe_float(index.lookup(_LATITUDE_CODES, _LATITUDE_KOREAN))
    return KnpsGeoRecord(
        dataset_key=dataset_key,
        source_id=_resolve_source_id(index, raw),
        name=index.lookup(_NAME_CODES, _NAME_KOREAN),
        name_en=index.lookup(_NAME_EN_CODES, _NAME_EN_KOREAN),
        geom_wkt=geom_wkt,
        longitude=longitude,
        latitude=latitude,
        road_address=index.lookup(_ROAD_ADDRESS_CODES, _ROAD_ADDRESS_KOREAN),
        raw=dict(raw),
    )


# ---------------------------------------------------------------------------
# Geometry → WKT / 대표점 (순수 Python, geo extra 불필요)
# ---------------------------------------------------------------------------

_WKT_KEYWORDS = {
    "Point": "POINT",
    "MultiPoint": "MULTIPOINT",
    "LineString": "LINESTRING",
    "MultiLineString": "MULTILINESTRING",
    "Polygon": "POLYGON",
    "MultiPolygon": "MULTIPOLYGON",
}


def _fmt_number(value: object) -> str:
    if isinstance(value, float):
        # round-trip 가능한 최단 표현. 정수형 float은 .0을 떼서 깔끔하게.
        return repr(int(value)) if value.is_integer() else repr(value)
    return str(value)


def _fmt_position(position: object) -> str:
    if not isinstance(position, (tuple, list)):
        return _fmt_number(position)
    return " ".join(_fmt_number(item) for item in position)


def _fmt_positions(node: object) -> str:
    if not isinstance(node, (tuple, list)) or not node:
        return "()"
    if all(isinstance(item, (int, float)) for item in node):
        return _fmt_position(node)
    return "(" + ", ".join(_fmt_positions(child) for child in node) + ")"


def geometry_to_wkt(geometry: Geometry) -> str:
    """:class:`Geometry`(GeoJSON 호환)를 WKT 문자열로 변환한다."""

    keyword = _WKT_KEYWORDS[geometry.type]
    coordinates = geometry.coordinates
    if geometry.type == "Point":
        return f"{keyword} ({_fmt_position(coordinates)})"
    return f"{keyword} {_fmt_positions(coordinates)}"


def _flatten_positions(node: object) -> list[tuple[float, ...]]:
    if (
        isinstance(node, (tuple, list))
        and node
        and all(isinstance(item, (int, float)) for item in node)
    ):
        return [tuple(float(v) for v in node)]
    if isinstance(node, (tuple, list)):
        result: list[tuple[float, ...]] = []
        for child in node:
            result.extend(_flatten_positions(child))
        return result
    return []


def representative_point(geometry: Geometry) -> tuple[float | None, float | None]:
    """geometry의 대표점(lon, lat)을 구한다.

    Point는 좌표 그대로, 그 외는 모든 정점의 산술평균(근사 centroid)을 돌려준다.
    """

    positions = _flatten_positions(geometry.coordinates)
    if not positions:
        return (None, None)
    if geometry.type == "Point":
        first = positions[0]
        return (first[0], first[1])
    lon = sum(pos[0] for pos in positions) / len(positions)
    lat = sum(pos[1] for pos in positions) / len(positions)
    return (lon, lat)
