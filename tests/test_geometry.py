import io
import zipfile

import pytest

from knps.catalog import file_dataset
from knps.exceptions import KnpsParseError
from knps.geometry import extract_geometries, parse_wkt, read_shapefile_geodataframe


def test_parse_wkt_point() -> None:
    geometry = parse_wkt("POINT (127.5 37.5)")
    assert geometry is not None
    assert geometry.type == "Point"
    assert geometry.coordinates == (127.5, 37.5)


def test_parse_wkt_handles_all_geometry_types() -> None:
    cases = {
        "LINESTRING (127 37, 128 38)": ("LineString", ((127.0, 37.0), (128.0, 38.0))),
        "MULTIPOINT (1 2, 3 4)": ("MultiPoint", ((1.0, 2.0), (3.0, 4.0))),
        "MULTIPOINT ((1 2),(3 4))": ("MultiPoint", ((1.0, 2.0), (3.0, 4.0))),
        "POLYGON ((0 0, 1 0, 1 1, 0 0))": (
            "Polygon",
            (((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),
        ),
        "MULTILINESTRING ((1 2,3 4),(5 6,7 8))": (
            "MultiLineString",
            (((1.0, 2.0), (3.0, 4.0)), ((5.0, 6.0), (7.0, 8.0))),
        ),
        "MULTIPOLYGON (((0 0,1 0,1 1,0 0)),((2 2,3 2,3 3,2 2)))": (
            "MultiPolygon",
            (
                (((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),
                (((2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 2.0)),),
            ),
        ),
    }
    for wkt, (expected_type, expected_coords) in cases.items():
        geometry = parse_wkt(wkt)
        assert geometry is not None, wkt
        assert geometry.type == expected_type
        assert geometry.coordinates == expected_coords


def test_parse_wkt_rejects_unknown_and_empty() -> None:
    assert parse_wkt("GARBAGE (1 2)") is None
    assert parse_wkt("POINT EMPTY") is None
    assert parse_wkt("not wkt at all") is None


def test_extract_geometries_from_csv_lon_lat_columns() -> None:
    dataset = file_dataset("knps_visitor_centers")
    payload = "이름,경도,위도\n탐방안내소,127.5,37.5\n없음,,\n".encode("cp949")

    collection = extract_geometries(dataset, payload)

    assert collection.dataset_key == "knps_visitor_centers"
    assert collection.geometry_type == "Point"
    assert collection.crs is None  # source_crs 미지정이라 재투영하지 않음
    assert len(collection.features) == 2
    first = collection.features[0]
    assert first.geometry is not None
    assert first.geometry.coordinates == (127.5, 37.5)
    assert first.as_dict == {"이름": "탐방안내소", "경도": "127.5", "위도": "37.5"}
    # 좌표가 비면 geometry는 None이지만 속성은 보존된다.
    assert collection.features[1].geometry is None
    assert collection.features[1].as_dict["이름"] == "없음"


def test_extract_geometries_from_csv_wkt_column() -> None:
    dataset = file_dataset("knps_trails")
    payload = '코스,wkt\n둘레길,"LINESTRING (127 37, 128 38)"\n'.encode()

    collection = extract_geometries(dataset, payload)

    feature = collection.features[0]
    assert feature.geometry is not None
    assert feature.geometry.type == "LineString"
    assert feature.geometry.coordinates == ((127.0, 37.0), (128.0, 38.0))


def test_extract_geometries_csv_reprojects_with_explicit_source_crs() -> None:
    pytest.importorskip("pyproj")
    dataset = file_dataset("knps_visitor_centers")
    payload = "이름,x,y\n측점,1000000,2000000\n".encode()

    collection = extract_geometries(dataset, payload, source_crs="EPSG:5179")

    assert collection.source_crs == "EPSG:5179"
    assert collection.crs == "EPSG:4326"
    point = collection.features[0].geometry
    assert point is not None
    lon, lat = point.coordinates
    assert 124.0 < lon < 132.0
    assert 33.0 < lat < 43.0


def test_extract_geometries_raises_when_no_geometry_columns() -> None:
    dataset = file_dataset("knps_lod_table_catalog")
    payload = "이름,값\n지리산,1\n".encode()

    with pytest.raises(KnpsParseError) as excinfo:
        extract_geometries(dataset, payload)
    assert excinfo.value.failure_kind == "geometry"


def test_extract_geometries_raises_for_zip_without_geometry_source() -> None:
    dataset = file_dataset("knps_trails")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.pdf", b"%PDF-1.4 not a geometry")

    with pytest.raises(KnpsParseError):
        extract_geometries(dataset, buffer.getvalue())


def _build_point_shapefile_zip(*, with_prj: bool) -> bytes:
    shapefile = pytest.importorskip("shapefile")
    shp, dbf, shx = io.BytesIO(), io.BytesIO(), io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shx=shx, encoding="cp949")
    writer.field("name", "C")
    writer.point(1000000.0, 2000000.0)
    writer.record("지리산")
    writer.close()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("park.shp", shp.getvalue())
        archive.writestr("park.dbf", dbf.getvalue())
        archive.writestr("park.shx", shx.getvalue())
        if with_prj:
            from pyproj import CRS

            # shapefile .prj는 ESRI WKT1 관례를 따른다 (GDAL/pyproj 모두 인식).
            archive.writestr("park.prj", CRS.from_epsg(5179).to_wkt("WKT1_ESRI"))
    return buffer.getvalue()


def test_extract_geometries_from_shapefile_without_prj_keeps_source_coords() -> None:
    pytest.importorskip("shapefile")
    dataset = file_dataset("knps_park_boundaries")

    collection = extract_geometries(dataset, _build_point_shapefile_zip(with_prj=False))

    assert collection.member_name == "park.shp"
    assert collection.source_crs is None
    assert collection.crs is None
    feature = collection.features[0]
    assert feature.geometry is not None
    # .prj도 source_crs도 없으니 원본 투영 좌표가 그대로 보존된다.
    assert feature.geometry.coordinates == (1000000.0, 2000000.0)
    assert feature.as_dict == {"name": "지리산"}


def test_extract_geometries_from_shapefile_detects_prj_and_reprojects() -> None:
    pytest.importorskip("shapefile")
    pytest.importorskip("pyproj")
    dataset = file_dataset("knps_park_boundaries")

    collection = extract_geometries(dataset, _build_point_shapefile_zip(with_prj=True))

    assert collection.source_crs == "EPSG:5179"
    assert collection.crs == "EPSG:4326"
    feature = collection.features[0]
    assert feature.geometry is not None
    lon, lat = feature.geometry.coordinates
    assert 124.0 < lon < 132.0
    assert 33.0 < lat < 43.0


def test_extract_geometries_explicit_source_crs_overrides_prj() -> None:
    pytest.importorskip("shapefile")
    pytest.importorskip("pyproj")
    dataset = file_dataset("knps_park_boundaries")

    # source_crs를 target과 같게 주면 재투영을 건너뛰고 원본 좌표를 유지한다.
    collection = extract_geometries(
        dataset,
        _build_point_shapefile_zip(with_prj=True),
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
    )

    assert collection.crs == "EPSG:4326"
    feature = collection.features[0]
    assert feature.geometry is not None
    assert feature.geometry.coordinates == (1000000.0, 2000000.0)


def test_geo_feature_collection_as_geojson_roundtrip() -> None:
    dataset = file_dataset("knps_visitor_centers")
    payload = "이름,경도,위도\n탐방안내소,127.5,37.5\n".encode("cp949")

    collection = extract_geometries(dataset, payload)
    geojson = collection.as_geojson

    assert geojson["type"] == "FeatureCollection"
    features = geojson["features"]
    assert isinstance(features, list)
    feature = features[0]
    assert feature["type"] == "Feature"
    assert feature["geometry"] == {"type": "Point", "coordinates": [127.5, 37.5]}
    assert feature["properties"]["이름"] == "탐방안내소"


def test_max_features_limits_extraction() -> None:
    dataset = file_dataset("knps_visitor_centers")
    payload = "이름,경도,위도\na,1,1\nb,2,2\nc,3,3\n".encode()

    collection = extract_geometries(dataset, payload, max_features=2)

    assert len(collection.features) == 2


def test_read_shapefile_geodataframe_returns_geodataframe() -> None:
    geopandas = pytest.importorskip("geopandas")
    pytest.importorskip("shapefile")
    dataset = file_dataset("knps_park_boundaries")

    gdf = read_shapefile_geodataframe(dataset, _build_point_shapefile_zip(with_prj=True))

    assert isinstance(gdf, geopandas.GeoDataFrame)
    assert len(gdf) == 1
    # cp949 한글 속성이 올바르게 디코드된다.
    assert gdf["name"].iloc[0] == "지리산"
    assert gdf.crs is not None and gdf.crs.to_epsg() == 5179


def test_read_shapefile_geodataframe_reprojects_to_target_crs() -> None:
    pytest.importorskip("geopandas")
    pytest.importorskip("shapefile")
    dataset = file_dataset("knps_park_boundaries")

    gdf = read_shapefile_geodataframe(
        dataset,
        _build_point_shapefile_zip(with_prj=True),
        target_crs="EPSG:4326",
    )

    assert gdf.crs is not None and gdf.crs.to_epsg() == 4326
    point = gdf.geometry.iloc[0]
    assert 124.0 < point.x < 132.0
    assert 33.0 < point.y < 43.0


def test_read_shapefile_geodataframe_source_crs_overrides_missing_prj() -> None:
    pytest.importorskip("geopandas")
    pytest.importorskip("shapefile")
    dataset = file_dataset("knps_park_boundaries")

    # .prj가 없어도 source_crs로 좌표계를 선언하고 재투영할 수 있다.
    gdf = read_shapefile_geodataframe(
        dataset,
        _build_point_shapefile_zip(with_prj=False),
        source_crs="EPSG:5179",
        target_crs="EPSG:4326",
    )

    assert gdf.crs is not None and gdf.crs.to_epsg() == 4326
    assert 124.0 < gdf.geometry.iloc[0].x < 132.0


def test_read_shapefile_geodataframe_target_without_crs_raises() -> None:
    pytest.importorskip("geopandas")
    pytest.importorskip("shapefile")
    dataset = file_dataset("knps_park_boundaries")

    with pytest.raises(KnpsParseError) as excinfo:
        read_shapefile_geodataframe(
            dataset,
            _build_point_shapefile_zip(with_prj=False),
            target_crs="EPSG:4326",
        )
    assert excinfo.value.failure_kind == "geometry"


def test_read_shapefile_geodataframe_rejects_non_zip() -> None:
    pytest.importorskip("geopandas")
    dataset = file_dataset("knps_park_boundaries")

    with pytest.raises(KnpsParseError):
        read_shapefile_geodataframe(dataset, b"not a zip at all")


def test_read_shapefile_geodataframe_raises_without_shp_member() -> None:
    pytest.importorskip("geopandas")
    dataset = file_dataset("knps_park_boundaries")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", b"no shapefile here")

    with pytest.raises(KnpsParseError):
        read_shapefile_geodataframe(dataset, buffer.getvalue())
