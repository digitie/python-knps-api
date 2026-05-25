import pytest

from knps import KnpsClient
from knps.catalog import file_datasets

# 2026-05-25 live check에서 직접 다운로드 URL이 검증된 13개 dataset.
# catalog의 ``direct_download=True``와 1:1 매칭되어야 한다.
KEYLESS_DATASET_KEYS = tuple(
    dataset.key for dataset in file_datasets() if dataset.direct_download
)


@pytest.mark.live
async def test_live_keyless_download_reads_pydantic_artifact() -> None:
    async with KnpsClient(timeout=60) as client:
        artifact = await client.files.download_artifact("knps_lod_table_catalog", preview_rows=2)

    assert artifact.kind == "csv"
    assert artifact.size_bytes > 0
    assert artifact.csv_previews
    assert artifact.csv_previews[0].headers[:4] == ("테이블명", "컬럼명", "데이터타입", "참조형식")
    assert artifact.csv_previews[0].rows


@pytest.mark.live
@pytest.mark.parametrize("dataset_key", KEYLESS_DATASET_KEYS)
async def test_live_every_keyless_url_returns_artifact(dataset_key: str) -> None:
    """검증된 13개 keyless URL 모두 실제로 bytes를 돌려주고 DTO로 읽힌다."""

    async with KnpsClient(timeout=120) as client:
        artifact = await client.files.download_artifact(dataset_key, preview_rows=1)

    assert artifact.size_bytes > 0, f"{dataset_key} returned empty body"
    assert artifact.kind in {"zip", "csv", "binary"}
    assert artifact.dataset_key == dataset_key
