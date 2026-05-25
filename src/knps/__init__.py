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
)
from .models import CatalogEntry, CsvPreview, CsvPreviewRow, FileArtifact, FileDataset, FileMember

PROVIDER_NAME = "python-knps-api"

__all__ = [
    "PROVIDER_NAME",
    "CatalogEntry",
    "CsvPreview",
    "CsvPreviewRow",
    "FileArtifact",
    "FileDataset",
    "FileMember",
    "KnpsApiError",
    "KnpsAuthError",
    "KnpsClient",
    "KnpsConfig",
    "KnpsNoDataError",
    "KnpsParseError",
    "KnpsRateLimitError",
    "KnpsRequestError",
    "KnpsServerError",
    "catalog_entries",
    "file_dataset",
    "file_datasets",
]
