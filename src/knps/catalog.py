"""국립공원공단 공개 데이터 카탈로그."""

from __future__ import annotations

from .models import ApiEndpoint, CatalogEntry, Category, FileDataset

DATA_GO_BASE = "https://www.data.go.kr/data"


API_ENDPOINTS: tuple[ApiEndpoint, ...] = ()


FILE_DATASETS: tuple[FileDataset, ...] = (
    FileDataset(
        key="knps_park_boundaries",
        title="국립공원공단_국립공원 공원경계_20231231",
        data_go_id="15017313",
        categories=("park", "spatial"),
        formats=("SHP",),
        detail_url=f"{DATA_GO_BASE}/15017313/fileData.do",
        description="국립공원 경계 polygon 공간데이터.",
        geometry_type="MultiPolygon",
        feature_kind="area",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_trails",
        title="국립공원공단_국립공원 탐방로 공간데이터_20170928",
        data_go_id="15003467",
        categories=("trail", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15003467/fileData.do",
        description="국립공원 탐방로 LineString/MultiLineString 공간데이터.",
        geometry_type="LineString",
        feature_kind="route",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_visitor_centers",
        title="국립공원공단_국립공원 탐방안내소 공간데이터_20141219",
        data_go_id="15003445",
        categories=("facility", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15003445/fileData.do",
        description="탐방안내소 point 공간데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_hazard_zones",
        title="국립공원공단_국립공원 위험지역 공간데이터_20180816",
        data_go_id="15003441",
        categories=("safety", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15003441/fileData.do",
        description="낙석, 추락, 급류 등 위험지역 polygon 공간데이터.",
        geometry_type="Polygon",
        feature_kind="area",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_weather_stations",
        title="국립공원공단_통합방재시스템_기상관측장비_20210928",
        data_go_id="15090557",
        categories=("weather", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15090557/fileData.do",
        description="국립공원 기상관측시설 point 메타데이터.",
        geometry_type="Point",
        feature_kind="weather",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_restrooms",
        title="국립공원공단_국립공원 화장실 공간데이터_20141219",
        data_go_id="15003468",
        categories=("facility", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15003468/fileData.do",
        description="국립공원 화장실 point 공간데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_cultural_resources",
        title="국립공원공단_국립공원 문화자원 공간데이터_20141219",
        data_go_id="15003443",
        categories=("park", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15003443/fileData.do",
        description="사찰, 탑, 비석, 유적 등 문화자원 point 공간데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_campgrounds",
        title="국립공원공단_국립공원 야영장 공간데이터_20141219",
        data_go_id="15003469",
        categories=("facility", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15003469/fileData.do",
        description="국립공원 야영장 명칭, 주소, 전화번호, 야영동수, 이용좌표 후보 데이터.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_shelters",
        title="국립공원공단_국립공원 대피소_20131102",
        data_go_id="2982556",
        categories=("facility", "safety", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/2982556/fileData.do",
        description="국립공원 대피소/산장 point 공간데이터 후보.",
        geometry_type="Point",
        feature_kind="place",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_linear_facilities",
        title="국립공원공단_국립공원 선형시설_20181231",
        data_go_id="15091972",
        categories=("facility", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15091972/fileData.do",
        description="국립공원 선형시설 데이터.",
        geometry_type="LineString",
        feature_kind="route",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_basic_statistics",
        title="국립공원공단_국립공원기본통계2020",
        data_go_id="15087598",
        categories=("statistics", "park"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15087598/fileData.do",
        description="국립공원 기본통계 데이터.",
        feature_kind=None,
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_visitor_statistics",
        title="국립공원공단_국립공원 시간별 일별 탐방객 통계",
        data_go_id="15107577",
        categories=("statistics", "park"),
        formats=("CSV", "XLSX"),
        detail_url=f"{DATA_GO_BASE}/15107577/fileData.do",
        description="국립공원별 월별 탐방객 통계.",
        feature_kind=None,
        update_cycle="monthly",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_protected_areas",
        title="국립공원공단_한국보호지역 데이터_20161231",
        data_go_id="15127921",
        categories=("park", "spatial"),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15127921/fileData.do",
        description="한국보호지역 데이터.",
        geometry_type="Polygon",
        feature_kind="area",
        update_cycle="irregular",
        verification_status="verified",
    ),
    FileDataset(
        key="knps_lod_table_catalog",
        title="국립공원공단_LOD 공간데이터 테이블 목록",
        data_go_id="15118945",
        categories=("spatial",),
        formats=("CSV",),
        detail_url=f"{DATA_GO_BASE}/15118945/fileData.do",
        description="KNPS LOD 공간데이터 테이블 목록.",
        feature_kind=None,
        update_cycle="irregular",
        verification_status="verified",
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
