"""Streamlit 기반 KNPS 파일 dataset 디버그 워크벤치."""
# ruff: noqa: E402,I001

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
for module_name, module in list(sys.modules.items()):
    if module_name != "knps" and not module_name.startswith("knps."):
        continue
    module_file = getattr(module, "__file__", None)
    if module_file is not None and not Path(module_file).resolve().is_relative_to(SRC):
        del sys.modules[module_name]

try:
    import pandas as pd
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - 선택 실행 도구
    raise SystemExit('Streamlit UI를 쓰려면 `pip install -e ".[debug-ui]"`를 실행하세요.') from exc

from knps import (
    DatasetOperation,
    DebugRun,
    KnpsClient,
    KnpsConfig,
    OperationParam,
    catalog_entries,
    dataset_operations,
    debug_error,
    file_dataset,
    jsonable,
    redact_sensitive,
    resolve_operation_kwargs,
    run_dataset_operation,
    save_fixture,
)
from knps.models import CatalogEntry, FileDataset

# KnpsConfig.from_env()이 실제로 읽는 RustFS credential env var 이름
# (3단 폴백: KNPS_* -> RUSTFS_* -> KRTOUR_MAP_*). knps.config 참고.
_RUSTFS_ENDPOINT_ENV_NAMES = (
    "KNPS_RUSTFS_ENDPOINT_URL",
    "RUSTFS_ENDPOINT_URL",
    "KRTOUR_MAP_OBJECT_STORE_ENDPOINT_URL",
)
_RUSTFS_BUCKET_ENV_NAMES = (
    "KNPS_RUSTFS_BUCKET",
    "RUSTFS_BUCKET",
    "KRTOUR_MAP_OBJECT_STORE_BUCKET",
)
_RUSTFS_ACCESS_KEY_ENV_NAMES = (
    "KNPS_RUSTFS_ACCESS_KEY",
    "RUSTFS_ACCESS_KEY",
    "KNPS_RUSTFS_ACCESS_KEY_ID",
    "RUSTFS_ACCESS_KEY_ID",
    "KRTOUR_MAP_OBJECT_STORE_ACCESS_KEY_ID",
)
_RUSTFS_SECRET_KEY_ENV_NAMES = (
    "KNPS_RUSTFS_SECRET_KEY",
    "RUSTFS_SECRET_KEY",
    "KNPS_RUSTFS_SECRET_ACCESS_KEY",
    "RUSTFS_SECRET_ACCESS_KEY",
    "KRTOUR_MAP_OBJECT_STORE_SECRET_ACCESS_KEY",
)

_SESSION_RUNS_KEY = "knps_debug_runs"

TAB_LABELS = (
    "Raw Response",
    "Pydantic Model",
    "Processed Result",
    "Validation Errors",
    "Debug Trace",
    "Fixture / Testcase",
)


def main() -> None:
    st.set_page_config(page_title="KNPS File Dataset Debug", layout="wide")
    st.title("KNPS File Dataset Debug")
    st.caption(
        "국립공원공단(KNPS) data.go.kr 파일 dataset catalog를 다운로드/파싱까지 실행해 "
        "검증하는 디버그 워크벤치입니다. 이 저장소는 OpenAPI 서비스가 아니라 파일 "
        "카탈로그라서 서비스키가 필요 없습니다."
    )

    entries = catalog_entries()

    st.sidebar.header("Dataset")
    keys = [entry.key for entry in entries]
    label_by_key = {entry.key: _entry_label(entry) for entry in entries}
    selected_key = st.sidebar.selectbox(
        "Dataset",
        keys,
        format_func=lambda key: label_by_key[str(key)],
    )
    entry = next(candidate for candidate in entries if candidate.key == selected_key)
    dataset = file_dataset(entry.key)

    st.sidebar.caption(entry.description)
    st.sidebar.caption(_returns_caption(dataset))

    env = _environment_sidebar()
    timeout = st.sidebar.number_input(
        "Timeout",
        min_value=1.0,
        max_value=60.0,
        value=10.0,
        step=1.0,
        help="다운로드 요청 timeout(초)입니다.",
    )
    fixture_base_dir = _fixture_base_dir_sidebar()

    st.sidebar.divider()
    st.sidebar.link_button("data.go.kr 상세 페이지 열기", entry.detail_url, width="stretch")
    if entry.url:
        st.sidebar.link_button("다운로드 URL 열기", entry.url, width="stretch")

    _info_row(entry, dataset)

    operations = dataset_operations(dataset)
    operation: DatasetOperation | None = None
    if operations:
        operation_labels = [op.label for op in operations]
        selected_operation_label = st.selectbox(
            "Operation",
            operation_labels,
            key=f"operation-select:{dataset.key}",
        )
        operation = operations[operation_labels.index(selected_operation_label)]
        st.caption(operation.description)
    else:
        st.warning(
            "검증된 download_url이 없어 실행 가능한 오퍼레이션이 없습니다 "
            f"(verification_status={entry.verification_status})."
        )

    tabs = st.tabs(list(TAB_LABELS))
    with tabs[0]:
        _raw_response_tab(dataset, entry, operation, env, float(timeout))
    with tabs[1]:
        _pydantic_model_tab(dataset, operation)
    with tabs[2]:
        _processed_result_tab(dataset, operation)
    with tabs[3]:
        _validation_errors_tab(dataset, operation)
    with tabs[4]:
        _debug_trace_tab(entries, dataset, operation, env, float(timeout), fixture_base_dir)
    with tabs[5]:
        _fixture_tab(dataset, operation, fixture_base_dir)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _entry_label(entry: CatalogEntry) -> str:
    return f"{entry.dataset_name} | {entry.dataset_id} | {entry.verification_status}"


def _returns_caption(dataset: FileDataset) -> str:
    formats = ", ".join(dataset.formats) or "n/a"
    geometry = dataset.geometry_type or "no geometry"
    return (
        f"반환: {formats} 파일 · geometry={geometry} · "
        f"feature={dataset.feature_kind or 'n/a'} · update={dataset.update_cycle or 'n/a'}"
    )


def _environment_sidebar() -> dict[str, str]:
    st.sidebar.subheader("Environment (RustFS)")
    st.sidebar.caption(
        "download_to_rustfs 오퍼레이션에만 필요합니다. 이 저장소는 서비스키가 없는 "
        "파일 카탈로그라 템플릿의 Auth 섹션은 생략합니다."
    )
    mode = st.sidebar.radio(
        "RustFS credentials",
        ["env", "manual"],
        horizontal=True,
        help="env: KnpsClient가 환경 변수로 읽음 · manual: 이 화면에서 직접 입력",
    )

    values: dict[str, str] = {
        "mode": str(mode),
        "endpoint_url": "",
        "bucket": "",
        "access_key": "",
        "secret_key": "",
        "region": "",
    }
    if mode == "env":
        endpoint_env = _first_set_env(_RUSTFS_ENDPOINT_ENV_NAMES)
        if endpoint_env is not None:
            st.sidebar.caption(f"env var 사용 중: {endpoint_env}")
        else:
            st.sidebar.caption(
                "감지된 RustFS env var가 없습니다. 후보: "
                + ", ".join(_RUSTFS_ENDPOINT_ENV_NAMES)
            )
        return values

    values["endpoint_url"] = st.sidebar.text_input(
        "RustFS endpoint URL", placeholder="https://rustfs.example.com"
    )
    values["bucket"] = st.sidebar.text_input("RustFS bucket", placeholder="knps")
    values["access_key"] = st.sidebar.text_input(
        "RustFS access key", type="password", help=", ".join(_RUSTFS_ACCESS_KEY_ENV_NAMES)
    )
    values["secret_key"] = st.sidebar.text_input(
        "RustFS secret key", type="password", help=", ".join(_RUSTFS_SECRET_KEY_ENV_NAMES)
    )
    values["region"] = st.sidebar.text_input("RustFS region", placeholder="us-east-1")
    st.sidebar.caption("수동 입력 값을 사용합니다 (비워둔 필드는 env var로 fallback).")
    return values


def _first_set_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip():
            return name
    return None


def _fixture_base_dir_sidebar() -> str:
    st.sidebar.subheader("Fixtures")
    candidates = _fixture_dir_candidates()
    options = [str(path) for path in candidates]
    custom_label = "Custom..."
    selected = st.sidebar.selectbox("Fixture base dir", [*options, custom_label])
    if selected == custom_label:
        selected = st.sidebar.text_input(
            "Custom fixture base dir",
            value=str((ROOT / "tests" / "fixtures").resolve()),
        )
    st.sidebar.caption(selected)
    return str(selected)


def _fixture_dir_candidates() -> list[Path]:
    preferred = [
        ROOT / "tests" / "fixtures",
        ROOT / "tests",
        ROOT / "examples",
        ROOT,
    ]
    candidates: list[Path] = []
    for path in preferred:
        resolved = path.resolve()
        if resolved not in candidates:
            candidates.append(resolved)
    return candidates


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------


def _info_row(entry: CatalogEntry, dataset: FileDataset) -> None:
    columns = st.columns([1.4, 1, 1, 1, 1, 1])
    columns[0].caption("Dataset")
    columns[0].write(entry.dataset_name)
    columns[1].caption("data.go.kr ID")
    columns[1].write(entry.dataset_id)
    columns[2].caption("Provider")
    columns[2].write(entry.provider)
    columns[3].caption("Status")
    columns[3].write(entry.verification_status)
    columns[4].caption("Formats")
    columns[4].write(", ".join(dataset.formats) or "n/a")
    columns[5].caption("Geometry")
    columns[5].write(dataset.geometry_type or "n/a")


# ---------------------------------------------------------------------------
# Operation form (카탈로그 메타데이터에서 위젯 자동 생성 — 오퍼레이션/dataset별
# 하드코딩 분기 없음)
# ---------------------------------------------------------------------------


def _render_operation_form(
    dataset: FileDataset,
    operation: DatasetOperation,
    *,
    key_prefix: str,
) -> tuple[bool, dict[str, Any], list[str]]:
    with st.form(f"run-form:{key_prefix}"):
        params = operation.params
        raw_values: dict[str, str | bool] = {}
        if not params:
            st.caption("이 오퍼레이션에는 추가 파라미터가 없습니다.")
        for index in range(0, len(params), 2):
            columns = st.columns(2)
            for column, param in zip(columns, params[index : index + 2], strict=False):
                with column:
                    raw_values[param.name] = _render_param_widget(dataset, param, key_prefix)
        submitted = st.form_submit_button("Run operation")

    kwargs = resolve_operation_kwargs(operation, dataset, raw_values)
    missing = [param.name for param in params if param.required and param.name not in kwargs]
    return submitted, kwargs, missing


def _render_param_widget(
    dataset: FileDataset,
    param: OperationParam,
    key_prefix: str,
) -> str | bool:
    default = param.default.replace("{dataset_key}", dataset.key)
    widget_key = f"{key_prefix}:param:{param.name}"
    label = f"{param.name} *" if param.required else param.name
    if param.kind == "bool":
        return st.checkbox(
            label,
            value=default.strip().lower() == "true",
            help=param.help or None,
            key=widget_key,
        )
    return st.text_input(
        label,
        value=default,
        help=param.help or None,
        key=widget_key,
    )


def _execute(
    dataset: FileDataset,
    operation: DatasetOperation,
    kwargs: dict[str, Any],
    env: dict[str, str],
    timeout: float,
) -> DebugRun:
    try:
        client = KnpsClient(timeout=timeout)
        if env["mode"] == "manual":
            client.config = KnpsConfig.from_env(
                timeout=timeout,
                max_rps=client.config.max_rps,
                rustfs_endpoint_url=env["endpoint_url"] or None,
                rustfs_bucket=env["bucket"] or None,
                rustfs_access_key=env["access_key"] or None,
                rustfs_secret_key=env["secret_key"] or None,
                rustfs_region=env["region"] or None,
            )
    except Exception as exc:  # pragma: no cover - UI 표시
        return DebugRun(
            function=operation.key,
            input=redact_sensitive(
                {"dataset_key": dataset.key, "operation": operation.key, "kwargs": kwargs}
            ),
            request={},
            response={},
            parsed=None,
            processed=None,
            trace=[f"client 초기화 실패: {exc.__class__.__name__}"],
            error=debug_error(exc),
        )
    return run_dataset_operation(client, dataset.key, operation, kwargs)


def _raw_response_tab(
    dataset: FileDataset,
    entry: CatalogEntry,
    operation: DatasetOperation | None,
    env: dict[str, str],
    timeout: float,
) -> None:
    st.subheader(dataset.title)
    st.caption(f"{dataset.provider} · data.go.kr {dataset.data_go_id} · {entry.detail_url}")

    if operation is None:
        st.info("실행 가능한 오퍼레이션이 없습니다. 위 경고를 참고하세요.")
        return

    key_prefix = f"{dataset.key}:{operation.key}"
    submitted, kwargs, missing = _render_operation_form(dataset, operation, key_prefix=key_prefix)

    st.subheader("Request kwargs preview")
    st.json(jsonable(redact_sensitive(kwargs)))

    if not submitted:
        return
    if missing:
        st.error("필수 파라미터를 입력하세요: " + ", ".join(missing))
        return

    run = _execute(dataset, operation, kwargs, env, timeout)
    _store_run(dataset.key, operation.key, run)

    if run.error:
        st.error(f"{run.error['type']}: {run.error['message']}")
    else:
        st.success(f"실행 성공 ({run.response.get('elapsed_ms', '?')}ms)")

    st.caption(
        "이 API는 JSON envelope가 아니라 파일 bytes를 반환하므로, Raw Response는 "
        "다운로드/파싱 실행 결과 요약입니다 — 파싱된 값은 Pydantic Model/Processed "
        "Result 탭에서 확인하세요."
    )
    st.json(jsonable(run.response))


def _pydantic_model_tab(dataset: FileDataset, operation: DatasetOperation | None) -> None:
    run = _current_run(dataset.key, operation)
    if run is None:
        st.info("Raw Response 탭에서 오퍼레이션을 실행하면 여기에서 Pydantic 모델을 확인합니다.")
        return
    if run.error:
        st.warning("실행 중 오류가 있습니다. Validation Errors 탭을 확인하세요.")
        return
    st.json(jsonable(run.parsed))


def _processed_result_tab(dataset: FileDataset, operation: DatasetOperation | None) -> None:
    run = _current_run(dataset.key, operation)
    if run is None:
        st.info("Raw Response 탭에서 오퍼레이션을 실행하면 처리된 결과 preview를 표시합니다.")
        return
    if run.error:
        st.warning("실행 중 오류가 있습니다. Validation Errors 탭을 확인하세요.")
        return
    data = jsonable(run.processed)
    if isinstance(data, list) and data:
        st.dataframe(pd.json_normalize(data, sep="."), width="stretch", hide_index=True)
    else:
        st.json(data)


def _validation_errors_tab(dataset: FileDataset, operation: DatasetOperation | None) -> None:
    run = _current_run(dataset.key, operation)
    if run is None:
        st.info("아직 실행된 오퍼레이션이 없습니다.")
        return
    if not run.error:
        st.success("현재 실행 결과에서 validation error 또는 exception이 없습니다.")
        return
    st.error(f"{run.error['type']}: {run.error['message']}")
    st.json(run.error)


def _debug_trace_tab(
    entries: tuple[CatalogEntry, ...],
    dataset: FileDataset,
    operation: DatasetOperation | None,
    env: dict[str, str],
    timeout: float,
    fixture_base_dir: str,
) -> None:
    st.subheader("Catalog")
    st.dataframe(_catalog_dataframe(entries), width="stretch", hide_index=True)

    st.subheader("Selected dataset")
    st.json(jsonable(dataset))
    st.caption(
        f"RustFS credentials: {env['mode']} · timeout={timeout}s · "
        f"fixture base dir={fixture_base_dir}"
    )

    run = _current_run(dataset.key, operation)
    if run is None:
        st.info("아직 실행된 오퍼레이션이 없습니다.")
        return

    st.subheader("Trace")
    st.write(run.trace)
    st.subheader("Request (masked)")
    st.json(jsonable(run.request))
    if run.catalog is not None:
        st.subheader("Dataset catalog snapshot")
        st.json(run.catalog)


def _catalog_dataframe(entries: tuple[CatalogEntry, ...]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        payload = entry.model_dump(mode="json")
        payload["categories"] = ", ".join(entry.categories)
        payload["formats"] = ", ".join(entry.formats)
        rows.append(payload)
    return pd.DataFrame(rows)


def _fixture_tab(
    dataset: FileDataset,
    operation: DatasetOperation | None,
    fixture_base_dir: str,
) -> None:
    run = _current_run(dataset.key, operation)
    if run is None or operation is None:
        st.info("Raw Response 탭에서 오퍼레이션을 실행한 뒤 fixture를 저장할 수 있습니다.")
        st.caption("Fixture base dir")
        st.code(fixture_base_dir, language=None)
        return

    function_name = f"{dataset.key}__{operation.key}"
    with st.expander("Save as fixture", expanded=True):
        case_name = st.text_input("Case name", value=f"{function_name}_normal")
        description = st.text_area(
            "Description", value=f"{dataset.title} / {operation.label} 정상 케이스"
        )
        assertion_mode = st.selectbox(
            "Assertion mode",
            ["snapshot", "schema_only", "required_fields", "count"],
        )
        exclude_fields_raw = st.text_input(
            "Exclude fields",
            value="fetched_at, request_id, updated_at",
        )
        required_fields_raw = st.text_input("Required fields", value="")
        overwrite = st.checkbox("Overwrite existing fixture", value=False)

        assertion = {
            "mode": assertion_mode,
            "exclude_fields": [
                value.strip() for value in exclude_fields_raw.split(",") if value.strip()
            ],
            "required_fields": [
                value.strip() for value in required_fields_raw.split(",") if value.strip()
            ],
        }

        st.subheader("Fixture preview")
        st.json(
            {
                "function": function_name,
                "input": jsonable(run.input),
                "request": jsonable(run.request),
                "response": jsonable(run.response),
                "processed": jsonable(run.processed),
                "assertion": assertion,
            }
        )

        if st.button("Save as fixture"):
            try:
                path = save_fixture(
                    base_dir=fixture_base_dir,
                    function_name=function_name,
                    case_name=case_name,
                    description=description,
                    input_data=run.input,
                    request_data=run.request,
                    response_data=run.response,
                    parsed_result=run.parsed,
                    processed_result=run.processed,
                    assertion=assertion,
                    overwrite=overwrite,
                )
            except Exception as exc:  # pragma: no cover - UI 표시
                st.error(str(exc))
            else:
                st.success(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Session state (데이터셋:오퍼레이션 별로 scope — 다른 조합으로 전환해도
# 이전 실행 결과가 사라지지 않는다)
# ---------------------------------------------------------------------------


def _run_key(dataset_key: str, operation_key: str) -> str:
    return f"{dataset_key}:{operation_key}"


def _store_run(dataset_key: str, operation_key: str, run: DebugRun) -> None:
    runs = st.session_state.setdefault(_SESSION_RUNS_KEY, {})
    runs[_run_key(dataset_key, operation_key)] = run


def _current_run(dataset_key: str, operation: DatasetOperation | None) -> DebugRun | None:
    if operation is None:
        return None
    runs = st.session_state.get(_SESSION_RUNS_KEY)
    if not isinstance(runs, dict):
        return None
    run = runs.get(_run_key(dataset_key, operation.key))
    return run if isinstance(run, DebugRun) else None


if __name__ == "__main__":
    main()
