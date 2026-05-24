"""국립공원공단(KNPS) 공개데이터 비공식 client."""

from __future__ import annotations

from .catalog import api_endpoint, api_endpoints, catalog_entries, file_dataset, file_datasets
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
)
from .models import ApiEndpoint, CatalogEntry, FileDataset, Page

PROVIDER_NAME = "python-knps-api"

__all__ = [
    "PROVIDER_NAME",
    "ApiEndpoint",
    "CatalogEntry",
    "FileDataset",
    "KnpsApiError",
    "KnpsAuthError",
    "KnpsClient",
    "KnpsConfig",
    "KnpsNoDataError",
    "KnpsParseError",
    "KnpsRateLimitError",
    "KnpsRequestError",
    "KnpsServerError",
    "Page",
    "api_endpoint",
    "api_endpoints",
    "catalog_entries",
    "file_dataset",
    "file_datasets",
]
