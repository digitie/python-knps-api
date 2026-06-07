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


@pytest.mark.live
async def test_live_shapefile_geometry_reprojects_to_wgs84() -> None:
    """공원경계 SHP ZIP을 geometry로 추출하고 WGS84로 재투영한다."""

    pytest.importorskip("shapefile")
    pytest.importorskip("pyproj")
    async with KnpsClient(timeout=120) as client:
        collection = await client.files.download_geometries("knps_park_boundaries")

    assert collection.features
    assert collection.crs == "EPSG:4326"
    first_geometry = next(
        feature.geometry for feature in collection.features if feature.geometry is not None
    )
    assert first_geometry.type in {"Polygon", "MultiPolygon"}
    # WGS84 재투영 후 한반도 경위도 범위 안에 있어야 한다.
    positions = _flatten_positions(first_geometry.coordinates)
    lon, lat = positions[0]
    assert 124.0 < lon < 132.0
    assert 33.0 < lat < 43.0


@pytest.mark.live
async def test_live_read_place_records_visitor_centers() -> None:
    """실데이터에서 typed place record가 source_id/name/lon/lat을 채운다."""

    async with KnpsClient(timeout=120) as client:
        records = await client.files.read_place_records("knps_visitor_centers")

    assert records
    first = records[0]
    assert first.dataset_key == "knps_visitor_centers"
    assert first.source_id and not first.source_id.startswith("row:")
    assert first.name
    assert first.longitude is not None and 124.0 < first.longitude < 132.0
    assert first.latitude is not None and 33.0 < first.latitude < 43.0


@pytest.mark.live
async def test_live_read_geo_records_trails() -> None:
    """실데이터에서 typed geo record가 WKT와 정규화 필드를 채운다."""

    async with KnpsClient(timeout=120) as client:
        records = await client.files.read_geo_records("knps_trails", max_features=50)

    assert records
    first = records[0]
    assert first.dataset_key == "knps_trails"
    assert first.geom_wkt.startswith(("POINT", "LINESTRING", "MULTILINESTRING"))
    assert first.name
    assert first.longitude is not None and 124.0 < first.longitude < 132.0
    assert first.latitude is not None and 33.0 < first.latitude < 43.0


def _flatten_positions(node: object) -> list[tuple[float, ...]]:
    if isinstance(node, tuple) and node and all(isinstance(item, float) for item in node):
        return [node]  # type: ignore[list-item]
    if isinstance(node, tuple):
        result: list[tuple[float, ...]] = []
        for child in node:
            result.extend(_flatten_positions(child))
        return result
    return []
