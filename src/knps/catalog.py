"""국립공원공단 공개 데이터 카탈로그."""

from __future__ import annotations

from .models import ApiEndpoint, CatalogEntry, Category, FileDataset

DATA_GO_BASE = "https://www.data.go.kr/data"


API_ENDPOINTS: tuple[ApiEndpoint, ...] = (
    ApiEndpoint(
        key="knps_visitor_statistics",
        title="국립공원공단_국립공원 탐방객 통계",
        data_go_id="15107577",
        categories=("statistics", "park"),
        provider="data.go.kr",
        service="file_or_api",
        operation="visitorStatistics",
        url="https://apis.data.go.kr/B551011/KnpsVisitorService/visitorStatistics",
        detail_url=f"{DATA_GO_BASE}/15107577/fileData.do",
        description=(
            "국립공원별 월별 탐방객 통계. 공개 검색에서 파일데이터 링크가 "
            "확인되었고 API endpoint는 live 검증 대상이다."
        ),
        notes=(
            "data.go.kr 상세는 파일데이터로 확인된다. API 형태 제공 여부는 "
            "기관 개편에 따라 달라질 수 있다."
        ),
        verification_status="needs_verification",
    ),
    ApiEndpoint(
        key="knps_access_restrictions",
        title="국립공원공단_국립공원 입산통제정보",
        data_go_id="",
        categories=("safety", "trail"),
        provider="data.go.kr",
        service="knpsRestrictionService",
        operation="getRestrictionList",
        url="https://apis.data.go.kr/B551011/KnpsRestrictionService/getRestrictionList",
        detail_url="https://www.data.go.kr/tcs/dss/selectDataSetList.do?orgFullName=국립공원공단",
        description="공원/구간별 입산통제, 탐방로 통제, 통제기간 정보를 조회하는 후보 API.",
        notes="dataset ID와 operation은 live 검증 필요. notice_type=access_restriction 후보.",
        verification_status="planned",
    ),
    ApiEndpoint(
        key="knps_fire_alerts",
        title="국립공원공단_국립공원 산불경보정보",
        data_go_id="",
        categories=("safety",),
        provider="data.go.kr",
        service="knpsFireAlertService",
        operation="getFireAlertList",
        url="https://apis.data.go.kr/B551011/KnpsFireAlertService/getFireAlertList",
        detail_url="https://www.data.go.kr/tcs/dss/selectDataSetList.do?orgFullName=국립공원공단",
        description="국립공원 산불경보/주의보를 notice로 적재하기 위한 후보 API.",
        notes="dataset ID와 operation은 live 검증 필요. notice_type=fire_alert 후보.",
        verification_status="planned",
    ),
)


FILE_DATASETS: tuple[FileDataset, ...] = (
    FileDataset(
        key="knps_park_boundaries",
        title="국립공원공단_국립공원 공원경계 공간데이터",
        data_go_id="15084538",
        categories=("park", "spatial"),
        formats=("SHP", "GeoJSON", "CSV", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084538/fileData.do",
        description="국립공원 경계 polygon 공간데이터.",
        geometry_type="MultiPolygon",
        feature_kind="area",
        update_cycle="yearly",
    ),
    FileDataset(
        key="knps_trails",
        title="국립공원공단_국립공원 탐방로 공간데이터",
        data_go_id="15084540",
        categories=("trail", "spatial"),
        formats=("SHP", "GeoJSON", "CSV", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084540/fileData.do",
        description="국립공원 탐방로 LineString/MultiLineString 공간데이터.",
        geometry_type="LineString",
        feature_kind="route",
        update_cycle="quarterly",
    ),
    FileDataset(
        key="knps_visitor_centers",
        title="국립공원공단_국립공원 탐방안내소 공간데이터",
        data_go_id="15084541",
        categories=("facility", "spatial"),
        formats=("SHP", "GeoJSON", "CSV", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084541/fileData.do",
        description="탐방안내소 point 공간데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="semiannual",
    ),
    FileDataset(
        key="knps_hazard_zones",
        title="국립공원공단_국립공원 위험지역 공간데이터",
        data_go_id="15084542",
        categories=("safety", "spatial"),
        formats=("SHP", "GeoJSON", "CSV", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084542/fileData.do",
        description="낙석, 추락, 급류 등 위험지역 polygon 공간데이터.",
        geometry_type="Polygon",
        feature_kind="area",
        update_cycle="monthly",
    ),
    FileDataset(
        key="knps_weather_stations",
        title="국립공원공단_국립공원 기상관측시설 현황",
        data_go_id="15084543",
        categories=("weather", "spatial"),
        formats=("CSV", "SHP", "GeoJSON", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084543/fileData.do",
        description="국립공원 기상관측시설 point 메타데이터.",
        geometry_type="Point",
        feature_kind="weather",
        update_cycle="yearly",
    ),
    FileDataset(
        key="knps_restrooms",
        title="국립공원공단_국립공원 화장실 공간데이터",
        data_go_id="15084544",
        categories=("facility", "spatial"),
        formats=("SHP", "GeoJSON", "CSV", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084544/fileData.do",
        description="국립공원 화장실 point 공간데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="semiannual",
    ),
    FileDataset(
        key="knps_cultural_resources",
        title="국립공원공단_국립공원 문화자원 공간데이터",
        data_go_id="15084545",
        categories=("park", "spatial"),
        formats=("SHP", "GeoJSON", "CSV", "ZIP"),
        detail_url=f"{DATA_GO_BASE}/15084545/fileData.do",
        description="사찰, 탑, 비석, 유적 등 문화자원 point 공간데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="yearly",
    ),
    FileDataset(
        key="knps_campgrounds",
        title="국립공원공단_국립공원 야영장 공간데이터",
        data_go_id="",
        categories=("facility", "spatial"),
        formats=("CSV", "SHP", "GeoJSON", "ZIP"),
        detail_url="https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=국립공원공단%20야영장%20공간데이터",
        description="국립공원 야영장 명칭, 주소, 전화번호, 야영동수, 이용좌표 후보 데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="quarterly",
        notes="공개 검색 snippet에서 존재가 확인되었고 상세 ID는 검증 필요.",
    ),
    FileDataset(
        key="knps_shelters",
        title="국립공원공단_국립공원 대피소 공간데이터",
        data_go_id="",
        categories=("facility", "safety", "spatial"),
        formats=("CSV", "SHP", "GeoJSON", "ZIP"),
        detail_url="https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=국립공원공단%20대피소%20공간데이터",
        description="국립공원 대피소/산장 point 공간데이터 후보.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="yearly",
        verification_status="planned",
    ),
    FileDataset(
        key="knps_recommended_courses",
        title="국립공원공단_국립공원 추천 탐방코스",
        data_go_id="",
        categories=("trail", "spatial"),
        formats=("CSV", "GeoJSON", "SHP", "ZIP"),
        detail_url="https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=국립공원공단%20추천%20탐방코스",
        description="난이도별 추천 탐방코스 route 후보 데이터.",
        geometry_type="LineString",
        feature_kind="route",
        update_cycle="quarterly",
        verification_status="planned",
    ),
    FileDataset(
        key="knps_park_photos",
        title="국립공원공단_국립공원 명소 사진/VR",
        data_go_id="",
        categories=("media", "park"),
        formats=("CSV", "JPG", "URL"),
        detail_url="https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=국립공원공단%20사진%20360%20VR",
        description="feature 본문이 아니라 source_links/media 파일로 연결할 후보 데이터.",
        feature_kind=None,
        update_cycle="irregular",
        verification_status="planned",
    ),
    FileDataset(
        key="knps_visitor_statistics",
        title="국립공원공단_국립공원 탐방객 통계",
        data_go_id="15107577",
        categories=("statistics", "park"),
        formats=("CSV", "XLSX"),
        detail_url=f"{DATA_GO_BASE}/15107577/fileData.do",
        description="국립공원별 월별 탐방객 통계.",
        feature_kind=None,
        update_cycle="monthly",
    ),
)


def api_endpoints(category: str | None = None) -> tuple[ApiEndpoint, ...]:
    """정리된 API endpoint 목록을 반환한다."""

    if category is None:
        return API_ENDPOINTS
    return tuple(endpoint for endpoint in API_ENDPOINTS if category in endpoint.categories)


def api_endpoint(key: str) -> ApiEndpoint:
    """endpoint key로 API endpoint를 찾는다."""

    for endpoint in API_ENDPOINTS:
        if endpoint.key == key:
            return endpoint
    raise KeyError(f"unknown KNPS API endpoint: {key}")


def file_datasets(category: str | None = None) -> tuple[FileDataset, ...]:
    """정리된 파일데이터 목록을 반환한다."""

    if category is None:
        return FILE_DATASETS
    return tuple(dataset for dataset in FILE_DATASETS if category in dataset.categories)


def file_dataset(key: str) -> FileDataset:
    """dataset key 또는 data.go.kr ID로 파일데이터를 찾는다."""

    for dataset in FILE_DATASETS:
        if dataset.key == key or (dataset.data_go_id and dataset.data_go_id == key):
            return dataset
    raise KeyError(f"unknown KNPS file dataset: {key}")


def catalog_entries(category: str | None = None) -> tuple[CatalogEntry, ...]:
    """API와 파일데이터를 합친 human-readable catalog를 반환한다."""

    entries: list[CatalogEntry] = []
    for endpoint in api_endpoints(category):
        entries.append(
            CatalogEntry(
                kind="api",
                key=endpoint.key,
                display_name=f"[API] {endpoint.title}",
                dataset_id=endpoint.data_go_id,
                dataset_name=endpoint.title,
                categories=endpoint.categories,
                provider=endpoint.provider,
                description=endpoint.description,
                detail_url=endpoint.detail_url,
                service=endpoint.service,
                operation=endpoint.operation,
                url=endpoint.url,
                service_key_param=endpoint.service_key_param,
                response_format=endpoint.response_format,
                response_type_param=endpoint.response_type_param,
                verification_status=endpoint.verification_status,
            )
        )
    for dataset in file_datasets(category):
        entries.append(
            CatalogEntry(
                kind="file_dataset",
                key=dataset.key,
                display_name=f"[FILE] {dataset.title}",
                dataset_id=dataset.data_go_id,
                dataset_name=dataset.title,
                categories=dataset.categories,
                provider=dataset.provider,
                description=dataset.description,
                detail_url=dataset.detail_url,
                formats=dataset.formats,
                url=dataset.download_url,
                verification_status=dataset.verification_status,
            )
        )
    return tuple(entries)


def catalog_entry(key: str) -> CatalogEntry:
    """catalog key로 항목을 찾는다."""

    for entry in catalog_entries():
        if entry.key == key or (entry.dataset_id and entry.dataset_id == key):
            return entry
    raise KeyError(f"unknown KNPS catalog entry: {key}")


def category_names() -> tuple[Category, ...]:
    """현재 catalog에서 사용하는 category 이름을 반환한다."""

    values = {category for entry in catalog_entries() for category in entry.categories}
    return tuple(sorted(values))
