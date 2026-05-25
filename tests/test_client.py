from knps import KnpsClient


async def test_client_exposes_file_dataset_catalog_only() -> None:
    client = KnpsClient()
    try:
        keys = {dataset.key for dataset in client.file_datasets()}
        catalog_kinds = {entry.kind for entry in client.catalog()}
    finally:
        await client.aclose()

    assert "knps_visitor_statistics" in keys
    assert catalog_kinds == {"file_dataset"}
    assert not hasattr(client, "endpoints")
    assert not hasattr(client, "raw_endpoint")
