from __future__ import annotations

import pandas as pd
import streamlit as st
from pydantic import BaseModel

from knps.catalog import catalog_entries, file_dataset
from knps.models import CatalogEntry


def jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def entry_option_label(entry: CatalogEntry) -> str:
    status = entry.verification_status
    dataset_id = entry.dataset_id or "TBD"
    return f"{entry.dataset_name} | {dataset_id} | {status}"


def entries_dataframe(entries: tuple[CatalogEntry, ...]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for entry in entries:
        payload = entry.model_dump(mode="json")
        payload["categories"] = ", ".join(entry.categories)
        payload["formats"] = ", ".join(entry.formats)
        rows.append(payload)
    return pd.DataFrame(rows)


st.set_page_config(page_title="KNPS File Dataset Workbench", layout="wide")

catalog = catalog_entries()
entry_options = {entry_option_label(entry): entry for entry in catalog}

st.title("KNPS File Dataset Workbench")
st.caption("Catalog-first debug UI for KNPS data.go.kr file datasets.")
st.info(
    "KNPS currently has no verified data.go.kr OpenAPI entries in this library. "
    "This workbench intentionally exposes file datasets only."
)

with st.sidebar:
    st.header("Dataset")
    selected_label = st.selectbox("File dataset", list(entry_options))
    selected_entry = entry_options[selected_label]

    st.divider()
    st.link_button("Open data.go.kr detail page", selected_entry.detail_url, width="stretch")
    if selected_entry.url:
        st.link_button("Open download URL", selected_entry.url, width="stretch")

dataset = file_dataset(selected_entry.key)

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

file_cols = st.columns(4)
file_cols[0].caption("Formats")
file_cols[0].write(", ".join(dataset.formats) or "n/a")
file_cols[1].caption("Feature kind")
file_cols[1].write(dataset.feature_kind or "n/a")
file_cols[2].caption("Geometry")
file_cols[2].write(dataset.geometry_type or "n/a")
file_cols[3].caption("Update")
file_cols[3].write(dataset.update_cycle or "n/a")

metadata_tab, catalog_tab, fixture_tab = st.tabs(["Metadata", "Catalog", "Fixture / Testcase"])

with metadata_tab:
    st.json(jsonable(dataset))

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
    st.dataframe(catalog_df, width="stretch", hide_index=True)

with fixture_tab:
    st.json(
        {
            "kind": selected_entry.kind,
            "key": selected_entry.key,
            "dataset_name": selected_entry.dataset_name,
            "data_go_id": selected_entry.dataset_id,
            "formats": list(selected_entry.formats),
            "verification_status": selected_entry.verification_status,
            "detail_url": selected_entry.detail_url,
        }
    )
