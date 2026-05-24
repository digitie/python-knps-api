from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any, TypeAlias, cast

import pandas as pd
import streamlit as st
from pydantic import BaseModel

from knps import KnpsApiError, KnpsClient
from knps.catalog import api_endpoint, catalog_entries, file_dataset
from knps.config import DEFAULT_ENV_NAME, KNPS_ENV_NAME
from knps.models import ApiEndpoint, CatalogEntry, Page, RawRecord

RunState: TypeAlias = dict[str, Any]


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def normalize_service_key(value: str | None) -> str | None:
    if value is None:
        return None
    key = "".join(str(value).split())
    return key or None


def resolve_service_key() -> str:
    return (
        normalize_service_key(os.getenv(KNPS_ENV_NAME))
        or normalize_service_key(os.getenv(DEFAULT_ENV_NAME))
        or ""
    )


def entry_option_label(entry: CatalogEntry) -> str:
    status = entry.verification_status
    dataset_id = entry.dataset_id or "TBD"
    return f"{entry.display_name} | {dataset_id} | {status}"


def entries_dataframe(entries: tuple[CatalogEntry, ...]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        payload = entry.model_dump(mode="json")
        payload["categories"] = ", ".join(entry.categories)
        payload["formats"] = ", ".join(entry.formats)
        rows.append(payload)
    return pd.DataFrame(rows)


def result_items_dataframe(result: Page[RawRecord]) -> pd.DataFrame:
    rows = [jsonable(item) for item in result.items]
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows, sep=".")


def parse_extra_parameters(text: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Line {line_number} must use key=value format.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Line {line_number} is missing a parameter name.")
        params[key] = value
    return params


def render_extra_parameters(*, key_prefix: str) -> dict[str, str]:
    with st.expander("Additional request parameters"):
        raw_params = st.text_area(
            "Query parameters",
            key=f"{key_prefix}:extra-params",
            placeholder="baseYm=202501\nparkCd=01",
            help="Enter one key=value pair per line. Blank lines and # comments are ignored.",
        )
    return parse_extra_parameters(raw_params)


async def run_api_request(
    *,
    api_key: str,
    endpoint: ApiEndpoint,
    params: dict[str, Any],
    page_no: int,
    num_of_rows: int,
    response_format: str | None,
    timeout: float,
    max_rps: float,
) -> Page[RawRecord]:
    async with KnpsClient(
        api_key=api_key,
        timeout=timeout,
        max_rps=max_rps,
    ) as client:
        return await client.raw_endpoint(
            endpoint.key,
            params,
            page_no=page_no,
            num_of_rows=num_of_rows,
            response_format=response_format,
        )


def flatten_mapping_keys(value: Mapping[str, Any], *, prefix: str = "") -> list[str]:
    keys: list[str] = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            keys.extend(flatten_mapping_keys(item, prefix=path))
        else:
            keys.append(path)
    return keys


def build_trace(
    *,
    selected_entry: CatalogEntry,
    service_key_input: str,
    normalized_key: str | None,
    params: dict[str, Any],
    page_no: int,
    num_of_rows: int,
) -> list[str]:
    return [
        f"kind={selected_entry.kind}",
        f"key={selected_entry.key}",
        f"dataset_name={selected_entry.dataset_name}",
        f"dataset_id={selected_entry.dataset_id or 'TBD'}",
        f"provider={selected_entry.provider}",
        f"verification_status={selected_entry.verification_status}",
        f"env_precedence={KNPS_ENV_NAME} > {DEFAULT_ENV_NAME}",
        f"service_key_present={bool(normalized_key)}",
        "service_key_whitespace_normalized="
        f"{bool(service_key_input and normalized_key != service_key_input)}",
        f"params={params}",
        f"page_no={page_no}",
        f"num_of_rows={num_of_rows}",
    ]


def store_run_state(
    *,
    result: Page[RawRecord] | None,
    error: dict[str, Any] | None,
    trace: list[str],
    request_params: dict[str, Any],
    page_no: int,
    num_of_rows: int,
    selected_entry: CatalogEntry,
) -> None:
    st.session_state["last_run"] = {
        "result": result,
        "error": error,
        "trace": trace,
        "request_params": request_params,
        "page_no": page_no,
        "num_of_rows": num_of_rows,
        "selected_entry": selected_entry,
    }


def last_run_state() -> RunState | None:
    return cast(RunState | None, st.session_state.get("last_run"))


st.set_page_config(page_title="KNPS API Workbench", layout="wide")

if "last_run" not in st.session_state:
    st.session_state["last_run"] = None

catalog = catalog_entries()
entry_options = {entry_option_label(entry): entry for entry in catalog}

st.title("KNPS API Workbench")
st.caption("Catalog-first debug UI for KNPS public APIs and file datasets.")

with st.sidebar:
    st.header("Request")
    selected_label = st.selectbox("Dataset", list(entry_options))
    selected_entry = entry_options[selected_label]

    st.divider()
    st.subheader("Service key")
    default_key = resolve_service_key()
    service_key_input = st.text_input(
        "Service key",
        value=default_key,
        type="password",
        placeholder="Loaded from environment when available",
        help="Whitespace from copy-paste is removed before requests.",
    )
    normalized_key = normalize_service_key(service_key_input)
    if service_key_input and normalized_key != service_key_input:
        st.caption("Copy-paste whitespace will be removed before the request.")
    st.caption(f"Env precedence: {KNPS_ENV_NAME} > {DEFAULT_ENV_NAME}")

    st.divider()
    timeout = st.number_input("Timeout seconds", min_value=1.0, max_value=120.0, value=10.0)
    max_rps = st.number_input("Max RPS", min_value=0.1, max_value=30.0, value=5.0)

    st.divider()
    st.link_button("Open detail page", selected_entry.detail_url, use_container_width=True)
    if selected_entry.kind == "file_dataset" and selected_entry.url:
        st.link_button("Open download URL", selected_entry.url, use_container_width=True)

info_cols = st.columns([1.5, 1, 1, 1, 1])
info_cols[0].caption("Dataset")
info_cols[0].write(selected_entry.dataset_name)
info_cols[1].caption("Kind")
info_cols[1].write(selected_entry.kind)
info_cols[2].caption("Provider")
info_cols[2].write(selected_entry.provider)
info_cols[3].caption("Dataset ID")
info_cols[3].write(selected_entry.dataset_id or "TBD")
info_cols[4].caption("Status")
info_cols[4].write(selected_entry.verification_status)

st.subheader(selected_entry.display_name)
st.write(selected_entry.description)

if selected_entry.kind == "api":
    selected_endpoint = api_endpoint(selected_entry.key)
    if selected_endpoint.verification_status == "planned":
        st.warning(
            "This endpoint is planned but not verified. The dataset ID and operation are still "
            "catalog placeholders, so request execution is disabled until live verification."
        )
    elif selected_endpoint.verification_status == "needs_verification":
        st.warning(
            "This endpoint has not been live-verified. It may return 404 or a data.go.kr "
            "result-code error if the guessed endpoint is no longer available."
        )
    endpoint_cols = st.columns(3)
    endpoint_cols[0].caption("Service")
    endpoint_cols[0].write(selected_endpoint.service)
    endpoint_cols[1].caption("Operation")
    endpoint_cols[1].write(selected_endpoint.operation)
    endpoint_cols[2].caption("Response")
    endpoint_cols[2].write(selected_endpoint.response_format or "json")

    with st.form("request_form"):
        param_col, option_col = st.columns([3, 1])
        with param_col:
            form_params = render_extra_parameters(key_prefix=selected_endpoint.key)
        page_no = option_col.number_input("pageNo", min_value=1, value=1)
        num_of_rows = option_col.number_input(
            "numOfRows",
            min_value=1,
            max_value=1000,
            value=10,
        )
        response_options = ["catalog default", "json", "xml"]
        response_choice = option_col.selectbox("Response format", response_options)
        response_format = None if response_choice == "catalog default" else response_choice
        run_clicked = st.form_submit_button(
            "Run request",
            type="primary",
            use_container_width=True,
            disabled=selected_endpoint.verification_status == "planned",
        )

    if run_clicked:
        trace = build_trace(
            selected_entry=selected_entry,
            service_key_input=service_key_input,
            normalized_key=normalized_key,
            params=form_params,
            page_no=int(page_no),
            num_of_rows=int(num_of_rows),
        )
        result: Page[RawRecord] | None = None
        error: dict[str, Any] | None = None
        try:
            if not normalized_key:
                raise ValueError("Service key is required.")
            result = asyncio.run(
                run_api_request(
                    api_key=normalized_key,
                    endpoint=selected_endpoint,
                    params=form_params,
                    page_no=int(page_no),
                    num_of_rows=int(num_of_rows),
                    response_format=response_format,
                    timeout=float(timeout),
                    max_rps=float(max_rps),
                )
            )
            trace.append(f"items={len(result.items)}")
            trace.append(f"total_count={result.total_count}")
        except KnpsApiError as exc:
            error = {"type": type(exc).__name__, "message": str(exc), "metadata": exc.metadata}
            trace.append(f"error={type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001 - debug UI must surface input/runtime issues.
            error = {"type": type(exc).__name__, "message": str(exc)}
            trace.append(f"error={type(exc).__name__}")

        store_run_state(
            result=result,
            error=error,
            trace=trace,
            request_params=form_params,
            page_no=int(page_no),
            num_of_rows=int(num_of_rows),
            selected_entry=selected_entry,
        )
else:
    dataset = file_dataset(selected_entry.key)
    file_cols = st.columns(4)
    file_cols[0].caption("Formats")
    file_cols[0].write(", ".join(dataset.formats) or "n/a")
    file_cols[1].caption("Feature kind")
    file_cols[1].write(dataset.feature_kind or "n/a")
    file_cols[2].caption("Geometry")
    file_cols[2].write(dataset.geometry_type or "n/a")
    file_cols[3].caption("Update")
    file_cols[3].write(dataset.update_cycle or "n/a")
    st.info(
        "This catalog item is a file dataset. Direct download is available after "
        "download_url verification."
    )

last_run = last_run_state()
last_result = cast(Page[RawRecord] | None, last_run["result"] if last_run else None)
last_error = cast(dict[str, Any] | None, last_run["error"] if last_run else None)
last_run_entry = cast(CatalogEntry | None, last_run["selected_entry"] if last_run else None)
last_run_is_stale = bool(last_run_entry and last_run_entry.key != selected_entry.key)

if last_run_is_stale:
    st.warning(
        "Showing the previous request result. Run the newly selected dataset to refresh "
        "Response, Table, Debug Trace, and Fixture tabs."
    )

if last_error:
    st.error(f"{last_error['type']}: {last_error['message']}")
elif last_result is not None:
    st.success(f"{len(last_result.items)} items, total_count={last_result.total_count}")
else:
    st.info("Select an API dataset and run a request.")

response_tab, table_tab, trace_tab, catalog_tab, fixture_tab = st.tabs(
    ["Response", "Table", "Debug Trace", "Catalog", "Fixture / Testcase"]
)

with response_tab:
    if last_result is not None:
        raw_col, model_col = st.columns(2)
        raw_col.subheader("Raw response")
        raw_col.json(jsonable(last_result.raw))
        model_col.subheader("Pydantic model")
        model_col.json(jsonable(last_result))
    elif last_error is not None:
        st.json(last_error)
    else:
        st.info("Run an API call to see the response.")

with table_tab:
    if last_result is not None:
        result_df = result_items_dataframe(last_result)
        if result_df.empty:
            st.info("No items returned.")
        else:
            st.dataframe(result_df, use_container_width=True, hide_index=True)
    else:
        st.info("Run an API call to see rows.")

with trace_tab:
    st.subheader("Current catalog item")
    st.json(jsonable(selected_entry))
    if last_run_entry is not None:
        st.subheader("Last run catalog item")
        st.json(jsonable(last_run_entry))
    st.subheader("Trace")
    trace = last_run["trace"] if last_run is not None else []
    st.code("\n".join(trace), language="text")

with catalog_tab:
    query = st.text_input("Filter catalog", placeholder="dataset, provider, status")
    catalog_df = entries_dataframe(catalog)
    if query:
        lowered = query.lower()
        mask = catalog_df.apply(
            lambda row: row.astype(str).str.lower().str.contains(lowered).any(),
            axis=1,
        )
        catalog_df = catalog_df[mask]
    st.dataframe(catalog_df, use_container_width=True, hide_index=True)

with fixture_tab:
    if last_result is None and last_error is None:
        st.info("Run an API call to create a fixture summary.")
    else:
        assert last_run is not None
        fixture_entry = cast(CatalogEntry, last_run["selected_entry"])
        fixture = {
            "kind": fixture_entry.kind,
            "key": fixture_entry.key,
            "dataset_name": fixture_entry.dataset_name,
            "params": last_run["request_params"],
            "page_no": last_run["page_no"],
            "num_of_rows": last_run["num_of_rows"],
            "error": last_error,
        }
        if last_result is not None:
            first_item = jsonable(last_result.items[0]) if last_result.items else {}
            fixture["result"] = {
                "item_count": len(last_result.items),
                "total_count": last_result.total_count,
                "first_item_keys": (
                    sorted(flatten_mapping_keys(first_item)) if isinstance(first_item, dict) else []
                ),
            }
        st.json(fixture)
