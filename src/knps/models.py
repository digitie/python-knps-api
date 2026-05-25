"""knps가 반환하는 Pydantic 모델."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

Category: TypeAlias = Literal[
    "park",
    "trail",
    "facility",
    "safety",
    "weather",
    "media",
    "statistics",
    "spatial",
]
Provider: TypeAlias = Literal["data.go.kr", "knps.or.kr"]
CatalogKind: TypeAlias = Literal["file_dataset"]
VerificationStatus: TypeAlias = Literal["verified", "needs_verification", "planned"]


class KnpsModel(BaseModel):
    """불변 공개 객체의 기반 모델."""

    model_config = ConfigDict(frozen=True)


class FileDataset(KnpsModel):
    """정리된 KNPS 파일데이터 메타데이터."""

    key: str
    title: str
    data_go_id: str
    categories: tuple[Category, ...]
    formats: tuple[str, ...]
    detail_url: str
    description: str
    provider: Provider = "data.go.kr"
    direct_download: bool = False
    download_url: str | None = None
    geometry_type: str | None = None
    feature_kind: str | None = None
    update_cycle: str | None = None
    verification_status: VerificationStatus = "needs_verification"
    notes: str | None = None


class CatalogEntry(KnpsModel):
    """디버그 UI 표시와 선택에 쓰는 human-readable 카탈로그 항목."""

    kind: CatalogKind
    key: str
    display_name: str
    dataset_id: str
    dataset_name: str
    categories: tuple[Category, ...]
    provider: str
    description: str
    detail_url: str
    url: str | None = None
    formats: tuple[str, ...] = ()
    verification_status: VerificationStatus = "needs_verification"
