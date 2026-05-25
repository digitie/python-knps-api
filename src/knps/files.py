"""KNPS 파일데이터 helper."""

from __future__ import annotations

from typing import Protocol, cast

from .artifacts import read_file_artifact
from .catalog import file_dataset, file_datasets
from .exceptions import KnpsRequestError
from .models import FileArtifact, FileDataset


class _DownloadHttp(Protocol):
    async def get_bytes(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        provider: str = "data.go.kr",
        endpoint: str | None = None,
    ) -> bytes: ...


class _FileClient(Protocol):
    _http: _DownloadHttp


class FileDataNamespace:
    """파일데이터 catalog와 다운로드 primitive."""

    def __init__(self, client: object) -> None:
        self._client = cast(_FileClient, client)

    def datasets(self, category: str | None = None) -> tuple[FileDataset, ...]:
        """정리된 파일데이터 목록을 반환한다."""

        return file_datasets(category)

    def dataset(self, key: str) -> FileDataset:
        """파일데이터 key 또는 data.go.kr ID로 catalog 항목을 반환한다."""

        return file_dataset(key)

    async def download(self, key: str, *, max_bytes: int | None = None) -> bytes:
        """검증된 직접 다운로드 URL에서 파일 bytes를 가져온다."""

        dataset = file_dataset(key)
        if not dataset.download_url:
            raise KnpsRequestError(
                f"download_url is not verified for dataset {dataset.key}",
                provider=dataset.provider,
                endpoint=dataset.key,
                failure_kind="catalog",
            )
        http = self._client._http
        return await http.get_bytes(
            dataset.download_url,
            max_bytes=max_bytes,
            provider=dataset.provider,
            endpoint=dataset.key,
        )

    def inspect_bytes(
        self,
        key: str,
        data: bytes,
        *,
        preview_rows: int = 5,
    ) -> FileArtifact:
        """다운로드 bytes를 파일 구조/CSV preview DTO로 변환한다."""

        return read_file_artifact(
            file_dataset(key),
            data,
            preview_rows=preview_rows,
        )

    async def download_artifact(
        self,
        key: str,
        *,
        preview_rows: int = 5,
    ) -> FileArtifact:
        """파일을 다운로드한 뒤 Pydantic DTO로 읽는다."""

        data = await self.download(key)
        return self.inspect_bytes(key, data, preview_rows=preview_rows)
