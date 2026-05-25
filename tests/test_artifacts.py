import io
import zipfile

import pytest
from pydantic import ValidationError

from knps.artifacts import read_file_artifact
from knps.catalog import file_dataset
from knps.models import CsvPreviewRow


def test_read_csv_file_artifact_as_pydantic_dto() -> None:
    dataset = file_dataset("knps_lod_table_catalog")
    artifact = read_file_artifact(
        dataset,
        "이름,값\n지리산,1\n설악산,2\n".encode("cp949"),
        preview_rows=1,
    )

    assert artifact.kind == "csv"
    assert artifact.dataset_key == "knps_lod_table_catalog"
    assert artifact.csv_previews[0].encoding == "cp949"
    assert artifact.csv_previews[0].headers == ("이름", "값")
    assert artifact.csv_previews[0].rows[0].values == (("이름", "지리산"), ("값", "1"))
    assert artifact.csv_previews[0].rows[0].as_dict == {"이름": "지리산", "값": "1"}
    assert artifact.csv_previews[0].rows[0].extra_fields == ()


def test_read_zip_file_artifact_members_and_csv_preview() -> None:
    dataset = file_dataset("knps_trails")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("trail.csv", "코스,거리\n둘레길,3.2\n")
        archive.writestr("trail.shp", b"shape")

    artifact = read_file_artifact(dataset, buffer.getvalue())

    assert artifact.kind == "zip"
    assert {member.name for member in artifact.members} == {"trail.csv", "trail.shp"}
    assert artifact.csv_previews[0].member_name == "trail.csv"
    assert artifact.csv_previews[0].rows[0].as_dict["코스"] == "둘레길"


def test_read_zip_file_artifact_decodes_cp949_member_names() -> None:
    dataset = file_dataset("knps_trails")
    buffer = io.BytesIO()
    info = zipfile.ZipInfo("탐방로.csv".encode("cp949").decode("cp437"))
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(info, "코스,거리\n둘레길,3.2\n")

    artifact = read_file_artifact(dataset, buffer.getvalue())

    assert artifact.members[0].name == "탐방로.csv"


def test_read_csv_preview_preserves_quoted_multiline_cells() -> None:
    """따옴표 안에 줄바꿈이 있는 cell이 row 경계로 잘리지 않는다."""

    dataset = file_dataset("knps_lod_table_catalog")
    payload = '제목,설명\n"공원","경계\n폴리곤"\n'.encode()

    artifact = read_file_artifact(dataset, payload, preview_rows=2)

    assert artifact.kind == "csv"
    row = artifact.csv_previews[0].rows[0]
    assert row.as_dict == {"제목": "공원", "설명": "경계\n폴리곤"}


def test_read_csv_preview_keeps_trailing_columns_in_extra_fields() -> None:
    """header 개수보다 긴 row의 trailing 값이 ``extra_fields``에 보존된다."""

    dataset = file_dataset("knps_lod_table_catalog")
    payload = "이름,값\n지리산,1,추가1,추가2\n".encode()

    artifact = read_file_artifact(dataset, payload, preview_rows=1)

    row = artifact.csv_previews[0].rows[0]
    assert row.values == (("이름", "지리산"), ("값", "1"))
    assert row.extra_fields == ("추가1", "추가2")


def test_csv_preview_row_values_are_immutable() -> None:
    """``values``는 tuple이라 in-place mutation이 불가능하다."""

    row = CsvPreviewRow(values=(("이름", "지리산"),))
    with pytest.raises(TypeError):
        row.values[0] = ("다른", "값")  # type: ignore[index]
    # Pydantic frozen이라 attribute 재할당도 막힘.
    with pytest.raises(ValidationError):
        row.values = (("이름", "치악산"),)  # type: ignore[misc]
