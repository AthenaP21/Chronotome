"""Guided institutional and geographic entity-resolution page."""

from __future__ import annotations

import hashlib
import io

import pandas as pd
import streamlit as st

from chronotome_core import run_entity_resolution
from chronotome_ui.state import clear_downstream_state
from chronotome_core.entity_resolution import validate_institution_alias_json


def _read_unified_upload(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    content = uploaded_file.getvalue()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        frame = pd.read_excel(io.BytesIO(content))
    else:
        frame = pd.read_csv(io.BytesIO(content), low_memory=False)
        if frame.shape[1] == 1:
            frame = pd.read_csv(io.BytesIO(content), sep="\t", low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _alias_summary_table(alias_info: dict) -> pd.DataFrame:
    table = pd.DataFrame(alias_info["summary"].items(), columns=["Alias-map measure", "Value"])
    table["Value"] = table["Value"].astype(str)
    return table


def render_entity_resolution():
    """Render dataset selection, JSON validation, resolution, audits, and exports."""
    st.title("Institutional and Geographic Entity Resolution")
    st.markdown(
        "Transform raw affiliation strings into canonical institutions and ISO-consistent countries, "
        "then attach unique institution/country lists and collaboration types to each article."
    )
    st.info(
        "This stage preserves the columns used by Chronotome's country and institutional graphs: "
        "`Institutions_Extracted`, `Countries_Extracted`, `Country_Count`, "
        "`Collaboration_Type`, and `Country_Classification`."
    )

    st.markdown("## 1. Choose the preprocessed dataset")
    ingestion_results = st.session_state.get("ingestion_results")
    has_current = ingestion_results is not None and isinstance(ingestion_results.get("processed_data"), pd.DataFrame)
    choices = ["Use current preprocessed Chronotome dataset"] if has_current else []
    choices.append("Upload a merged Chronotome dataset")
    dataset_choice = st.radio("Dataset source", choices, horizontal=True, key="entity_dataset_source")
    dataset = None
    dataset_signature = None
    if dataset_choice.startswith("Use current"):
        dataset = ingestion_results["processed_data"]
        dataset_signature = ("session", len(dataset), tuple(dataset.columns))
        st.success(f"Using the current preprocessed dataset: {len(dataset):,} articles.")
    else:
        dataset_upload = st.file_uploader(
            "Upload merged_bibliometric_dataset.csv or .xlsx", type=["csv", "xls", "xlsx"],
            key="entity_dataset_upload",
        )
        if dataset_upload:
            try:
                dataset = _read_unified_upload(dataset_upload)
                dataset_signature = (dataset_upload.name, len(dataset_upload.getvalue()),
                                     hashlib.sha256(dataset_upload.getvalue()).hexdigest())
                st.success(f"Loaded {len(dataset):,} articles and {len(dataset.columns):,} columns.")
            except Exception as exc:
                st.error(f"The merged dataset could not be read: {exc}")

    if dataset is not None:
        required = [column for column in ("Affiliations", "Title", "Publication Year", "DOI") if column not in dataset]
        if "Affiliations" in required:
            st.error("The dataset is missing the required `Affiliations` column. Return to preprocessing and check schema mapping.")
            dataset = None
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Articles", f"{len(dataset):,}")
            c2.metric("With affiliations", f"{dataset['Affiliations'].notna().sum():,}")
            c3.metric("Affiliation coverage", f"{dataset['Affiliations'].notna().mean() * 100:.1f}%")
            if required:
                st.warning(f"Optional linking fields missing: {', '.join(required)}")

    st.markdown("## 2. Choose and validate institutions.json")
    alias_choice = st.radio(
        "Institution alias source",
        ["Bundled Zenodo alias map", "Upload an updated institutions.json"],
        horizontal=True, key="entity_alias_source",
    )
    alias_upload = None
    if alias_choice.startswith("Upload"):
        alias_upload = st.file_uploader(
            "Upload institutions.json", type=["json"], key="institution_alias_upload",
            help="Expected structure: canonical institution name → list of aliases.",
        )
        if not alias_upload:
            st.info("Upload the updated JSON to validate it before entity resolution.")

    alias_info = None
    alias_signature = None
    if alias_choice.startswith("Bundled") or alias_upload:
        try:
            alias_info = validate_institution_alias_json(alias_upload)
            alias_signature = (alias_info["name"], hashlib.sha256(alias_info["content"]).hexdigest())
            st.dataframe(_alias_summary_table(alias_info), use_container_width=True, hide_index=True)
            if alias_info["collisions"].empty:
                st.success("Alias map structure is valid and no conflicting lookup keys were found.")
            else:
                st.warning(
                    f"The alias map is valid but contains {len(alias_info['collisions']):,} normalized-key collisions. "
                    "Chronotome keeps the first mapping; review the collision table after processing."
                )
            with st.expander("How custom alias maps are merged with the backup"):
                st.write(
                    "The selected JSON is authoritative. Chronotome loads its canonical names and aliases first. "
                    "The embedded backup may add aliases only for canonicals already present in that JSON; backup-only "
                    "canonical institutions are ignored. Conflicting keys retain the first JSON mapping and are reported."
                )
        except ValueError as exc:
            st.error(str(exc))

    st.markdown("## 3. Resolve institutions and countries")
    with st.expander("Reproducible rules used in this stage"):
        st.markdown(
            """
- Clean HTML entities, bracketed fragments, punctuation, spacing, and diacritics.
- Split article affiliations on semicolons to create one row per affiliation.
- Score comma-separated components to select the most institution-like fragment.
- Expand notebook abbreviations (`Univ` → `University`, `Inst` → `Institute`, etc.).
- Apply complex patterns for Max Planck and CSIC/INTA, then the selected alias lookup.
- Treat the last comma-separated component as the country candidate and standardize it with aliases and `pycountry`.
- Aggregate unique standardized institutions and countries back to the article level.
            """
        )
    ready = dataset is not None and alias_info is not None
    current_signature = (dataset_signature, alias_signature)
    if st.button("Run entity resolution", type="primary", disabled=not ready):
        try:
            with st.spinner("Exploding affiliations and resolving institutions and countries…"):
                result = run_entity_resolution(dataset, alias_json_file=alias_upload)
                clear_downstream_state("entity")
                st.session_state["entity_resolution_results"] = result
                st.session_state["entity_resolution_signature"] = current_signature
            st.success("Institutional and geographic entity resolution complete.")
        except (ValueError, KeyError) as exc:
            st.error(f"Entity resolution could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected affiliation value stopped entity resolution: {exc}")

    results = st.session_state.get("entity_resolution_results")
    results_current = results is not None and st.session_state.get("entity_resolution_signature") == current_signature
    if results and not results_current:
        st.warning("The dataset or alias map changed. Run entity resolution again for the current configuration.")
    if not results_current:
        return
    for warning in results["warnings"]:
        st.warning(warning)

    st.markdown("## 4. Entity-resolution results")
    overview_tab, affiliations_tab, articles_tab, cleaning_tab, aliases_tab, downloads_tab = st.tabs(
        ["Overview", "Affiliation-level table", "Article-level summary", "Cleaning report", "Alias audit", "Downloads"]
    )
    with overview_tab:
        st.dataframe(results["audit"]["summary"], use_container_width=True, hide_index=True)
        left, right = st.columns(2)
        with left:
            st.markdown("#### Most frequent institutions")
            st.dataframe(results["audit"]["institution_frequencies"].head(25), use_container_width=True, hide_index=True)
        with right:
            st.markdown("#### Most frequent countries")
            st.dataframe(results["audit"]["country_frequencies"].head(25), use_container_width=True, hide_index=True)
    with affiliations_tab:
        st.caption(f"Showing the first 200 of {len(results['affiliations']):,} extracted affiliation rows.")
        st.dataframe(results["affiliations"].head(200), use_container_width=True, hide_index=True)
    with articles_tab:
        columns = [column for column in ["Title", "Publication Year", "Countries_Extracted",
                   "Institutions_Extracted", "Country_Count", "Collaboration_Type"]
                   if column in results["article_summary"]]
        st.dataframe(results["article_summary"][columns].head(200), use_container_width=True, hide_index=True)
    with cleaning_tab:
        st.markdown("#### Abbreviation expansions")
        if results["audit"]["abbreviations"].empty:
            st.info("No configured abbreviations were expanded.")
        else:
            st.dataframe(results["audit"]["abbreviations"], use_container_width=True, hide_index=True)
        st.markdown("#### Complex regular-expression patterns")
        st.dataframe(results["audit"]["complex_patterns"], use_container_width=True, hide_index=True)
        st.markdown("#### Unresolved country fragments")
        if results["audit"]["unresolved_countries"].empty:
            st.success("All detected country fragments were standardized.")
        else:
            st.dataframe(results["audit"]["unresolved_countries"], use_container_width=True, hide_index=True)
    with aliases_tab:
        st.markdown("#### Applied institution alias mappings")
        st.dataframe(results["audit"]["aliases"].head(100), use_container_width=True, hide_index=True)
        st.markdown("#### Alias collisions")
        if results["alias_info"]["collisions"].empty:
            st.success("No alias collisions were detected.")
        else:
            st.dataframe(results["alias_info"]["collisions"], use_container_width=True, hide_index=True)
        with st.expander("Backup canonicals ignored because they were absent from the selected JSON"):
            st.dataframe(results["alias_info"]["backup_ignored"], use_container_width=True, hide_index=True)
    with downloads_tab:
        exports = results["exports"]
        st.download_button(
            "Download all entity-resolution outputs (ZIP)",
            exports["chronotome_entity_resolution_outputs.zip"],
            "chronotome_entity_resolution_outputs.zip", "application/zip", type="primary",
        )
        for filename, label, mime in (
            ("exploded_affiliations_list.csv", "Affiliation-level table (CSV)", "text/csv"),
            ("exploded_affiliations_list.xlsx", "Affiliation-level table (Excel)", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("final_article_summary_with_countries.csv", "Article-level summary (CSV)", "text/csv"),
            ("final_article_summary_with_countries.xlsx", "Article-level summary (Excel)", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("active_institutions.json", "Active institutions.json", "application/json"),
        ):
            st.download_button(f"Download {label}", exports[filename], filename, mime, key=f"entity-{filename}")

    if st.button("Continue to corpus characteristics and production trends"):
        st.session_state["_chronotome_navigate_to"] = "Corpus & production"
        st.rerun()
