# KNPS file dataset scope

이 문서는 `python-knps-api`가 제공할 국립공원공단(KNPS) 공개 데이터 catalog와 public client 방향성을 기록한다.

## Client API shape

- public client는 `httpx`/`asyncio` 기반이다.
- 생성 방식은 `KnpsClient()`, `KnpsClient.from_env()`, `async with`를 지원한다.
- data.go.kr 파일 다운로드는 2026-05-25 live check 기준으로 별도 키 없이 동작한다.
- `rate limit`, `exception`은 KNPS 전용 계층이다. 다른 provider의 예외를 import하지 않는다.
- downstream인 `python-krtour-map`은 wrapper/adapter를 만들지 않고 이 라이브러리의 public client/catalog/model을 직접 사용한다.

## 구현 상태

| 영역 | 상태 | 비고 |
|------|------|------|
| catalog model | implemented | `FileDataset`, `CatalogEntry` |
| file dataset catalog | implemented | 13개 직접 다운로드 URL 검증, `knps_basic_statistics`는 URL 미확인 |
| file artifact DTO | implemented | `FileArtifact`, `FileMember`, `CsvPreview` |
| SHP/CSV geometry parser | implemented | `geo` extra의 `pyshp`/`pyproj`로 `GeoFeatureCollection` 추출, `.prj`/명시 `source_crs`로 WGS84 재투영 |
| geopandas loader | implemented | `geo` extra로 ZIP shapefile을 `GeoDataFrame`으로 로드 (`read_shapefile_geodataframe`, `client.files.download_geodataframe`) |
| typed feature model | planned | 원본 provider model만 제공, feature 변환은 krtour-map ETL |

## OpenAPI

KNPS는 현재 이 라이브러리에서 OpenAPI catalog를 제공하지 않는다. data.go.kr의 KNPS 공개 catalog는 파일데이터 중심이며, `apis.data.go.kr/B551011/...` prefix는 한국관광공사(KTO) 서비스 코드라 KNPS endpoint로 사용하지 않는다. 추정 URL은 catalog와 debug UI에 올리지 않는다.

## File datasets

`python-krtour-map/docs/forest-feature-etl.md`의 KNPS §11을 seed catalog로 삼는다. data.go.kr 상세 ID는 live test에서 확정하며, 확정 전에는 `verification_status="needs_verification"`을 유지한다.

| key | 공식 이름 | data.go.kr | format | geometry | feature |
|-----|-----------|------------|--------|----------|---------|
| `knps_park_boundaries` | 국립공원공단_국립공원 공원경계_20231231 | `15017313` | SHP | MultiPolygon | area |
| `knps_trails` | 국립공원공단_국립공원 탐방로 공간데이터_20170928 | `15003467` | CSV | LineString | route |
| `knps_visitor_centers` | 국립공원공단_국립공원 탐방안내소 공간데이터_20141219 | `15003445` | CSV | Point | place |
| `knps_hazard_zones` | 국립공원공단_국립공원 위험지역 공간데이터_20180816 | `15003441` | CSV | Polygon | area |
| `knps_weather_stations` | 국립공원공단_통합방재시스템_기상관측장비_20210928 | `15090557` | CSV | Point | weather |
| `knps_restrooms` | 국립공원공단_국립공원 화장실 공간데이터_20141219 | `15003468` | CSV | Point | place |
| `knps_cultural_resources` | 국립공원공단_국립공원 문화자원 공간데이터_20141219 | `15003443` | CSV | Point | place |
| `knps_campgrounds` | 국립공원공단_국립공원 야영장 공간데이터_20141219 | `15003469` | CSV | Point | place |
| `knps_shelters` | 국립공원공단_국립공원 대피소_20131102 | `2982556` | CSV | Point | place |
| `knps_park_offices` | 국립공원 공원사무소 공간데이터_20180813 | `15003440` | CSV | Point | place |
| `knps_linear_facilities` | 국립공원공단_국립공원 선형시설_20181231 | `15091972` | CSV | LineString | route |
| `knps_basic_statistics` | 국립공원공단_국립공원기본통계2020 | `15087598` | CSV | n/a | timeseries |
| `knps_visitor_statistics` | 국립공원공단_국립공원 탐방객 통계 | `15107577` | CSV/XLSX | n/a | timeseries |
| `knps_protected_areas` | 국립공원공단_한국보호지역 데이터_20161231 | `15127921` | CSV | Polygon | area |
| `knps_lod_table_catalog` | 국립공원공단_LOD 공간데이터 테이블 목록 | `15118945` | CSV | n/a | metadata |

## 공간데이터 처리 원칙

- 원본 좌표계는 EPSG:5179 또는 5186일 수 있다. parser는 `source_crs`(또는 shapefile `.prj`)가 확인되면 WGS84로 재투영하고, `GeoFeatureCollection.source_crs`/`crs`에 원본·현재 좌표계를 함께 보존한다. 좌표계를 알 수 없으면 원본 좌표를 그대로 둔다.
- SHP 한글 인코딩은 CP949 가능성을 기본 고려한다 (`pyshp`에 `encoding="cp949"` 적용).
- ZIP 내부에 CSV와 shapefile이 함께 있으면 record 식별자는 shapefile attribute를 우선하고, CSV는 부가 필드 보강에 사용한다.
- geometry 추출은 `client.files.extract_geometries(key, data, ...)` 또는 `await client.files.download_geometries(key, ...)`로 호출한다. CSV는 WKT 컬럼 또는 위경도 컬럼을 자동 감지한다.
- shapefile을 `geopandas.GeoDataFrame`으로 바로 받으려면 `geo` extra를 설치하고 `client.files.read_geodataframe(key, data, ...)` 또는 `await client.files.download_geodataframe(key, ...)`를 사용한다. 한글 속성은 기본 `cp949`로 디코드한다.
- geometry가 없는 통계/media dataset은 feature 본문에 섞지 않고 별도 timeseries/source link로 전달한다.

## 제외/보류

- 생태 연구용 식생도, 멸종위기종 서식지는 v1 feature provider 범위 밖이다. 보안/마스킹 정책이 먼저 필요하다.
- 예약 결제, 실시간 예약 가능 여부는 KNPS 예약 시스템 정책과 robots/login 흐름 확인 전까지 제외한다.
