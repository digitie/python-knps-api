"""국립공원공단(KNPS) 공개데이터 비공식 client."""

from __future__ import annotations

from .catalog import catalog_entries, file_dataset, file_datasets
from .client import KnpsClient
from .config import KnpsConfig
from .exceptions import (
    KnpsApiError,
    KnpsAuthError,
    KnpsNoDataError,
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
    "CatalogEntry",
    "CsvPreview",
    "CsvPreviewRow",
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
    "KnpsNoDataError",
    "KnpsParseError",
    "KnpsPlaceRecord",
    "KnpsRateLimitError",
    "KnpsRequestError",
    "KnpsServerError",
    "KnpsStorageError",
    "catalog_entries",
    "extract_geometries",
    "file_dataset",
    "file_datasets",
    "geometry_to_wkt",
    "normalize_geo_record",
    "normalize_place_record",
    "parse_wkt",
    "representative_point",
]
