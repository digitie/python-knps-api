"""국립공원공단 공개 데이터 카탈로그."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .exceptions import KnpsRequestError
from .geometry import WGS84
from .models import CatalogEntry, Category, FileDataset

DATA_GO_BASE = "https://www.data.go.kr/data"
DATA_GO_DOWNLOAD_BASE = "https://www.data.go.kr/cmm/cmm/fileDownload.do"

OperationParamKind = Literal["str", "int", "bool"]

_POINT_GEOMETRY_TYPES = frozenset({"Point", "MultiPoint"})


def _download_url(file_id: str) -> str:
    return f"{DATA_GO_DOWNLOAD_BASE}?atchFileId={file_id}&fileDetailSn=1&insertDataPrcus=N"


@dataclass(frozen=True, slots=True)
class OperationParam:
    """디버그 UI가 오퍼레이션 위젯을 자동 생성하기 위한 파라미터 명세.

    ``default``가 ``{dataset_key}`` 토큰을 포함하면 호출부가 선택된
    dataset의 key로 채워 넣는다(예: ``download_to_rustfs``의 ``local_path``).
    """

    name: str
    kind: OperationParamKind
    required: bool = False
    default: str = ""
    help: str = ""


@dataclass(frozen=True, slots=True)
class DatasetOperation:
    """``KnpsClient.files``의 실제 메서드 하나에 대응하는 디버그 UI 오퍼레이션.

    ``key``는 항상 :class:`~knps.files.FileDataNamespace`의 메서드 이름과
    같다 — 디버그 UI는 이 값으로 ``getattr(client.files, key)``를 호출해서
    라우팅하므로, 데이터셋/오퍼레이션 이름별 ``if`` 분기가 필요 없다.
    """

    key: str
    label: str
    description: str
    params: tuple[OperationParam, ...] = ()


def dataset_operations(dataset: FileDataset) -> tuple[DatasetOperation, ...]:
    """이 dataset에 실행 가능한 :class:`DatasetOperation` 목록을 반환한다.

    검증된 ``download_url``이 없으면(``needs_verification`` 등) 빈 tuple을
    돌려준다 — ADR-002에 따라 미검증 dataset은 다운로드를 시도하지 않는다.
    나머지는 ``geometry_type`` 유무로 spatial 전용 오퍼레이션을 켠다.
    """

    if not dataset.direct_download or not dataset.download_url:
        return ()

    operations: list[DatasetOperation] = [
        DatasetOperation(
            key="download_artifact",
            label="Download + inspect (raw bytes, CSV/ZIP preview)",
            description="파일을 다운로드하고 구조(ZIP member/CSV header)와 앞부분 행을 미리본다.",
            params=(
                OperationParam(
                    "preview_rows",
                    "int",
                    default="5",
                    help="CSV preview에 포함할 행 수.",
                ),
                OperationParam(
                    "max_bytes",
                    "int",
                    help="다운로드를 자를 최대 byte 수(선택, 비우면 전체 다운로드).",
                ),
            ),
        ),
    ]

    if dataset.geometry_type is not None:
        operations.append(
            DatasetOperation(
                key="download_geometries",
                label="Extract geometries (GeoFeatureCollection)",
                description="SHP/CSV에서 geometry feature를 추출한다(선택적으로 좌표 재투영).",
                params=(
                    OperationParam(
                        "source_crs",
                        "str",
                        help="원본 좌표계 EPSG 코드(선택, 예: EPSG:5179). 비우면 .prj에서 감지.",
                    ),
                    OperationParam(
                        "target_crs",
                        "str",
                        default=WGS84,
                        help="목표 좌표계(기본 WGS84).",
                    ),
                    OperationParam(
                        "max_features",
                        "int",
                        help="추출할 최대 feature 수(선택).",
                    ),
                    OperationParam(
                        "max_bytes",
                        "int",
                        help="다운로드를 자를 최대 byte 수(선택).",
                    ),
                ),
            )
        )
        operations.append(
            DatasetOperation(
                key="read_geo_records",
                label="Normalize to KnpsGeoRecord rows",
                description="geometry feature를 WKT + 정규화 속성의 typed record로 변환한다.",
                params=(
                    OperationParam(
                        "source_crs",
                        "str",
                        help="원본 좌표계 EPSG 코드(선택, 예: EPSG:5179).",
                    ),
                    OperationParam(
                        "target_crs",
                        "str",
                        default=WGS84,
                        help="목표 좌표계(기본 WGS84).",
                    ),
                    OperationParam(
                        "max_features",
                        "int",
                        help="추출할 최대 feature 수(선택).",
                    ),
                    OperationParam(
                        "max_bytes",
                        "int",
                        help="다운로드를 자를 최대 byte 수(선택).",
                    ),
                ),
            )
        )
        if dataset.geometry_type in _POINT_GEOMETRY_TYPES:
            operations.append(
                DatasetOperation(
                    key="read_place_records",
                    label="Normalize to KnpsPlaceRecord rows",
                    description="point CSV 전체 행을 typed KnpsPlaceRecord로 정규화한다.",
                    params=(
                        OperationParam(
                            "max_bytes",
                            "int",
                            help="다운로드를 자를 최대 byte 수(선택).",
                        ),
                    ),
                )
            )

    operations.append(
        DatasetOperation(
            key="download_to_rustfs",
            label="Download + save to local file & RustFS",
            description="파일을 다운로드해 로컬에 저장하고 동시에 RustFS(S3 호환)에 업로드한다.",
            params=(
                OperationParam(
                    "local_path",
                    "str",
                    required=True,
                    default="tests/fixtures/downloads/{dataset_key}.download",
                    help="로컬 저장 경로.",
                ),
                OperationParam(
                    "object_key",
                    "str",
                    help="RustFS object key(선택, 비우면 URL 파일명에서 자동 생성).",
                ),
                OperationParam(
                    "overwrite_local",
                    "bool",
                    default="true",
                    help="로컬 파일이 이미 있으면 덮어쓴다.",
                ),
                OperationParam(
                    "max_bytes",
                    "int",
                    help="다운로드를 자를 최대 byte 수(선택).",
                ),
            ),
        )
    )
    return tuple(operations)


FILE_DATASETS: tuple[FileDataset, ...] = (
    FileDataset(
        key="knps_park_boundaries",
        title="국립공원공단_국립공원 공원경계_20231231",
        data_go_id="15017313",
        categories=("park", "spatial"),
        formats=("SHP",),
        detail_url=f"{DATA_GO_BASE}/15017313/fileData.do",
        description="국립공원 경계 polygon 공간데이터.",
        direct_download=True,
        download_url=_download_url("FILE_000000003536231"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002823639"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002575152"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002843111"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002579150"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002575038"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002592399"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002575144"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000000377005"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002456374"),
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
        verification_status="needs_verification",
        notes="2026-05-25 live check에서 직접 다운로드 URL을 확인하지 못했다.",
    ),
    FileDataset(
        key="knps_visitor_statistics",
        title="국립공원공단_국립공원 시간별 일별 탐방객 통계",
        data_go_id="15107577",
        categories=("statistics", "park"),
        formats=("CSV", "XLSX"),
        detail_url=f"{DATA_GO_BASE}/15107577/fileData.do",
        description="국립공원별 월별 탐방객 통계.",
        direct_download=True,
        download_url=_download_url("FILE_000000003643932"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002908040"),
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
        direct_download=True,
        download_url=_download_url("FILE_000000002793370"),
        feature_kind=None,
        update_cycle="irregular",
        verification_status="verified",
    ),
)


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
    raise KnpsRequestError(
        f"unknown KNPS file dataset: {key}",
        provider="data.go.kr",
        endpoint=key,
        failure_kind="unknown_dataset",
    )


def catalog_entries(category: str | None = None) -> tuple[CatalogEntry, ...]:
    """파일데이터 human-readable catalog를 반환한다."""

    entries: list[CatalogEntry] = []
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
    raise KnpsRequestError(
        f"unknown KNPS catalog entry: {key}",
        provider="data.go.kr",
        endpoint=key,
        failure_kind="unknown_dataset",
    )


def category_names() -> tuple[Category, ...]:
    """현재 catalog에서 사용하는 category 이름을 반환한다."""

    values = {category for entry in catalog_entries() for category in entry.categories}
    return tuple(sorted(values))
