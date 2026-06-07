from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from knps import KnpsClient, KnpsStorageError


@pytest.fixture
def mock_s3() -> MagicMock:
    with patch("boto3.client") as mock_client:
        s3_instance = MagicMock()
        mock_client.return_value = s3_instance
        yield s3_instance


async def test_download_to_rustfs_success(tmp_path, mock_s3) -> None:
    # Arrange
    local_file = tmp_path / "test_output.csv"
    mock_bytes = b"mock file data content"

    # KnpsClient의 _fetch_dataset_bytes를 가로채기 위해 mock
    client = KnpsClient(
        timeout=5,
        max_rps=2,
    )
    # env를 강제로 주입하여 config 로드
    client.config = client.config.from_env(
        rustfs_endpoint_url="http://localhost:9000",
        rustfs_bucket="test-bucket",
        rustfs_access_key="access",
        rustfs_secret_key="secret",
    )

    with patch.object(
        client.files, "_fetch_dataset_bytes", AsyncMock(return_value=mock_bytes)
    ):
        # Act
        object_key = await client.files.download_to_rustfs(
            "knps_lod_table_catalog",
            local_file,
            object_key="features/test_catalog.csv",
        )

        # Assert
        assert object_key == "features/test_catalog.csv"
        # 1) 로컬 파일 쓰기 검증
        assert local_file.exists()
        assert local_file.read_bytes() == mock_bytes

        # 2) S3 업로드 검증
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="features/test_catalog.csv",
            Body=mock_bytes,
            ContentType=ANY,
        )


async def test_download_to_rustfs_missing_config(tmp_path, mock_s3) -> None:
    local_file = tmp_path / "test_output.csv"
    client = KnpsClient()
    # config의 endpoint_url을 None으로 설정
    client.config = client.config.from_env(rustfs_endpoint_url="")

    with patch.object(
        client.files, "_fetch_dataset_bytes", AsyncMock(return_value=b"data")
    ):
        with pytest.raises(KnpsStorageError) as exc_info:
            await client.files.download_to_rustfs(
                "knps_lod_table_catalog",
                local_file,
            )

        assert "RustFS endpoint URL is not configured" in str(exc_info.value)
        # 설정이 비어있으면 로컬 파일도 쓰기 전 혹은 그 단계에서 멈추어야 함
        # (또는 롤백되거나 예외 발생)
        # 현재 구현 상 로컬 저장은 수행되고 S3 설정 확인 시점에서 예외가 나므로
        # 로컬 파일은 생성되어 있음


async def test_download_to_rustfs_overwrite_false(tmp_path, mock_s3) -> None:
    local_file = tmp_path / "test_output.csv"
    local_file.write_bytes(b"existing data")
    client = KnpsClient()

    with patch.object(
        client.files, "_fetch_dataset_bytes", AsyncMock(return_value=b"new data")
    ):
        with pytest.raises(KnpsStorageError) as exc_info:
            await client.files.download_to_rustfs(
                "knps_lod_table_catalog",
                local_file,
                overwrite_local=False,
            )

        assert "Local file already exists" in str(exc_info.value)
        assert local_file.read_bytes() == b"existing data"  # 기존 데이터 유지됨


async def test_download_to_rustfs_upload_failure(tmp_path, mock_s3) -> None:
    local_file = tmp_path / "test_output.csv"
    mock_s3.put_object.side_effect = Exception("S3 Connection Lost")

    client = KnpsClient()
    client.config = client.config.from_env(
        rustfs_endpoint_url="http://localhost:9000",
        rustfs_bucket="test-bucket",
    )

    with patch.object(
        client.files, "_fetch_dataset_bytes", AsyncMock(return_value=b"data")
    ):
        with pytest.raises(KnpsStorageError) as exc_info:
            await client.files.download_to_rustfs(
                "knps_lod_table_catalog",
                local_file,
            )

        assert "Failed to upload data to RustFS" in str(exc_info.value)
        # 로컬 저장은 되었는지 확인
        assert local_file.exists()
        assert local_file.read_bytes() == b"data"
