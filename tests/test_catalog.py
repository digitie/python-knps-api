from knps import PROVIDER_NAME
from knps.catalog import catalog_entries, dataset_operations, file_dataset, file_datasets


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


def test_catalog_entries_include_only_file_datasets() -> None:
    entries = catalog_entries()
    assert {entry.kind for entry in entries} == {"file_dataset"}
    assert all(entry.provider for entry in entries)


def test_keyless_direct_download_urls_are_recorded() -> None:
    direct = {dataset.key: dataset for dataset in file_datasets() if dataset.direct_download}
    assert len(direct) == 13
    assert "knps_basic_statistics" not in direct
    assert all(dataset.download_url for dataset in direct.values())
    assert all("atchFileId=" in dataset.download_url for dataset in direct.values())


def test_dataset_operations_empty_for_unverified_dataset() -> None:
    dataset = file_dataset("knps_basic_statistics")
    assert dataset.direct_download is False
    assert dataset_operations(dataset) == ()


def test_dataset_operations_gate_spatial_ops_by_geometry_type() -> None:
    non_spatial = dataset_operations(file_dataset("knps_lod_table_catalog"))
    assert {op.key for op in non_spatial} == {"download_artifact", "download_to_rustfs"}

    line_dataset = dataset_operations(file_dataset("knps_trails"))
    assert {op.key for op in line_dataset} == {
        "download_artifact",
        "download_geometries",
        "read_geo_records",
        "download_to_rustfs",
    }

    point_dataset = dataset_operations(file_dataset("knps_visitor_centers"))
    assert {op.key for op in point_dataset} == {
        "download_artifact",
        "download_geometries",
        "read_geo_records",
        "read_place_records",
        "download_to_rustfs",
    }


def test_dataset_operation_keys_match_file_namespace_methods() -> None:
    from knps.files import FileDataNamespace

    for entry in catalog_entries():
        for operation in dataset_operations(file_dataset(entry.key)):
            assert hasattr(FileDataNamespace, operation.key), operation.key


def test_download_to_rustfs_local_path_default_is_dataset_scoped() -> None:
    operation = next(
        op
        for op in dataset_operations(file_dataset("knps_trails"))
        if op.key == "download_to_rustfs"
    )
    local_path_param = next(param for param in operation.params if param.name == "local_path")
    assert local_path_param.required is True
    assert "{dataset_key}" in local_path_param.default


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
