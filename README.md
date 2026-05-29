# python-knps-api

국립공원공단(KNPS) 공개 파일데이터를 여행, 탐방, 안전, 기상 use case 중심으로 다루는 비공식 async Python client다.

이 package는 `python-mois-api`, `python-krheritage-api`, `python-khoa-api`, `python-krforest-api`와 같은 방향성을 따른다. 기관별 provider 라이브러리를 분리하고, `python-krtour-map`은 이 public client와 typed model/catalog를 직접 사용한다. rate limit, 예외 계층은 KNPS 전용으로 독립시킨다.

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성한다. API field, code identifier, 명령어, URL, provider 원문은 필요한 경우 원문을 유지한다.

## 설치

```bash
pip install -e ".[dev]"
```

공간데이터 SHP 파싱(`pyshp`)과 좌표 재투영(`pyproj`)은 코어 의존성이라 별도 extra 없이 사용할 수 있다.

## 다운로드

```python
import asyncio

from knps import KnpsClient


async def main() -> None:
    async with KnpsClient() as client:
        for dataset in client.files.datasets("spatial"):
            print(dataset.key, dataset.title, dataset.formats)


asyncio.run(main())
```

## Catalog 예시

```python
import asyncio

from knps import KnpsClient


async def main() -> None:
    async with KnpsClient() as client:
        for dataset in client.file_datasets("spatial"):
            print(dataset.key, dataset.data_go_id, dataset.detail_url)


asyncio.run(main())
```

KNPS는 data.go.kr에서 확인된 provider catalog가 파일데이터 중심이며, 현재 이 라이브러리의 OpenAPI catalog는 제공하지 않는다. SHP/CSV parser는 `docs/knps-feature-etl.md`의 dataset별 변환 규칙에 맞춰 확장한다.

## File dataset

File-data namespace는 curated catalog를 제공한다. 2026-05-25 live check 기준으로 data.go.kr 직접 다운로드 URL이 확인된 dataset은 별도 키 없이 `client.files.download(...)`로 bytes를 받을 수 있다. 다운로드한 ZIP/CSV는 `client.files.download_artifact(...)`로 `FileArtifact`/`FileMember`/`CsvPreview` Pydantic v2 DTO로 읽을 수 있다. 아직 다운로드 URL 검증이 필요한 dataset은 catalog에서 `verification_status="needs_verification"`으로 표시한다.

```python
async with KnpsClient() as client:
    artifact = await client.files.download_artifact("knps_lod_table_catalog")
    print(artifact.kind, artifact.csv_previews[0].headers)
```

## Geometry 추출

공간데이터(SHP ZIP, WKT/위경도 CSV)는 `pyshp`/`pyproj` 코어 의존성으로 `GeoFeatureCollection`으로 추출한다. shapefile `.prj` 또는 명시한 `source_crs`가 확인되면 WGS84로 재투영하고, 원본 좌표계는 `source_crs`에 보존한다.

```python
async with KnpsClient() as client:
    collection = await client.files.download_geometries(
        "knps_park_boundaries",
        source_crs="EPSG:5179",  # .prj가 있으면 생략 가능
    )
    print(collection.geometry_type, collection.source_crs, collection.crs)
    print(collection.features[0].as_geojson)
```

CSV는 WKT 컬럼(`wkt`/`geom`/`the_geom` 등) 또는 위경도 컬럼(`경도`/`위도`, `lon`/`lat`, `x`/`y`)을 자동 감지한다. 좌표계를 알 수 없으면 재투영 없이 원본 좌표를 그대로 보존한다. shapefile 한글 속성은 기본 `cp949`로 디코드한다.

## Debug UI

Streamlit 기반 디버그 UI는 KNPS file dataset catalog를 빠르게 확인하고, Metadata, Catalog, Fixture 탭으로 검토할 수 있다.

```bash
pip install -e ".[debug-ui]"
streamlit run debug_ui/app.py
```

## Scope

v1 scope는 `python-krtour-map/docs/forest-feature-etl.md`의 KNPS 통합 계획을 라이브러리로 분리한 것이다.

- 국립공원 경계, 탐방로, 탐방안내소, 위험지역, 기상관측시설, 화장실, 문화자원
- 야영장, 대피소, 선형시설, 보호지역, 탐방객 통계
- 파일데이터는 원본 catalog와 bytes download primitive를 제공하고, feature 변환은 downstream ETL에서 수행한다.

## 문서 지도

- [`docs/knps-api.md`](docs/knps-api.md) — KNPS API/file dataset catalog와 client 방향성
- [`docs/knps-feature-etl.md`](docs/knps-feature-etl.md) — `python-krtour-map` feature/notice/weather 적재 계약
- [`docs/decisions.md`](docs/decisions.md) — 프로젝트 기술 및 정책 의사결정
- [`docs/testing.md`](docs/testing.md) — 테스트/fixture/live test 정책

## Reference

Curated scope는 data.go.kr의 국립공원공단 공개 데이터, `python-krtour-map/docs/forest-feature-etl.md`, 그리고 공개 검색으로 확인 가능한 국립공원 공간데이터 안내를 기준으로 작성했다. data.go.kr 검색/상세 페이지는 운영 상태와 로그인 흐름에 따라 응답이 달라질 수 있으므로, ID와 다운로드 URL은 live test에서 계속 검증한다.
