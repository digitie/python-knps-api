"""KNPS 파일데이터 helper."""

from __future__ import annotations

from typing import Protocol, cast

from .artifacts import read_file_artifact
from .catalog import file_dataset, file_datasets
from .exceptions import KnpsRequestError
from .geometry import WGS84, extract_geometries
from .models import FileArtifact, FileDataset, GeoFeatureCollection

_DEFAULT_PREVIEW_ROWS = 5


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

        return await self._fetch_dataset_bytes(file_dataset(key), max_bytes=max_bytes)

    async def _fetch_dataset_bytes(
        self,
        dataset: FileDataset,
        *,
        max_bytes: int | None = None,
    ) -> bytes:
        """이미 lookup된 ``FileDataset``에서 bytes를 가져오는 내부 helper."""

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
        preview_rows: int = _DEFAULT_PREVIEW_ROWS,
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
        preview_rows: int = _DEFAULT_PREVIEW_ROWS,
        max_bytes: int | None = None,
    ) -> FileArtifact:
        """파일을 다운로드한 뒤 Pydantic DTO로 읽는다.

        ``max_bytes``로 다운로드를 잘라낼 수 있다. ZIP/CSV가 잘리면 reader가
        ``binary``로 fallback하거나 partial preview만 반환할 수 있으니, 큰
        파일을 빠르게 살펴볼 때만 사용한다.

        ``download`` + ``inspect_bytes``를 따로 호출하면 catalog lookup이 두 번
        일어나는데, 이 메서드는 lookup을 한 번만 수행한다.
        """

        dataset = file_dataset(key)
        data = await self._fetch_dataset_bytes(dataset, max_bytes=max_bytes)
        return read_file_artifact(dataset, data, preview_rows=preview_rows)

    def extract_geometries(
        self,
        key: str,
        data: bytes,
        *,
        source_crs: str | None = None,
        target_crs: str | None = WGS84,
        max_features: int | None = None,
    ) -> GeoFeatureCollection:
        """다운로드 bytes에서 geometry feature를 추출한다.

        ZIP 안에 shapefile이 있으면 ``pyshp``로 읽고, 그 외에는 CSV의 WKT/위경도
        컬럼에서 geometry를 만든다. ``source_crs``가 주어지거나 shapefile
        ``.prj``에서 감지되고 ``target_crs``와 다르면 ``pyproj``로 재투영한다.
        """

        return extract_geometries(
            file_dataset(key),
            data,
            source_crs=source_crs,
            target_crs=target_crs,
            max_features=max_features,
        )

    async def download_geometries(
        self,
        key: str,
        *,
        source_crs: str | None = None,
        target_crs: str | None = WGS84,
        max_features: int | None = None,
        max_bytes: int | None = None,
    ) -> GeoFeatureCollection:
        """파일을 다운로드한 뒤 geometry feature로 추출한다.

        ``download`` + ``extract_geometries``를 따로 호출하는 것과 같지만 catalog
        lookup을 한 번만 수행한다.
        """

        dataset = file_dataset(key)
        data = await self._fetch_dataset_bytes(dataset, max_bytes=max_bytes)
        return extract_geometries(
            dataset,
            data,
            source_crs=source_crs,
            target_crs=target_crs,
            max_features=max_features,
        )
