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
            members.append(
                FileMember(
                    name=_decode_zip_name(info.filename),
                    size_bytes=info.file_size,
                    compressed_size_bytes=info.compress_size,
                )
            )
            if info.filename.lower().endswith(CSV_SUFFIXES):
                preview = _read_csv_preview(
                    _decode_zip_name(info.filename),
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

    lines = text.splitlines()
    if not lines:
        return None

    rows = list(csv.reader(lines))
    if not rows or len(rows[0]) < 2:
        return None

    headers = tuple(_clean_header(header, index) for index, header in enumerate(rows[0]))
    preview_values: list[CsvPreviewRow] = []
    for raw_row in rows[1 : 1 + preview_rows]:
        padded = [*raw_row, *([None] * max(0, len(headers) - len(raw_row)))]
        values = dict(zip(headers, padded[: len(headers)], strict=False))
        preview_values.append(CsvPreviewRow(values=values))

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


def _decode_zip_name(name: str) -> str:
    try:
        return name.encode("cp437").decode("cp949")
    except UnicodeError:
        return name
