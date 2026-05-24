# knps-feature-etl.md — 국립공원공단(KNPS) ETL

본 문서는 KNPS 데이터를 `python-krtour-map`의 `place`/`area`/`route`/`notice`/`WeatherValue`로 정규화하는 계약이다.

## 1. 문서 정보

| 항목 | 값 |
|------|----|
| provider | `python-knps-api` |
| import | `from knps import KnpsClient` |
| Feature.kind | `place`, `area`, `route`, `weather` / notice / timeseries |
| 코드 entrypoint | `krtour.map.providers.knps`, `krtour.map.knps` |
| 인증 | `KNPS_SERVICE_KEY` 또는 `DATA_GO_KR_SERVICE_KEY` |
| 갱신 주기 | dataset별 (안전 notice: 30분~일, 공간데이터: 월~연) |

## 2. dataset 매핑

| dataset_key | provider catalog | feature/detail |
|-------------|------------------|----------------|
| `knps_park_boundaries` | `client.files.dataset("knps_park_boundaries")` | Polygon/MultiPolygon → `area`, `area_kind="national_park"` |
| `knps_trails` | `client.files.dataset("knps_trails")` | LineString/MultiLineString → `route`, `route_type="hiking_trail"` |
| `knps_visitor_centers` | `client.files.dataset("knps_visitor_centers")` | Point → `place`, `place_kind="visitor_center"` |
| `knps_hazard_zones` | `client.files.dataset("knps_hazard_zones")` | Polygon/MultiPolygon → `area`, `area_kind="hazard_zone"` |
| `knps_weather_stations` | `client.files.dataset("knps_weather_stations")` | Point → weather-only feature anchor |
| `knps_restrooms` | `client.files.dataset("knps_restrooms")` | Point → `place`, `place_kind="restroom_national_park"` |
| `knps_cultural_resources` | `client.files.dataset("knps_cultural_resources")` | Point → `place`, 문화자원 subtype 분기 |
| `knps_campgrounds` | `client.files.dataset("knps_campgrounds")` | Point/Polygon → `place` 또는 `area`, `place_kind="campground"` |
| `knps_shelters` | `client.files.dataset("knps_shelters")` | Point → `place`, `place_kind="mountain_shelter"` |
| `knps_access_restrictions` | `client.raw_endpoint("knps_access_restrictions")` | notice, `notice_type="access_restriction"` |
| `knps_fire_alerts` | `client.raw_endpoint("knps_fire_alerts")` | notice, `notice_type="fire_alert"` |
| `knps_recommended_courses` | `client.files.dataset("knps_recommended_courses")` | LineString → `route`, difficulty 직접 채움 |
| `knps_park_photos` | `client.files.dataset("knps_park_photos")` | feature_files/source_links media |
| `knps_visitor_statistics` | `client.files.dataset("knps_visitor_statistics")` | feature 본문 X, monthly timeseries |

## 3. 매핑 룰

- 공원경계는 `area`로 적재하고 대표점은 polygon centroid를 사용한다.
- 탐방로와 추천 탐방코스는 `route`로 적재한다. 구간 상태가 통제이면 route payload에 보존하고 notice dataset과 연결한다.
- 위험지역은 관광 category를 만들지 않고 `AreaDetail.area_kind="hazard_zone"`과 `payload.hazard_type`, `payload.risk_grade`로 표현한다.
- 기상관측시설은 weather-only feature anchor다. 관측값이 별도 API로 확보되면 `WeatherValue`로 분리 적재한다.
- 화장실, 탐방안내소, 야영장, 대피소는 `place`다.
- 문화자원은 `RESOURCE_TYPE`에 따라 사찰/유적/기타 문화자원으로 category를 분기한다.
- 통계와 media는 feature 본문에 섞지 않는다. 통계는 별도 timeseries, 사진/VR은 `feature_files` 또는 `source_links(role="media")`로 연결한다.

## 4. category

| 종류 | category 코드 | detail | marker_icon |
|------|---------------|--------|-------------|
| 국립공원 경계 | `01020101` `TOURISM_NATURAL_LANDSCAPE_MOUNTAIN_VALLEY_NATIONAL_PARK` | `area_kind="national_park"` | `park` |
| 탐방로/추천코스 | `01020103` `TOURISM_NATURAL_LANDSCAPE_MOUNTAIN_VALLEY_FOREST_TRAIL` | `route_type="hiking_trail"` | `park` |
| 탐방안내소 | `01060101` `TOURISM_INFORMATION_CENTER_PUBLIC` | `place_kind="visitor_center"` | `information` |
| 위험지역 | category 없음 | `area_kind="hazard_zone"` | `barrier` |
| 화장실 | `05060000` `CONVENIENCE_TOILET` | `place_kind="restroom_national_park"` | `toilet` |
| 문화자원: 사찰 | `01070100` `TOURISM_HERITAGE_TEMPLE` | `place_kind="temple"` | `religious-buddhist` |
| 문화자원: 유적 | `01070300` `TOURISM_HERITAGE_HISTORIC_SITE` | `place_kind="historic_site"` | `monument` |
| 문화자원: 기타 | `01070000` `TOURISM_HERITAGE` | `place_kind="cultural_resource"` | `monument` |
| 야영장 | `03060100` `LODGING_CAMPGROUND_AUTO` | `place_kind="campground"` | `campsite` |
| 대피소 | `03080100` `LODGING_MOUNTAIN_SHELTER_KNPS` | `place_kind="mountain_shelter"` | `shelter` |

> downstream `python-krtour-map`의 maki dispatch (ADR-027, ADR-029)와 일치한다. 표준 Maki 아이콘 집합에 `danger`는 없고 위험지역에는 `barrier`(또는 `alert`)를 사용한다. 대피소는 `shelter`(Maki 표준)로 통일한다.

## 5. 핵심 함수

```python
async def park_boundaries_to_bundles(items, *, fetched_at, reverse_geocoder=None):
    ...

async def trails_to_bundles(items, *, fetched_at, reverse_geocoder=None):
    ...

async def facility_points_to_bundles(items, *, dataset_key, fetched_at, reverse_geocoder=None):
    ...

async def hazard_zones_to_bundles(items, *, fetched_at, reverse_geocoder=None):
    ...

async def access_restrictions_to_notices(items, *, fetched_at):
    ...
```

## 6. Dagster asset 카탈로그

| asset | dataset_key | cron | group | concurrency |
|-------|-------------|------|-------|-------------|
| `feature_area_knps_park_boundaries` | `knps_park_boundaries` | `0 3 1 1 *` | `features_area` | `knps_api: 1` |
| `feature_route_knps_trails` | `knps_trails` | `0 3 1 */3 *` | `features_route` | `knps_api: 1` |
| `feature_place_knps_visitor_centers` | `knps_visitor_centers` | `0 3 1 1,7 *` | `features_place` | `knps_api: 1` |
| `feature_area_knps_hazard_zones` | `knps_hazard_zones` | `0 3 1 * *` | `features_area` | `knps_api: 1` |
| `feature_weather_knps_stations` | `knps_weather_stations` | `0 3 1 1 *` | `features_weather` | `knps_api: 1` |
| `feature_place_knps_restrooms` | `knps_restrooms` | `0 3 1 1,7 *` | `features_place` | `knps_api: 1` |
| `feature_place_knps_cultural_resources` | `knps_cultural_resources` | `0 3 1 1 *` | `features_place` | `knps_api: 1` |
| `feature_place_knps_campgrounds` | `knps_campgrounds` | `0 3 1 */3 *` | `features_place` | `knps_api: 1` |
| `feature_place_knps_shelters` | `knps_shelters` | `0 3 1 1 *` | `features_place` | `knps_api: 1` |
| `notice_knps_access_restrictions` | `knps_access_restrictions` | `0 5 * * *` | `features_notice` | `knps_api: 1` |
| `notice_knps_fire_alerts` | `knps_fire_alerts` | `*/30 * * * *` | `features_notice` | `knps_api: 1` |

## 7. 검증

- catalog key 중복 없음.
- `data_go_id`가 있는 dataset은 detail URL reachability를 live test에서 검증한다.
- SHP/GeoJSON parser 도입 후 fixture는 dataset별 최소 1건, geometry type별 1건 이상 둔다.
- 통제/산불 notice는 만료일, 발령일, source URL 보존을 테스트한다.

## 8. 후속

1. data.go.kr 상세 ID와 직접 다운로드 URL 확정.
2. SHP/GeoJSON ZIP parser 구현.
3. `python-krtour-map`에 `krtour.map.providers.knps`와 loader 추가.
4. 위험지역/대피소/notice type 관련 ADR을 accepted로 전환.
