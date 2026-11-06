"""대피소 합성 SHP 회귀. 실제 KNPS 필드·좌표계 검증 자료가 아니다."""

import io
import zipfile

import httpx
import pytest
import shapefile
from pyproj import CRS

from knps import KnpsClient
from knps.exceptions import KnpsParseError


def _zip(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return stream.getvalue()


def _layer(
    stem="shelters",
    *,
    polygon=False,
    encoding="cp949",
    cpg=None,
    crs=4326,
    coords=(127.5, 37.5),
    objectid=1,
    name="한글 대피소",
):
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(
        shp=shp,
        shx=shx,
        dbf=dbf,
        shapeType=shapefile.POLYGON if polygon else shapefile.POINT,
        encoding=encoding,
    ) as writer:
        writer.field("OBJECTID", "N", decimal=0)
        writer.field("KOR_NM", "C", size=80)
        writer.field("EXTRA", "C", size=80)
        if polygon:
            writer.poly([[(127, 37), (127, 38), (128, 38), (127, 37)]])
        else:
            writer.point(*coords)
        writer.record(objectid, name, "미확인 속성")
    entries = {
        stem + ".shp": shp.getvalue(),
        stem + ".shx": shx.getvalue(),
        stem + ".dbf": dbf.getvalue(),
    }
    if crs is not None:
        entries[stem + ".prj"] = CRS.from_epsg(crs).to_wkt().encode()
    if cpg is not None:
        entries[stem + ".cpg"] = cpg.encode()
    return entries


async def _read(payload, **kwargs):
    def respond(request):
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        async with KnpsClient(session=session, max_rps=None) as client:
            return await client.files.read_place_records("knps_shelters", **kwargs)


async def test_nested_multiple_points_excludes_polygon_and_preserves_raw():
    payload = _zip(
        {
            **_layer("00_footprint", polygon=True),
            "b.zip": _zip(_layer("시설/PT")),
            "a.zip": _zip(_layer("시설/PT", coords=(128.5, 38.5))),
        }
    )
    rows = await _read(payload)
    assert len(rows) == 2
    assert [row.longitude for row in rows] == [128.5, 127.5]
    assert [row.source_member for row in rows] == ["a.zip!/시설/PT.shp", "b.zip!/시설/PT.shp"]
    assert len({row.source_id for row in rows}) == 2  # 두 레이어의 OBJECTID=1
    assert all(row.name == "한글 대피소" for row in rows)
    for row in rows:
        assert {k: v for k, v in row.raw.items() if not k.startswith("__knps_")} == {
            "OBJECTID": "1",
            "KOR_NM": "한글 대피소",
            "EXTRA": "미확인 속성",
        }
        assert row.raw["__knps_source_member__"] == row.source_member
        assert row.raw["__knps_source_crs__"] == "EPSG:4326"
    assert (await _read(payload)) == rows


async def test_shp_member_identity_is_independent_of_zip_order():
    entries = {"b.zip": _zip(_layer("PT")), "a.zip": _zip(_layer("PT"))}
    first = await _read(_zip(entries))
    second = await _read(_zip(dict(reversed(list(entries.items())))))
    assert first == second
    assert len({row.source_id for row in first}) == 2


@pytest.mark.parametrize("cpg", ["UTF-8", "65001"])
async def test_cpg_utf8_preserves_korean(cpg):
    rows = await _read(_zip(_layer(encoding="utf-8", cpg=cpg)))
    assert rows[0].name == "한글 대피소"
    assert rows[0].raw["EXTRA"] == "미확인 속성"


async def test_prj_projected_points_are_reprojected():
    rows = await _read(_zip(_layer(crs=5179, coords=(1000000, 2000000))))
    assert rows[0].longitude == pytest.approx(127.5)
    assert rows[0].latitude == pytest.approx(38.0)


async def test_explicit_crs_supports_points_without_prj():
    rows = await _read(_zip(_layer(crs=None)), source_crs="EPSG:4326")
    assert (rows[0].longitude, rows[0].latitude) == (127.5, 37.5)


async def test_plain_csv_control_unchanged():
    rows = await _read("국립공원관리번호,명칭,경도,위도\nA,대피소,127.5,37.5\n".encode())
    assert rows[0].source_id == "A"
    assert rows[0].name == "대피소"


async def test_csv_zip_control_unchanged():
    rows = await _read(
        _zip({"shelters.csv": "국립공원관리번호,명칭,경도,위도\nA,대피소,127.5,37.5\n".encode()})
    )
    assert rows[0].source_id == "A"


@pytest.mark.parametrize("crs", [None, "invalid"])
async def test_unknown_or_invalid_prj_does_not_guess_wgs84(crs):
    entries = _layer(crs=None)
    if crs:
        entries["shelters.prj"] = b"not a coordinate system"
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))


async def test_polygon_only_is_not_a_shelter_centroid_or_silent_empty_success():
    with pytest.raises(KnpsParseError):
        await _read(_zip(_layer(polygon=True)))


async def test_shp_only_bytes_are_not_readable_via_csv_reader():
    from knps.artifacts import read_all_csv_rows

    payload = _zip({"nested.zip": _zip(_layer())})
    with pytest.raises(KnpsParseError, match="no CSV/TXT"):
        read_all_csv_rows(payload)
    assert len(await _read(payload)) == 1


async def test_point_shp_takes_precedence_over_unrelated_csv():
    payload = _zip({**_layer(), "dictionary.csv": b"name,value\nfake,1\n"})
    rows = await _read(payload)
    assert len(rows) == 1
    assert rows[0].name == "한글 대피소"


@pytest.mark.parametrize("coord", [(float("nan"), 37), (200, 37), (127, 100)])
async def test_nonfinite_or_out_of_range_point_is_rejected(coord):
    with pytest.raises(KnpsParseError):
        await _read(_zip(_layer(coords=coord)))


async def test_explicit_invalid_crs_is_typed_error():
    with pytest.raises(KnpsParseError):
        await _read(_zip(_layer()), source_crs="invalid")


@pytest.mark.parametrize("cpg", ["not-an-encoding", "UTF-8"])
async def test_unknown_cpg_or_wrong_declared_encoding_is_not_replaced(cpg):
    with pytest.raises(KnpsParseError):
        await _read(_zip(_layer(encoding="cp949", cpg=cpg)))


async def test_point_requires_dbf():
    entries = _layer()
    del entries["shelters.dbf"]
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))


@pytest.mark.parametrize("name", ["../PT.shp", "/PT.shp", "C:/PT.shp", "a!/PT.shp"])
async def test_unsafe_archive_paths_rejected(name):
    with pytest.raises(KnpsParseError):
        await _read(_zip({name: b"bad"}))


async def test_case_ambiguous_members_rejected():
    with pytest.raises(KnpsParseError):
        await _read(_zip({**_layer(), "SHELTERS.SHP": b"ambiguous"}))


@pytest.mark.parametrize(
    "limit,value",
    [
        ("_MAX_DEPTH", 0),
        ("_MAX_MEMBERS", 5),
        ("_MAX_MEMBER_BYTES", 10),
        ("_MAX_TOTAL_BYTES", 500),
    ],
)
async def test_archive_resource_budgets_are_enforced(monkeypatch, limit, value):
    from knps import place_shp

    monkeypatch.setattr(place_shp, limit, value)
    payload = _zip({"a.zip": _zip(_layer()), "b.zip": _zip(_layer())})
    with pytest.raises(KnpsParseError, match="limit"):
        await _read(payload)


async def test_duplicate_source_id_within_a_layer_is_not_silently_overwritten():
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf) as writer:
        writer.field("OBJECTID", "N")
        for x in (127, 128):
            writer.point(x, 37)
            writer.record(1)
    with pytest.raises(KnpsParseError, match="duplicate"):
        await _read(
            _zip(
                {
                    "p.shp": shp.getvalue(),
                    "p.shx": shx.getvalue(),
                    "p.dbf": dbf.getvalue(),
                    "p.prj": CRS.from_epsg(4326).to_wkt().encode(),
                }
            )
        )


async def test_zero_id_is_scoped_to_member_not_treated_as_global_identity():
    rows = await _read(_zip({**_layer("one", objectid=0), **_layer("two", objectid=0)}))
    assert len({r.source_id for r in rows}) == 2
    assert all(r.raw["OBJECTID"] == "0" for r in rows)


def test_bare_codes_are_explicit_and_original_properties_are_preserved():
    from knps.records import normalize_place_record

    raw = {"OBJECTID": "1", "ID_CD": "A", "KOR_NM": "대피소", "UNKNOWN": "원본"}
    legacy = normalize_place_record("knps_shelters", raw)
    shp = normalize_place_record("knps_shelters", raw, bare_codes=True)
    assert legacy.name is None
    assert legacy.source_id.startswith("row:")
    assert shp.name == "대피소"
    assert shp.source_id == "A"
    assert shp.raw == raw == legacy.raw


def test_catalog_does_not_claim_synthetic_fields_verified():
    from knps.catalog import file_dataset

    shelters = file_dataset("knps_shelters")
    assert shelters.verification_status == "needs_verification"
    assert shelters.download_url  # 이전 다운로드 URL은 그대로 보존


def _two_points():
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf) as writer:
        writer.field("OBJECTID", "N")
        for x, identity in ((127, 1), (128, 2)):
            writer.point(x, 37)
            writer.record(identity)
    return {
        "p.shp": shp.getvalue(),
        "p.shx": shx.getvalue(),
        "p.dbf": dbf.getvalue(),
        "p.prj": CRS.from_epsg(4326).to_wkt().encode(),
    }


async def test_mismatched_dbf_count_rejects_partial_success():
    entries = _two_points()
    dbf = bytearray(entries["p.dbf"])
    dbf[4:8] = (1).to_bytes(4, "little")
    entries["p.dbf"] = bytes(dbf)
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))


async def test_deleted_dbf_row_does_not_shift_next_point_attributes():
    entries = _two_points()
    dbf = bytearray(entries["p.dbf"])
    header_length = int.from_bytes(dbf[8:10], "little")
    dbf[header_length] = ord("*")
    entries["p.dbf"] = bytes(dbf)
    rows = await _read(_zip(entries))
    assert len(rows) == 1
    assert rows[0].raw["OBJECTID"] == "2"
    assert rows[0].longitude == 128


async def test_geometry_only_update_preserves_id_but_changes_raw_payload():
    first = (await _read(_zip(_layer(coords=(127, 37)))))[0]
    moved = (await _read(_zip(_layer(coords=(128, 38)))))[0]
    assert first.source_id == moved.source_id
    assert first.raw != moved.raw
    assert first.raw["OBJECTID"] == moved.raw["OBJECTID"] == "1"
    assert first.raw["__knps_point_wgs84__"] != moved.raw["__knps_point_wgs84__"]


async def test_missing_optional_shx_and_uppercase_sidecars():
    entries = {name.upper(): data for name, data in _layer().items() if not name.endswith(".shx")}
    rows = await _read(_zip(entries))
    assert rows[0].source_member == "SHELTERS.SHP"
    assert rows[0].name == "한글 대피소"


@pytest.mark.parametrize("shape_type", [shapefile.POINTZ, shapefile.POINTM])
async def test_point_z_and_m_use_actual_xy_only(shape_type):
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shape_type) as writer:
        writer.field("OBJECTID", "N")
        if shape_type == shapefile.POINTZ:
            writer.pointz(127, 37, 1200)
        else:
            writer.pointm(127, 37, 1200)
        writer.record(1)
    rows = await _read(
        _zip(
            {
                "p.shp": shp.getvalue(),
                "p.dbf": dbf.getvalue(),
                "p.prj": CRS.from_epsg(4326).to_wkt().encode(),
            }
        )
    )
    assert (rows[0].longitude, rows[0].latitude) == (127, 37)


async def test_multipoint_is_not_promoted_to_single_shelter():
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.MULTIPOINT) as writer:
        writer.field("OBJECTID", "N")
        writer.multipoint([(127, 37), (128, 38)])
        writer.record(1)
    with pytest.raises(KnpsParseError, match="no usable Point"):
        await _read(_zip({"p.shp": shp.getvalue(), "p.dbf": dbf.getvalue()}))


async def test_anonymous_points_with_identical_attributes_do_not_collapse():
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf) as writer:
        writer.field("UNKNOWN", "C")
        for x in (127, 128):
            writer.point(x, 37)
            writer.record("same")
    rows = await _read(
        _zip(
            {
                "p.shp": shp.getvalue(),
                "p.dbf": dbf.getvalue(),
                "p.prj": CRS.from_epsg(4326).to_wkt().encode(),
            }
        )
    )
    assert len({r.source_id for r in rows}) == 2
    assert all(r.name is None for r in rows)


async def test_other_dataset_keeps_existing_csv_member_selection():
    payload = _zip(
        {**_layer(), "data.csv": "국립공원관리번호,명칭,경도,위도\nA,기존CSV,127,37\n".encode()}
    )

    def respond(request):
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        async with KnpsClient(session=session, max_rps=None) as client:
            rows = await client.files.read_place_records("knps_visitor_centers")
    assert len(rows) == 1
    assert rows[0].source_id == "A"
    assert rows[0].name == "기존CSV"
    assert rows[0].source_member is None
    assert not any(k.startswith("__knps_") for k in rows[0].raw)


def test_only_shelter_catalog_place_operation_adds_source_crs():
    from knps.catalog import dataset_operations, file_dataset

    def params(key):
        operation = next(
            op for op in dataset_operations(file_dataset(key)) if op.key == "read_place_records"
        )
        return {p.name for p in operation.params}

    assert params("knps_shelters") == {"source_crs", "max_bytes"}
    assert params("knps_visitor_centers") == {"max_bytes"}
