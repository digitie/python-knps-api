import pytest

from knps import KnpsClient


@pytest.mark.live
async def test_live_keyless_download_reads_pydantic_artifact() -> None:
    async with KnpsClient(timeout=60) as client:
        artifact = await client.files.download_artifact("knps_lod_table_catalog", preview_rows=2)

    assert artifact.kind == "csv"
    assert artifact.size_bytes > 0
    assert artifact.csv_previews
    assert artifact.csv_previews[0].headers[:4] == ("테이블명", "컬럼명", "데이터타입", "참조형식")
    assert artifact.csv_previews[0].rows
