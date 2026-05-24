"""knps가 반환하는 Pydantic 모델."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field

RawRecord: TypeAlias = Mapping[str, Any]
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
CatalogKind: TypeAlias = Literal["api", "file_dataset"]
VerificationStatus: TypeAlias = Literal["verified", "needs_verification", "planned"]
T = TypeVar("T")


class KnpsModel(BaseModel):
    """불변 공개 객체의 기반 모델."""

    model_config = ConfigDict(frozen=True)


class CallContext(KnpsModel):
    """응답을 만든 원격 호출의 메타데이터."""

    provider: str | None = None
    endpoint: str | None = None
    request_url: str | None = None
    request_params: RawRecord = Field(default_factory=dict)
    collected_at: datetime | None = None


class Page(KnpsModel, Generic[T]):
    """페이지네이션 API 응답."""

    items: tuple[T, ...]
    total_count: int
    page_no: int
    num_of_rows: int
    raw: RawRecord = Field(repr=False)
    header: RawRecord = Field(default_factory=dict)
    context: CallContext = Field(default_factory=CallContext)

    @property
    def is_empty(self) -> bool:
        return not self.items

    @property
    def has_next_page(self) -> bool:
        if self.num_of_rows <= 0:
            return False
        return self.page_no * self.num_of_rows < self.total_count

    @property
    def next_page_no(self) -> int | None:
        if not self.has_next_page:
            return None
        return self.page_no + 1


class ApiEndpoint(KnpsModel):
    """정리된 KNPS API endpoint 메타데이터."""

    key: str
    title: str
    data_go_id: str
    categories: tuple[Category, ...]
    provider: Provider
    service: str
    operation: str
    url: str
    detail_url: str
    description: str
    notes: str | None = None
    service_key_param: str = "serviceKey"
    response_format: str | None = None
    response_type_param: str | None = "_type"
    verification_status: VerificationStatus = "needs_verification"


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
    service: str | None = None
    operation: str | None = None
    url: str | None = None
    formats: tuple[str, ...] = ()
    service_key_param: str | None = None
    response_format: str | None = None
    response_type_param: str | None = None
    verification_status: VerificationStatus = "needs_verification"
