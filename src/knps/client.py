"""사용자용 국립공원공단 공개데이터 비동기 클라이언트."""

from __future__ import annotations

from types import TracebackType
from typing import Any

from ._http import AsyncSessionLike, KnpsHttp
from .catalog import catalog_entries
from .config import KnpsConfig
from .files import FileDataNamespace
from .models import CatalogEntry, FileDataset


class KnpsClient:
    """KNPS 공공데이터 비동기 facade."""

    def __init__(
        self,
        *,
        timeout: float | str | None = None,
        max_rps: float | str | None = None,
        session: AsyncSessionLike | None = None,
    ) -> None:
        self.config = KnpsConfig.from_env(
            timeout=timeout,
            max_rps=max_rps,
        )
        self.timeout = self.config.timeout
        self._http = KnpsHttp(
            timeout=self.timeout,
            session=session,
            max_rps=self.config.max_rps,
        )
        self.files = FileDataNamespace(self)
        self.closed = False

    @classmethod
    def from_env(cls, **kwargs: Any) -> KnpsClient:
        """``KnpsClient(...)``의 호환성 alias.

        과거 API에서는 ``DATA_GO_KR_SERVICE_KEY`` 등을 환경 변수로 읽었다.
        keyless 파일 다운로드만 남으면서 이 메서드는 단순히 인자를 그대로
        ``__init__``에 전달한다. 새 코드에서는 ``KnpsClient(...)``를 직접
        호출하는 것을 권장한다.
        """

        return cls(**kwargs)

    @classmethod
    def aio(cls, **kwargs: Any) -> KnpsClient:
        """비동기 클라이언트 생성자."""

        return cls(**kwargs)

    async def __aenter__(self) -> KnpsClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self.closed = True

    def file_datasets(self, category: str | None = None) -> tuple[FileDataset, ...]:
        """정리된 파일데이터 메타데이터를 반환한다."""

        return self.files.datasets(category)

    def catalog(self, category: str | None = None) -> tuple[CatalogEntry, ...]:
        """디버그 UI와 선택 목록에서 쓰는 human-readable 카탈로그를 반환한다."""

        return catalog_entries(category)
