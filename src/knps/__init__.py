"""국립공원공단(KNPS) 공개데이터 비공식 client."""

from __future__ import annotations

from .catalog import (
    DatasetOperation,
    OperationParam,
    catalog_entries,
    dataset_operations,
    file_dataset,
    file_datasets,
)
from .client import KnpsClient
from .config import KnpsConfig
from .debug import (
    DEFAULT_ASSERTION,
    SENSITIVE_KEYS,
    DebugRun,
    arun_dataset_operation,
    debug_error,
    jsonable,
    redact_sensitive,
    resolve_operation_kwargs,
    run_dataset_operation,
    save_fixture,
    slugify_case_name,
)
from .exceptions import (
    KnpsApiError,
    KnpsAuthError,
    KnpsParseError,
    KnpsRateLimitError,
    KnpsRequestError,
    KnpsServerError,
    KnpsStorageError,
)
from .geometry import extract_geometries, parse_wkt
from .models import (
    CatalogEntry,
    CsvPreview,
    CsvPreviewRow,
    FileArtifact,
    FileDataset,
    FileMember,
    GeoFeature,
    GeoFeatureCollection,
    Geometry,
    KnpsGeoRecord,
    KnpsPlaceRecord,
)
from .records import (
    geometry_to_wkt,
    normalize_geo_record,
    normalize_place_record,
    representative_point,
)

PROVIDER_NAME = "python-knps-api"

__all__ = [
    "PROVIDER_NAME",
    "DEFAULT_ASSERTION",
    "SENSITIVE_KEYS",
    "CatalogEntry",
    "CsvPreview",
    "CsvPreviewRow",
    "DatasetOperation",
    "DebugRun",
    "FileArtifact",
    "FileDataset",
    "FileMember",
    "GeoFeature",
    "GeoFeatureCollection",
    "Geometry",
    "KnpsApiError",
    "KnpsAuthError",
    "KnpsClient",
    "KnpsConfig",
    "KnpsGeoRecord",
    "KnpsParseError",
    "KnpsPlaceRecord",
    "KnpsRateLimitError",
    "KnpsRequestError",
    "KnpsServerError",
    "KnpsStorageError",
    "OperationParam",
    "arun_dataset_operation",
    "catalog_entries",
    "dataset_operations",
    "debug_error",
    "extract_geometries",
    "file_dataset",
    "file_datasets",
    "geometry_to_wkt",
    "jsonable",
    "normalize_geo_record",
    "normalize_place_record",
    "parse_wkt",
    "redact_sensitive",
    "representative_point",
    "resolve_operation_kwargs",
    "run_dataset_operation",
    "save_fixture",
    "slugify_case_name",
]
