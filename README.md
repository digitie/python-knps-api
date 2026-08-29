# python-knps-api

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![GPL-3.0-or-later 라이선스](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)
![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)

국립공원공단(KNPS) 공개 파일데이터를 여행, 탐방, 안전, 기상 use case 중심으로 다루는 비공식 async Python client다. `KnpsClient`는 file dataset catalog 조회, 원본 bytes/artifact 다운로드, 공간데이터 geometry 추출, heterogeneous CSV의 typed·정규화 record 변환을 하나의 표면으로 제공한다.

이 package는 `python-mois-api`, `python-krheritage-api`, `python-khoa-api`, `python-krforest-api`와 같은 방향성을 따른다. 기관별 provider 라이브러리를 분리하고, `python-krtour-map`은 이 public client와 typed model/catalog를 직접 사용한다. rate limit, 예외 계층은 KNPS 전용으로 독립시킨다.

최근 변경 사항은 [`CHANGELOG.md`](CHANGELOG.md) `[Unreleased]`를 참고한다.

## 제공 표면

| 표면 | 진입점 | 설명 |
|------|--------|------|
| File dataset catalog | `client.files.datasets(category)` / `client.file_datasets(category)` | 카테고리별 curated `FileDataset` catalog 조회 |
| 원본 bytes 다운로드 | `await client.files.download(key)` | 직접 다운로드 URL이 확인된 dataset의 bytes 반환 |
| Artifact 파싱 | `await client.files.download_artifact(key)` | ZIP/CSV를 `FileArtifact`/`FileMember`/`CsvPreview` Pydantic v2 DTO로 변환 |
| Geometry 추출 | `await client.files.download_geometries(key, ...)` | SHP/CSV를 `GeoFeatureCollection`으로 추출하고 WGS84로 재투영(`geo` extra 필요) |
| Typed·정규화 record | `await client.files.read_place_records(key)` / `read_geo_records(key)` | heterogeneous CSV header를 공통 필드로 정규화한 `KnpsPlaceRecord`/`KnpsGeoRecord` 반환 |
| RustFS(S3 호환) 이중 저장 | `await client.files.download_to_rustfs(key, ...)` | 로컬 저장과 동시에 S3 호환 저장소에 적재(ADR-004) |
| Debug UI | `streamlit run examples/streamlit_debug_ui.py` | dataset 선택 후 실제 download/geometry/RustFS 오퍼레이션을 실행하고 Raw Response/Pydantic Model/Processed Result/Validation Errors/Debug Trace/Fixture 6탭으로 검토 |

## 먼저 읽을 문서

| 필요 정보 | 문서 |
|-----------|------|
| KNPS API/file dataset catalog와 client 방향성 | [`docs/knps-api.md`](docs/knps-api.md) |
| `python-krtour-map` feature/notice/weather 적재 계약 | [`docs/knps-feature-etl.md`](docs/knps-feature-etl.md) |
| 프로젝트 구조적 의사결정(ADR) | [`docs/decisions.md`](docs/decisions.md) |
| 테스트/fixture/live test 정책 | [`docs/testing.md`](docs/testing.md) |
| 작업 백로그(T-NNN) | [`docs/tasks.md`](docs/tasks.md) |
| 개발 기록과 결정 일지 | [`docs/journal.md`](docs/journal.md) |
| 변경 이력 | [`CHANGELOG.md`](CHANGELOG.md) |

## 설치 + 사용법

```bash
pip install -e ".[dev]"

# 공간데이터 ZIP/SHP/GeoJSON 파싱을 구현할 때는 geo extra를 추가한다.
pip install -e ".[dev,geo]"
```

```python
import asyncio

from knps import KnpsClient


async def main() -> None:
    async with KnpsClient() as client:
        for dataset in client.files.datasets("spatial"):
            print(dataset.key, dataset.title, dataset.formats)

        data = await client.files.download("knps_lod_table_catalog")
        artifact = await client.files.download_artifact("knps_lod_table_catalog")
        print(len(data), artifact.kind, artifact.csv_previews[0].headers)


asyncio.run(main())
```

KNPS는 data.go.kr에서 확인된 provider catalog가 파일데이터 중심이며, 현재 이 라이브러리의 OpenAPI catalog는 제공하지 않는다. SHP/CSV parser는 `docs/knps-feature-etl.md`의 dataset별 변환 규칙에 맞춰 확장한다. Debug UI는 `pip install -e ".[debug-ui]"` 후 `streamlit run examples/streamlit_debug_ui.py`로 실행한다(이 저장소는 파일 카탈로그라 서비스키가 필요 없다).

## 예제: Typed·정규화 record

heterogeneous한 KNPS CSV header(예: `명칭_한글(KOR_NM)` vs `소속위치(STN_NAME)` vs 순한글 `탐방코스(한글)`)를 downstream이 best-guess하지 않도록, `read_place_records` / `read_geo_records`가 공통 필드로 정규화한 typed record(`KnpsPlaceRecord` / `KnpsGeoRecord`)를 돌려준다. normalizer는 header의 `(영문코드)` 접미사를 먼저 시도하고, 코드가 없으면 순한글 header 이름으로 fallback한다. 원본 header→value 매핑 전체는 `raw`에 보존된다.

```python
async with KnpsClient() as client:
    # point CSV (탐방안내소/화장실/야영장/문화자원/기상관측시설 등) — 전체 행 정규화
    places = await client.files.read_place_records("knps_visitor_centers")
    print(places[0].source_id, places[0].name, places[0].longitude, places[0].latitude)

    # 공간 dataset — geometry는 WKT로, 속성은 정규화 필드로
    geo = await client.files.read_geo_records("knps_trails")
    print(geo[0].name, geo[0].geom_wkt[:40], geo[0].longitude, geo[0].latitude)
```

이 예제는 point/geo CSV 정규화만 다룬다 — `read_place_records`는 preview가 아니라 첫 CSV member의 모든 행을 읽고, `read_geo_records`는 `download_geometries` 위에 올라가므로 폴리곤 SHP dataset(`knps_park_boundaries`/`knps_protected_areas` 등)은 `geo` extra(`pyshp`/`pyproj`)가 설치돼 있어야 하며 없으면 `KnpsParseError`가 난다.

## 검증

```bash
pip install -e ".[dev,geo]"
python -m ruff check .
python -m mypy src/knps
python -m pytest -q -m "not live"
python -m pytest -q -m live   # 실 KNPS/data.go.kr 서버 호출, 선택
```

## 데이터/외부 API 출처

Curated scope는 data.go.kr의 국립공원공단 공개 데이터, `python-krtour-map/docs/forest-feature-etl.md`, 그리고 공개 검색으로 확인 가능한 국립공원 공간데이터 안내를 기준으로 작성했다. 다루는 도메인은 국립공원 경계·탐방로·탐방안내소·위험지역·기상관측시설·화장실·문화자원·야영장·대피소·선형시설·보호지역·탐방객 통계이며, 파일데이터는 원본 catalog와 bytes download primitive를 제공하고 feature 변환은 downstream ETL에서 수행한다. data.go.kr 검색/상세 페이지는 운영 상태와 로그인 흐름에 따라 응답이 달라질 수 있으므로, ID와 다운로드 URL은 live test에서 계속 검증한다.

## 디렉터리 개요

| 경로 | 설명 |
|------|------|
| `src/knps/` | `knps` 패키지 소스(`client`, `catalog`, `files`, `geometry`, `records`, `config`, `exceptions`, `debug`) |
| `tests/` | pytest 기반 단위/live 테스트 |
| `docs/` | 설계 문서, ADR, 태스크, 일지 |
| `examples/streamlit_debug_ui.py` | Streamlit 기반 디버그 UI(`debug-ui` extra 필요) |
| `.github/workflows/` | CI(lint/typecheck/test) |

## 문서/기여 규칙

- 모든 Markdown 문서는 한글로 작성한다(코드 식별자/API 필드명/명령어/URL/제공자 원문 용어만 예외) — 자세한 규칙은 `AGENTS.md`를 참고한다.
- 구조적 의사결정은 `docs/decisions.md`에 ADR로 기록하고, 순수 개발 규칙은 `AGENTS.md`에 둔다.
- 사용자 가시 변경은 `CHANGELOG.md`에 반영한다.
- PR 전 `ruff check`, `mypy`, `pytest -m "not live"`를 로컬에서 통과시킨다.

## 법적 고지

이 저장소의 라이선스(GPL-3.0-or-later, [`LICENSE`](LICENSE))는 이 저장소의 코드에만 적용된다. 국립공원공단, 공공데이터포털(data.go.kr)이 제공하는 상위 데이터/API의 이용은 각 제공기관의 이용약관과 재배포 조건을 따라야 하며, 이 저장소가 그 준수를 보장하지 않는다.
