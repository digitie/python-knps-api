import io
import zipfile

from knps.artifacts import read_file_artifact
from knps.catalog import file_dataset


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
    assert artifact.csv_previews[0].rows[0].values == {"이름": "지리산", "값": "1"}


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
    assert artifact.csv_previews[0].rows[0].values["코스"] == "둘레길"


def test_read_zip_file_artifact_decodes_cp949_member_names() -> None:
    dataset = file_dataset("knps_trails")
    buffer = io.BytesIO()
    info = zipfile.ZipInfo("탐방로.csv".encode("cp949").decode("cp437"))
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(info, "코스,거리\n둘레길,3.2\n")

    artifact = read_file_artifact(dataset, buffer.getvalue())

    assert artifact.members[0].name == "탐방로.csv"
