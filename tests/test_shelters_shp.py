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
    global_field=None,
    global_id="GLOBAL-A",
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
        if global_field is not None:
            writer.field(global_field, "C", size=40)
        if polygon:
            writer.poly([[(127, 37), (127, 38), (128, 38), (127, 37)]])
        else:
            writer.point(*coords)
        values = [objectid, name, "미확인 속성"]
        if global_field is not None:
            values.append(global_id)
        writer.record(*values)
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


@pytest.mark.parametrize("global_field", ["ID_CD", "STN_ID"])
async def test_global_id_survives_renamed_archive_and_layer(global_field):
    original = await _read(_zip({"old.zip": _zip(_layer("old/PT", global_field=global_field))}))
    renamed = await _read(_zip({"new.zip": _zip(_layer("new/PT", global_field=global_field))}))
    assert original[0].source_id == renamed[0].source_id == "GLOBAL-A"
    assert original[0].source_member != renamed[0].source_member
    assert original[0].raw["__knps_source_member__"] != renamed[0].raw["__knps_source_member__"]


@pytest.mark.parametrize("global_field", ["ID_CD", "STN_ID"])
@pytest.mark.parametrize("coords", [(127.5, 37.5), (128, 38)])
async def test_duplicate_global_id_across_members_is_fail_closed(global_field, coords):
    payload = _zip(
        {
            "a.zip": _zip(_layer(global_field=global_field)),
            "b.zip": _zip(_layer(global_field=global_field, coords=coords)),
        }
    )
    with pytest.raises(KnpsParseError, match="duplicate"):
        await _read(payload)


async def test_global_identity_survives_geometry_only_change_with_raw_delta():
    original = (await _read(_zip(_layer(global_field="ID_CD"))))[0]
    moved = (await _read(_zip(_layer(global_field="ID_CD", coords=(128, 38)))))[0]
    assert original.source_id == moved.source_id == "GLOBAL-A"
    assert original.raw != moved.raw


@pytest.mark.parametrize("corruption", ["negative_shp_length", "zero_dbf_stride"])
async def test_malicious_framing_is_rejected_before_any_reader(monkeypatch, corruption):
    entries = _layer()
    del entries["shelters.shx"]
    if corruption == "negative_shp_length":
        import struct

        shp = bytearray(entries["shelters.shp"])
        shp[104:108] = struct.pack(">i", -4)
        entries["shelters.shp"] = bytes(shp)
    else:
        dbf = bytearray(entries["shelters.dbf"])
        dbf[4:8] = (0xFFFFFFFF).to_bytes(4, "little")
        dbf[10:12] = b"\0\0"
        entries["shelters.dbf"] = bytes(dbf)

    def must_not_construct_reader(*args, **kwargs):
        raise AssertionError("unsafe framing reached pyshp.Reader")

    monkeypatch.setattr(shapefile, "Reader", must_not_construct_reader)
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))


async def test_stale_shx_and_shortened_dbf_do_not_hide_second_physical_point():
    entries = _two_points()
    shx = bytearray(entries["p.shx"][:108])
    shx[24:28] = (54).to_bytes(4, "big")
    entries["p.shx"] = bytes(shx)
    dbf = bytearray(entries["p.dbf"])
    header = int.from_bytes(dbf[8:10], "little")
    stride = int.from_bytes(dbf[10:12], "little")
    dbf[4:8] = (1).to_bytes(4, "little")
    entries["p.dbf"] = bytes(dbf[: header + stride])
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))


async def test_valid_two_physical_points_without_shx_are_read_in_order():
    entries = _two_points()
    del entries["p.shx"]
    rows = await _read(_zip(entries))
    assert [r.longitude for r in rows] == [127, 128]
    assert [r.raw["OBJECTID"] for r in rows] == ["1", "2"]


@pytest.mark.parametrize(
    "corruption",
    [
        "shp_file_length",
        "shp_magic",
        "shp_version",
        "shp_zero_record_length",
        "shp_record_outside_file",
        "shp_wrong_point_body",
        "shp_trailing_record_header",
        "dbf_header_length",
        "dbf_header_terminator",
        "dbf_zero_field_width",
        "dbf_stride_mismatch",
        "dbf_huge_count",
        "dbf_truncated_body",
        "dbf_trailing_garbage",
    ],
)
async def test_structural_corruption_rejected_before_reader(monkeypatch, corruption):
    import struct

    entries = _layer()
    if corruption.startswith("shp_"):
        data = bytearray(entries["shelters.shp"])
        if corruption == "shp_file_length":
            data[24:28] = (50).to_bytes(4, "big")
        elif corruption == "shp_magic":
            data[0:4] = b"\0" * 4
        elif corruption == "shp_version":
            data[28:32] = b"\0" * 4
        elif corruption == "shp_zero_record_length":
            data[104:108] = b"\0" * 4
        elif corruption == "shp_record_outside_file":
            data[104:108] = struct.pack(">i", 0x7FFFFFFF)
        elif corruption == "shp_wrong_point_body":
            data[108:112] = (5).to_bytes(4, "little")
        elif corruption == "shp_trailing_record_header":
            data.extend(b"\0\0")
            data[24:28] = (len(data) // 2).to_bytes(4, "big")
        entries["shelters.shp"] = bytes(data)
    else:
        data = bytearray(entries["shelters.dbf"])
        header = int.from_bytes(data[8:10], "little")
        if corruption == "dbf_header_length":
            data[8:10] = (65535).to_bytes(2, "little")
        elif corruption == "dbf_header_terminator":
            data[header - 1] = 0
        elif corruption == "dbf_zero_field_width":
            data[32 + 16] = 0
        elif corruption == "dbf_stride_mismatch":
            stride = int.from_bytes(data[10:12], "little")
            data[10:12] = (stride + 1).to_bytes(2, "little")
        elif corruption == "dbf_huge_count":
            data[4:8] = (0xFFFFFFFF).to_bytes(4, "little")
        elif corruption == "dbf_truncated_body":
            del data[-5:]
        elif corruption == "dbf_trailing_garbage":
            data.extend(b"garbage")
        entries["shelters.dbf"] = bytes(data)

    def must_not_construct_reader(*args, **kwargs):
        raise AssertionError("invalid structure reached pyshp.Reader")

    monkeypatch.setattr(shapefile, "Reader", must_not_construct_reader)
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))


async def test_cumulative_record_limit_checked_before_materializing_layer(monkeypatch):
    from knps import place_shp

    payload = _zip(_two_points())
    monkeypatch.setattr(place_shp, "_MAX_RECORDS", 1)

    def must_not_construct_reader(*args, **kwargs):
        raise AssertionError("record budget must precede Reader")

    monkeypatch.setattr(shapefile, "Reader", must_not_construct_reader)
    with pytest.raises(KnpsParseError, match="record limit"):
        await _read(payload)


async def test_record_limit_shared_by_nested_layers_before_second_reader(monkeypatch):
    from knps import place_shp

    payload = _zip({"a.zip": _zip(_layer()), "b.zip": _zip(_layer())})
    monkeypatch.setattr(place_shp, "_MAX_RECORDS", 1)
    real_reader = shapefile.Reader
    calls = []

    def reader_once(*args, **kwargs):
        calls.append(1)
        if len(calls) > 1:
            raise AssertionError("second layer must fail budget before Reader")
        return real_reader(*args, **kwargs)

    monkeypatch.setattr(shapefile, "Reader", reader_once)
    with pytest.raises(KnpsParseError, match="record limit"):
        await _read(payload)
    assert len(calls) == 1


async def test_ignored_stale_shx_cannot_truncate_valid_physical_shp_and_dbf():
    entries = _two_points()
    shx = bytearray(entries["p.shx"][:108])
    shx[24:28] = (54).to_bytes(4, "big")
    entries["p.shx"] = bytes(shx)
    rows = await _read(_zip(entries))
    assert [r.longitude for r in rows] == [127, 128]
    assert [r.raw["OBJECTID"] for r in rows] == ["1", "2"]


@pytest.mark.parametrize(
    "dataset,zipped",
    [
        ("knps_shelters", False),
        ("knps_shelters", True),
        ("knps_visitor_centers", False),
    ],
)
async def test_explicit_source_crs_csv_fallback_rejected_before_csv_reader(
    monkeypatch,
    dataset,
    zipped,
):
    from knps import files

    payload = "국립공원관리번호,명칭,경도,위도\nA,기존CSV,127.5,37.5\n".encode()
    if zipped:
        payload = _zip({"data.csv": payload})

    def must_not_read_csv(*args, **kwargs):
        raise AssertionError("explicit source_crs reached CSV reader")

    monkeypatch.setattr(files, "read_all_csv_rows", must_not_read_csv)

    def respond(request):
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        async with KnpsClient(session=session, max_rps=None) as client:
            with pytest.raises(KnpsParseError):
                await client.files.read_place_records(dataset, source_crs="EPSG:5179")


@pytest.mark.parametrize(
    "dataset,zipped",
    [
        ("knps_shelters", False),
        ("knps_shelters", True),
        ("knps_visitor_centers", False),
    ],
)
async def test_none_source_crs_csv_fallback_control_unchanged(dataset, zipped):
    payload = "국립공원관리번호,명칭,경도,위도\nA,기존CSV,127.5,37.5\n".encode()
    if zipped:
        payload = _zip({"data.csv": payload})

    def respond(request):
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        async with KnpsClient(session=session, max_rps=None) as client:
            rows = await client.files.read_place_records(dataset, source_crs=None)
    assert rows[0].source_id == "A"
    assert (rows[0].longitude, rows[0].latitude) == (127.5, 37.5)


def _null_then_point(*, deleted):
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(
        shp=shp,
        shx=shx,
        dbf=dbf,
        shapeType=shapefile.POINT,
    ) as writer:
        writer.field("OBJECTID", "N")
        writer.null()
        writer.record(1)
        writer.point(128, 38)
        writer.record(2)
    dbf_bytes = bytearray(dbf.getvalue())
    if deleted:
        header = int.from_bytes(dbf_bytes[8:10], "little")
        dbf_bytes[header] = ord("*")
    return {
        "p.shp": shp.getvalue(),
        "p.shx": shx.getvalue(),
        "p.dbf": bytes(dbf_bytes),
        "p.prj": CRS.from_epsg(4326).to_wkt().encode(),
    }


async def test_deleted_dbf_null_shape_is_skipped_without_losing_next_point():
    rows = await _read(_zip(_null_then_point(deleted=True)))
    assert len(rows) == 1
    assert rows[0].raw["OBJECTID"] == "2"
    assert (rows[0].longitude, rows[0].latitude) == (128, 38)


async def test_active_dbf_null_shape_still_rejected():
    with pytest.raises(KnpsParseError):
        await _read(_zip(_null_then_point(deleted=False)))


async def test_deleted_dbf_null_with_nonfour_byte_body_rejected_before_reader(monkeypatch):
    entries = _layer()
    shp = bytearray(entries["shelters.shp"])
    shp[108:112] = b"\0\0\0\0"  # 원래 Point body 길이 20을 유지한 채 NULL로 위장
    entries["shelters.shp"] = bytes(shp)
    dbf = bytearray(entries["shelters.dbf"])
    header = int.from_bytes(dbf[8:10], "little")
    dbf[header] = ord("*")
    entries["shelters.dbf"] = bytes(dbf)

    def must_not_construct_reader(*args, **kwargs):
        raise AssertionError("oversized NULL reached Reader")

    monkeypatch.setattr(shapefile, "Reader", must_not_construct_reader)
    with pytest.raises(KnpsParseError):
        await _read(_zip(entries))
