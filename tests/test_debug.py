from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from knps import DebugRun, KnpsClient
from knps.catalog import DatasetOperation, dataset_operations, file_dataset
from knps.debug import (
    arun_dataset_operation,
    debug_error,
    jsonable,
    redact_sensitive,
    resolve_operation_kwargs,
    run_dataset_operation,
    save_fixture,
    slugify_case_name,
)
from knps.exceptions import KnpsParseError
from knps.models import CsvPreview, CsvPreviewRow, FileArtifact


def _operation(dataset_key: str, operation_key: str) -> DatasetOperation:
    dataset = file_dataset(dataset_key)
    operations = {op.key: op for op in dataset_operations(dataset)}
    return operations[operation_key]


def test_jsonable_converts_pydantic_models_and_tuples() -> None:
    preview = CsvPreview(
        member_name=None,
        encoding="utf-8",
        headers=("이름",),
        rows=(CsvPreviewRow(values=(("이름", "지리산"),)),),
    )
    payload = jsonable((preview, {"count": 1}))

    assert payload == [
        {
            "member_name": None,
            "encoding": "utf-8",
            "headers": ["이름"],
            "rows": [{"values": [["이름", "지리산"]], "extra_fields": []}],
        },
        {"count": 1},
    ]


def test_redact_sensitive_masks_rustfs_credentials() -> None:
    payload = {
        "rustfs_access_key": "AKIA...",
        "rustfs_secret_key": "SECRET",
        "headers": {"Authorization": "Bearer SECRET"},
        "items": [{"service_key": "SECRET"}, {"name": "safe"}],
    }

    assert redact_sensitive(payload) == {
        "rustfs_access_key": "<REDACTED>",
        "rustfs_secret_key": "<REDACTED>",
        "headers": {"Authorization": "<REDACTED>"},
        "items": [{"service_key": "<REDACTED>"}, {"name": "safe"}],
    }


def test_debug_error_includes_type_message_traceback_and_provider_fields() -> None:
    try:
        raise KnpsParseError(
            "boom",
            provider="data.go.kr",
            endpoint="knps_trails",
            failure_kind="csv",
            params={"api_key": "SECRET"},
        )
    except KnpsParseError as exc:
        payload = debug_error(exc)

    assert payload["type"] == "KnpsParseError"
    assert payload["message"] == "boom"
    assert "Traceback" in payload["traceback"]
    assert payload["provider"] == "data.go.kr"
    assert payload["endpoint"] == "knps_trails"
    assert payload["failure_kind"] == "csv"
    assert payload["params"]["api_key"] == "<REDACTED>"


def test_save_fixture_writes_redacted_json_and_prevents_overwrite(tmp_path: Path) -> None:
    path = save_fixture(
        base_dir=tmp_path,
        function_name="knps_lod_table_catalog__download_artifact",
        case_name="정상 케이스",
        description="download_artifact replay fixture",
        input_data={"kwargs": {"rustfs_secret_key": "SECRET"}},
        request_data={"download_url": "https://example.invalid"},
        response_data={"status": "ok"},
        parsed_result=None,
        processed_result=[],
    )

    assert path.name == "정상-케이스.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["input"]["kwargs"]["rustfs_secret_key"] == "<REDACTED>"
    assert saved["assertion"]["mode"] == "snapshot"

    try:
        save_fixture(
            base_dir=tmp_path,
            function_name="knps_lod_table_catalog__download_artifact",
            case_name="정상 케이스",
            description="duplicate",
            input_data={},
            request_data={},
            response_data={},
            parsed_result=None,
            processed_result=None,
        )
    except FileExistsError:
        pass
    else:  # pragma: no cover - 안전망
        raise AssertionError("expected FileExistsError")


def test_slugify_case_name_has_fallback() -> None:
    assert slugify_case_name("  다운로드 Case 01  ") == "다운로드-case-01"
    assert slugify_case_name("!!!") == "case"


def test_resolve_operation_kwargs_type_converts_and_skips_blank_optional() -> None:
    operation = _operation("knps_park_boundaries", "download_geometries")
    kwargs = resolve_operation_kwargs(
        operation,
        file_dataset("knps_park_boundaries"),
        {
            "source_crs": "  ",
            "target_crs": "EPSG:4326",
            "max_features": "10",
            "max_bytes": "",
        },
    )

    assert kwargs == {"target_crs": "EPSG:4326", "max_features": 10}


async def test_arun_dataset_operation_success_builds_response_summary_and_processed() -> None:
    client = KnpsClient()
    try:
        artifact = FileArtifact(
            dataset_key="knps_lod_table_catalog",
            data_go_id="15118945",
            kind="csv",
            size_bytes=42,
            csv_previews=(
                CsvPreview(
                    member_name=None,
                    encoding="utf-8",
                    headers=("이름",),
                    rows=(CsvPreviewRow(values=(("이름", "지리산"),)),),
                ),
            ),
        )
        client.files.download_artifact = AsyncMock(return_value=artifact)  # type: ignore[method-assign]

        operation = _operation("knps_lod_table_catalog", "download_artifact")
        run = await arun_dataset_operation(
            client, "knps_lod_table_catalog", operation, {"preview_rows": 1}
        )
    finally:
        await client.aclose()

    assert isinstance(run, DebugRun)
    assert run.error is None
    assert run.response["status"] == "ok"
    assert run.response["result_type"] == "FileArtifact"
    assert run.response["size_bytes"] == 42
    assert run.response["csv_preview_count"] == 1
    assert run.processed == [artifact.csv_previews[0]]
    assert run.catalog is not None
    assert run.catalog["key"] == "knps_lod_table_catalog"
    assert any("실행 성공" in step for step in run.trace)


async def test_arun_dataset_operation_captures_errors_without_raising() -> None:
    client = KnpsClient()
    try:
        client.files.download_artifact = AsyncMock(  # type: ignore[method-assign]
            side_effect=KnpsParseError("could not decode", failure_kind="csv")
        )
        operation = _operation("knps_lod_table_catalog", "download_artifact")
        run = await arun_dataset_operation(client, "knps_lod_table_catalog", operation, {})
    finally:
        await client.aclose()

    assert run.error is not None
    assert run.error["type"] == "KnpsParseError"
    assert run.error["failure_kind"] == "csv"
    assert run.response["status"] == "error"
    assert run.parsed is None
    assert run.processed is None


async def test_arun_dataset_operation_rejects_unknown_operation_key() -> None:
    client = KnpsClient()
    try:
        bogus = DatasetOperation(key="not_a_real_op", label="x", description="y")
        run = await arun_dataset_operation(client, "knps_lod_table_catalog", bogus, {})
    finally:
        await client.aclose()

    assert run.error is not None
    assert run.error["failure_kind"] == "unknown_operation"
    assert run.catalog is not None


def test_run_dataset_operation_closes_client(monkeypatch) -> None:
    client = KnpsClient()
    client.files.download_artifact = AsyncMock(  # type: ignore[method-assign]
        return_value=FileArtifact(
            dataset_key="knps_lod_table_catalog",
            data_go_id="15118945",
            kind="binary",
            size_bytes=0,
        )
    )
    aclose_mock = AsyncMock()
    monkeypatch.setattr(client, "aclose", aclose_mock)

    operation = _operation("knps_lod_table_catalog", "download_artifact")
    run = run_dataset_operation(client, "knps_lod_table_catalog", operation, {})

    assert run.error is None
    aclose_mock.assert_awaited_once()
