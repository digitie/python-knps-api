from knps import PROVIDER_NAME
from knps.catalog import api_endpoint, catalog_entries, file_dataset, file_datasets


def test_provider_name() -> None:
    assert PROVIDER_NAME == "python-knps-api"


def test_core_file_datasets_exist() -> None:
    keys = {dataset.key for dataset in file_datasets()}
    assert "knps_park_boundaries" in keys
    assert "knps_trails" in keys
    assert "knps_visitor_centers" in keys
    assert "knps_hazard_zones" in keys
    assert "knps_weather_stations" in keys
    assert "knps_restrooms" in keys
    assert "knps_cultural_resources" in keys


def test_lookup_by_key_and_id() -> None:
    by_key = file_dataset("knps_trails")
    by_id = file_dataset("15084540")
    assert by_key == by_id
    assert by_key.feature_kind == "route"


def test_catalog_entries_include_api_and_file() -> None:
    entries = catalog_entries()
    assert any(entry.kind == "api" for entry in entries)
    assert any(entry.kind == "file_dataset" for entry in entries)
    assert all(entry.provider for entry in entries)


def test_api_endpoint_metadata() -> None:
    endpoint = api_endpoint("knps_visitor_statistics")
    assert endpoint.service_key_param == "serviceKey"
    assert endpoint.verification_status in {"verified", "needs_verification", "planned"}
