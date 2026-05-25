"""다운로드 파일 bytes를 Pydantic DTO로 읽는 helper."""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Literal

from .models import CsvPreview, CsvPreviewRow, FileArtifact, FileDataset, FileMember

CSV_SUFFIXES = (".csv", ".txt")
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr")


def read_file_artifact(
    dataset: FileDataset,
    data: bytes,
    *,
    preview_rows: int = 5,
) -> FileArtifact:
    """다운로드 파일을 archive/text 구조만 읽어서 DTO로 변환한다."""

    if zipfile.is_zipfile(io.BytesIO(data)):
        return _read_zip_artifact(dataset, data, preview_rows=preview_rows)

    preview = _read_csv_preview(None, data, preview_rows=preview_rows)
    kind: Literal["csv", "binary"] = "csv" if preview is not None else "binary"
    return FileArtifact(
        dataset_key=dataset.key,
        data_go_id=dataset.data_go_id,
        kind=kind,
        size_bytes=len(data),
        csv_previews=() if preview is None else (preview,),
    )


def _read_zip_artifact(
    dataset: FileDataset,
    data: bytes,
    *,
    preview_rows: int,
) -> FileArtifact:
    members: list[FileMember] = []
    previews: list[CsvPreview] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            decoded_name = _decode_zip_member_name(info)
            members.append(
                FileMember(
                    name=decoded_name,
                    size_bytes=info.file_size,
                    compressed_size_bytes=info.compress_size,
                )
            )
            if decoded_name.lower().endswith(CSV_SUFFIXES):
                preview = _read_csv_preview(
                    decoded_name,
                    archive.read(info),
                    preview_rows=preview_rows,
                )
                if preview is not None:
                    previews.append(preview)
    return FileArtifact(
        dataset_key=dataset.key,
        data_go_id=dataset.data_go_id,
        kind="zip",
        size_bytes=len(data),
        members=tuple(members),
        csv_previews=tuple(previews),
    )


def _read_csv_preview(
    member_name: str | None,
    data: bytes,
    *,
    preview_rows: int,
) -> CsvPreview | None:
    decoded = _decode_text(data)
    if decoded is None:
        return None
    text, encoding = decoded

    if not text:
        return None

    # csv.reader가 직접 텍스트 스트림을 받게 해서 quoted multi-line cell을 보존한다.
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) < 2:
        return None

    headers = tuple(_clean_header(header, index) for index, header in enumerate(rows[0]))
    header_count = len(headers)
    preview_values: list[CsvPreviewRow] = []
    for raw_row in rows[1 : 1 + preview_rows]:
        # header_count보다 짧으면 None으로 패딩, 길면 나머지를 extra_fields로 보존.
        in_header_vals: list[str | None] = list(raw_row[:header_count])
        in_header_vals.extend([None] * (header_count - len(in_header_vals)))
        extra = tuple(raw_row[header_count:])
        pairs = tuple(zip(headers, in_header_vals, strict=True))
        preview_values.append(CsvPreviewRow(values=pairs, extra_fields=extra))

    return CsvPreview(
        member_name=member_name,
        encoding=encoding,
        headers=headers,
        rows=tuple(preview_values),
    )


def _decode_text(data: bytes) -> tuple[str, str] | None:
    for encoding in TEXT_ENCODINGS:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        return text, encoding
    return None


def _clean_header(value: str, index: int) -> str:
    header = value.strip().lstrip("\ufeff")
    return header or f"field_{index + 1}"


def _decode_zip_member_name(info: zipfile.ZipInfo) -> str:
    """ZIP entry name을 한글 친화적으로 디코드한다.

    KNPS 파일들은 대부분 cp949 raw bytes filename으로 저장되어 있어서,
    Python ``zipfile``이 cp437로 한 번 디코드한 결과를 다시 cp437 bytes로
    되돌린 뒤 cp949로 디코드하면 원본 한글이 복원된다. UTF-8 flag(0x800)가
    켜진 utf-8 filename은 cp437 인코드 단계에서 자연스럽게 ``UnicodeError``가
    나서 원본 이름을 그대로 돌려준다.
    """

    name = info.filename
    try:
        return name.encode("cp437").decode("cp949")
    except UnicodeError:
        return name
