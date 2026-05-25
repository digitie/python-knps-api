from knps import PROVIDER_NAME
from knps.catalog import catalog_entries, file_dataset, file_datasets


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
    assert "knps_campgrounds" in keys
    assert "knps_shelters" in keys
    assert "knps_visitor_statistics" in keys


def test_lookup_by_key_and_id() -> None:
    by_key = file_dataset("knps_trails")
    by_id = file_dataset("15003467")
    assert by_key == by_id
    assert by_key.feature_kind == "route"


def test_catalog_entries_include_only_verified_file_datasets() -> None:
    entries = catalog_entries()
    assert {entry.kind for entry in entries} == {"file_dataset"}
    assert all(entry.provider for entry in entries)
    assert all(entry.verification_status == "verified" for entry in entries)


def test_verified_data_go_ids_match_catalog() -> None:
    expected = {
        "knps_park_boundaries": "15017313",
        "knps_trails": "15003467",
        "knps_visitor_centers": "15003445",
        "knps_hazard_zones": "15003441",
        "knps_weather_stations": "15090557",
        "knps_restrooms": "15003468",
        "knps_cultural_resources": "15003443",
        "knps_campgrounds": "15003469",
        "knps_shelters": "2982556",
        "knps_linear_facilities": "15091972",
        "knps_basic_statistics": "15087598",
        "knps_visitor_statistics": "15107577",
        "knps_protected_areas": "15127921",
        "knps_lod_table_catalog": "15118945",
    }
    assert {dataset.key: dataset.data_go_id for dataset in file_datasets()} == expected
