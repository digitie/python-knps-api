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
- geometry가 없는 통계/media dataset은 feature 본문에 섞지 않고 별도 timeseries/source link로 전달한다.

## 제외/보류

- 생태 연구용 식생도, 멸종위기종 서식지는 v1 feature provider 범위 밖이다. 보안/마스킹 정책이 먼저 필요하다.
- 예약 결제, 실시간 예약 가능 여부는 KNPS 예약 시스템 정책과 robots/login 흐름 확인 전까지 제외한다.

## 대피소 중첩 SHP (2026-11-07)

issue #17의 대피소 읽기는 CSV뿐 아니라 ZIP 안의 중첩 ZIP/SHP도 지원한다.
이 절은 합성 fixture로 검증한 파서 계약이며 실제 KNPS 필드·좌표계 검증이 아니다.
기존 표의 대피소 CSV 표기는 과거 카탈로그 기록이다. 현재 대피소 항목은
needs_verification이며 기존 다운로드 URL을 보존한다. 라이브 성공이나 운영 적재를 뜻하지 않는다.

    records = await client.files.read_place_records("knps_shelters")
    # PRJ가 없을 때만 공식 근거로 확인한 CRS를 호출자가 명시한다.
    # records = await client.files.read_place_records(
    #     "knps_shelters", source_crs=officially_verified_source_crs
    # )

- Point/PointZ/PointM의 XY만 WGS84 경위도로 제공한다. 부지 Polygon, MultiPoint,
  선형 레이어를 중심점으로 대체하지 않는다. Point가 없는 SHP archive는 오류다.
- 유효한 PRJ 또는 명시적 source_crs가 필수다. 없거나 잘못되면 거부한다.
  원본 숫자가 경위도처럼 보인다는 이유로 CRS를 추정하지 않는다. 명시적 CRS는 PRJ보다 우선한다.
- CPG가 있으면 해당 인코딩을 엄격히 적용한다. CPG가 없으면 기존 SHP 경로와 같은
  CP949를 사용하되 대체 문자로 복구하지 않는다. 실제 원천 인코딩 확인은 필요하다.
- DBF 영문 bare code는 대피소 경로에서만 bare_codes=True로 기존 normalizer에 연결한다.
  기존에 의미가 정의된 KOR_NM/ID_CD/OBJECTID 등의 후보만 정규화하고 새 필드는 추측하지 않는다.
  알 수 없는 속성은 raw에 남고 정규화 name은 None일 수 있다.
- 기존 normalizer가 선택한 전역 ID_CD/STN_ID는 source_id로 그대로 보존한다.
  중첩 archive나 SHP 파일명이 바뀌어도 이 ID는 바뀌지 않는다.
  전체 archive의 중복 전역 ID는 내용이 같더라도 오류다. 가짜 ID를 만들거나 덮어쓰지 않는다.
- 로컬 OBJECTID/SEQNO/NO 및 식별자 없는 행만 멤버 경로와 원래 식별자의 SHA256으로
  범위를 한정한다. 출처 경로는 source_member에 남긴다. 다른 멤버의 같은 로컬 ID/0 값은
  합쳐지지 않는다. 같은 멤버의 중복 ID는 오류다. 식별자 없는 행은 속성 해시와 실제 좌표를
  사용한다. 파일명 변경은 로컬 ID만 바꾸며, 실제 원천 ID의 품질을 검증했다고 주장하지 않는다.
- 원래 DBF key/value는 raw에 그대로 두고 예약 key 세 개를 추가한다:
  __knps_point_wgs84__ (XY JSON), __knps_source_member__, __knps_source_crs__.
  소비자가 raw만 해시해도 geometry-only 변경을 감지한다. 실제 ID가 있으면 좌표만
  이동해도 source_id는 유지된다. 예약 key 충돌은 오류다.
- pyshp Reader 생성 전에 SHP header의 실제 길이, 각 record의 양수 길이·전진·경계,
  Point body 크기와 물리 개수를 독립적으로 검증한다. DBF의 header/descriptor,
  양수 stride와 필드 폭의 합, count와 실제 bytes, 삭제 flag도 먼저 검증한다.
  SHP 물리 개수와 DBF count가 다르면 부분 성공하지 않는다.
- SHX는 있더라도 읽지 않는다. 검증된 SHP 본문을 순차 읽으므로 오래된 SHX가
  실제 Point를 숨기지 못한다. 사전 검증에서 NULL shape는 정확히 type 4 bytes만 허용한다.
  DBF 삭제 행의 NULL은 같은 행 번호와 함께 제외하고, 활성 DBF 행의 NULL은 계속 오류다.
- 중첩 ZIP 깊이 최대 3(바깥 ZIP은 0), 총 멤버 10,000, 멤버당 256 MiB,
  누적 해제 크기 512 MiB와 archive 전체 물리 SHP record 100,000개가 상한이다.
  record 상한은 각 레이어를 Reader/typed record로 만들기 전에 검사한다.
  중첩 ZIP 자체와 내부 멤버를 모두 누적 계산한다.
  경로 순회·모호한 대소문자 중복 경로는 거부하고 파일을 디스크에 추출하지 않는다.
- read_place_records의 명시적 source_crs는 대피소 SHP에만 적용한다. SHP 경로가
  아닌 plain CSV/CSV ZIP 및 다른 CSV dataset은 CSV reader/normalizer 진입 전에
  KnpsParseError로 거부한다. None 기본값의 기존 CSV 동작은 유지한다.
- 다른 dataset의 geometry 선택, CSV 전체 행 읽기, 비동기 thread offload는 그대로다.
  SHP-only bytes를 CSV 전용 read_all_csv_rows에 전달하면 계속 오류다.

### 후속 원천 확인

Claude가 공식 원본을 확보할 때 원본/멤버 지문, DBF 헤더와 한글 값, PRJ/CPG,
실제 Point 수와 Polygon 제외 수를 기록해야 한다. 합성 필드가 원천에 있다고 가정하지 않는다.
검증된 멤버·ID의 안정성과 좌표 의미를 확인한 뒤에만 카탈로그 검증 상태를 승격한다.
Map은 병합된 provider를 소비하고 동일 ID의 좌표 변경이 raw payload hash에 반영되는지
검증한다. 이 변경은 새 dataset 정책·운영 schedule·적재를 제공하지 않는다.
