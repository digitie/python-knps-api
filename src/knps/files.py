"""KNPS 파일데이터 helper."""

from __future__ import annotations

import asyncio
import os
import urllib.parse
from pathlib import Path
from typing import Protocol, cast

import boto3

from .artifacts import read_file_artifact
from .catalog import file_dataset, file_datasets
from .config import KnpsConfig
from .exceptions import KnpsRequestError, KnpsStorageError
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
    config: KnpsConfig


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

        SHP(``pyshp``)와 좌표 재투영(``pyproj``)은 선택 의존성(``geo`` extra)이다.
        ``source_crs``가 주어지거나 shapefile ``.prj``에서 감지되고 ``target_crs``와
        다르면 좌표를 재투영한다.
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

    async def download_to_rustfs(
        self,
        key: str,
        local_path: str | Path,
        *,
        object_key: str | None = None,
        overwrite_local: bool = True,
        max_bytes: int | None = None,
    ) -> str:
        """검증된 직접 다운로드 URL에서 파일 bytes를 다운로드하여 로컬에 저장하고,
        S3 호환 객체 저장소(RustFS)에도 동시에 저장합니다.

        S3(RustFS) 업로드 성공 후 최종 저장된 object_key를 반환합니다.
        """
        # 1. 데이터셋 다운로드
        dataset = file_dataset(key)
        data = await self._fetch_dataset_bytes(dataset, max_bytes=max_bytes)

        # 2. 로컬 저장
        path = Path(local_path)
        if path.exists() and not overwrite_local:
            raise KnpsStorageError(
                f"Local file already exists at {path} and overwrite_local is False",
                provider="local",
                endpoint=key,
                failure_kind="local_write",
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(path.write_bytes, data)
        except Exception as exc:
            raise KnpsStorageError(
                f"Failed to write local file at {path}: {exc}",
                provider="local",
                endpoint=key,
                failure_kind="local_write",
            ) from exc

        # 3. RustFS(S3) 설정 확인 및 클라이언트 초기화
        config = self._client.config
        if not config.rustfs_endpoint_url:
            raise KnpsStorageError(
                "RustFS endpoint URL is not configured.",
                provider="rustfs",
                endpoint=key,
                failure_kind="config",
            )

        try:
            s3_client = boto3.client(
                "s3",
                endpoint_url=config.rustfs_endpoint_url,
                aws_access_key_id=config.rustfs_access_key,
                aws_secret_access_key=config.rustfs_secret_key,
                region_name=config.rustfs_region,
            )
        except Exception as exc:
            raise KnpsStorageError(
                f"Failed to initialize boto3 S3 client: {exc}",
                provider="rustfs",
                endpoint=key,
                failure_kind="client_init",
            ) from exc

        # 4. object_key 결정
        if not object_key:
            parsed = urllib.parse.urlparse(dataset.download_url or "")
            filename = os.path.basename(parsed.path)
            if not filename:
                filename = f"{key}.dat"
            object_key = f"datasets/{key}/{filename}"

        # 5. RustFS(S3) 업로드
        try:
            import mimetypes

            content_type, _ = mimetypes.guess_type(object_key)
            if not content_type:
                content_type = "application/octet-stream"

            await asyncio.to_thread(
                s3_client.put_object,
                Bucket=config.rustfs_bucket or "knps",
                Key=object_key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:
            raise KnpsStorageError(
                f"Failed to upload data to RustFS (bucket: {config.rustfs_bucket}, "
                f"key: {object_key}): {exc}",
                provider="rustfs",
                endpoint=key,
                failure_kind="upload",
            ) from exc

        return object_key
