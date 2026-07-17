"""Source-aware Streamlit ingestion and harmonization page."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from chronotome_core import run_ingestion
from chronotome_core.export import dataframe_csv
from chronotome_core.io import InputError, inspect_source_uploads
from chronotome_core.runner import DEFAULT_CONFIG
from chronotome_ui.navigation import navigate_to_page
from chronotome_ui.state import clear_downstream_state


def _as_list(uploaded):
    if uploaded is None:
        return []
    return uploaded if isinstance(uploaded, list) else [uploaded]


def _signature(scopus_files, wos_files, modes):
    return (
        tuple((item.name, getattr(item, "size", len(item.getvalue()))) for item in scopus_files),
        tuple((item.name, getattr(item, "size", len(item.getvalue()))) for item in wos_files),
        modes["Scopus"], modes["WoS"],
    )


def _source_uploader(source: str, enabled: bool):
    if not enabled:
        return [], "single"
    mode_label = st.radio(
        f"{source} ingestion mode", ["Single file", "Appendage (split export)"],
        horizontal=True, key=f"{source.lower()}_mode",
        help="Appendage stacks numbered parts of one export series before harmonization.",
    )
    mode = "appendage" if mode_label.startswith("Appendage") else "single"
    if mode == "single":
        uploaded = st.file_uploader(
            f"Upload one {source} export", type=["csv", "txt", "xls", "xlsx"],
            accept_multiple_files=False, key=f"{source.lower()}_single_upload",
        )
    else:
        uploaded = st.file_uploader(
            f"Upload numbered {source} parts", type=["csv", "txt", "xls", "xlsx"],
            accept_multiple_files=True, key=f"{source.lower()}_append_upload",
            help="Example: export_1.csv, export_2.csv, export_3.csv",
        )
        st.caption("Files must share one base name and extension and end in `_1`, `_2`, `_3`, …")
    return _as_list(uploaded), mode


def _show_verification(source: str, verification: dict):
    summary = verification["summary"]
    st.markdown(f"### {source} verification")
    cols = st.columns(5)
    cols[0].metric("Files", summary["Files"])
    cols[1].metric("Records", f"{summary['Records']:,}")
    cols[2].metric("Columns", summary["Columns (union)"])
    cols[3].metric("Year range", summary["Year range"])
    cols[4].metric("DOI coverage", summary["DOI coverage"])
    st.dataframe(verification["files"], width="stretch", hide_index=True)
    signal_table = pd.DataFrame([
        ("Titles present", f"{summary['Titles present']:,}"),
        ("Affiliation coverage", summary["Affiliation coverage"]),
        ("Raw duplicate DOI rows", f"{summary['Raw duplicate DOI rows']:,}"),
        ("Mode", summary["Mode"]),
    ], columns=["Signal", "Detected value"])
    st.dataframe(signal_table, width="stretch", hide_index=True)
    for warning in verification["warnings"]:
        st.warning(warning)
    if not verification["warnings"]:
        st.success(f"{source} files are ordered, readable, and schema-compatible.")
    if summary["Mode"] == "Appendage":
        st.download_button(
            f"Download verified stitched {source} CSV",
            verification["stitched_csv"],
            f"stitched_{source.lower().replace(' ', '_')}_export.csv",
            "text/csv", key=f"verified-stitched-{source}",
        )


def _compact_verification(verification: dict) -> dict:
    """Retain display metadata and one portable stitched export, not raw frames."""
    compact = {
        "files": verification["files"],
        "summary": dict(verification["summary"]),
        "warnings": list(verification["warnings"]),
    }
    if compact["summary"]["Mode"] == "Appendage":
        compact["stitched_csv"] = dataframe_csv(verification["combined"])
    return compact


def render_ingestion():
    """Render configuration, verification, harmonization, PRISMA, and exports."""
    st.title("Data Ingestion, Preprocessing and Harmonization")
    st.markdown(
        "Load **Scopus** and/or **Web of Science (WoS)** exports, "
        "stitches split exports when requested, harmonizes their metadata, and deduplicates "
        "the merged corpus."
    )
    st.info(
        "Chronotome checks file content, delimiters, Excel formats, and Web of Science tab-delimited "
        "files before records are merged."
    )

    with st.expander("How Single file and Appendage modes work", expanded=False):
        st.markdown(
            """
**Single file** is for one complete export from a source.

**Appendage** is for one export split by a database limit. Chronotome only stacks files that:

- follow `NAME_1.ext`, `NAME_2.ext`, `NAME_3.ext`, …;
- share the same base name and extension;
- belong to the same source uploader.

Appendage does not merge Scopus with WoS and does not silently combine differently named query series. Files are sorted by their numeric suffix, not browser upload order.
            """
        )

    st.markdown("## 1. Choose sources and ingestion modes")
    selected_sources = st.multiselect(
        "Which database exports do you have?", ["Scopus", "Web of Science"],
        default=["Scopus", "Web of Science"],
    )
    left, right = st.columns(2)
    with left:
        st.markdown("### Scopus")
        st.caption("CSV recommended; TXT, XLS, and XLSX are also accepted.")
        scopus_files, scopus_mode = _source_uploader("Scopus", "Scopus" in selected_sources)
    with right:
        st.markdown("### Web of Science")
        st.caption("Tab-delimited TXT/CSV, Excel, and WoS `.xls` text anomalies are supported.")
        wos_files, wos_mode = _source_uploader("WoS", "Web of Science" in selected_sources)

    modes = {"Scopus": scopus_mode, "WoS": wos_mode}
    current_signature = _signature(scopus_files, wos_files, modes)
    any_files = bool(scopus_files or wos_files)

    st.markdown("## 2. Verify uploads")
    st.caption(
        "Verification checks source identity, parser route, title fields, schema coverage, "
        "appendage order, missing parts, DOI coverage, years, affiliations, and duplicate-file signals."
    )
    if st.button("Verify uploaded files", type="primary", disabled=not any_files):
        try:
            with st.spinner("Reading files and checking ingestion signals…"):
                verification = {}
                if scopus_files:
                    details = inspect_source_uploads(scopus_files, "Scopus", scopus_mode)
                    verification["Scopus"] = _compact_verification(details)
                if wos_files:
                    details = inspect_source_uploads(wos_files, "WoS", wos_mode)
                    verification["WoS"] = _compact_verification(details)
            st.session_state["ingestion_verification"] = verification
            st.session_state["ingestion_signature"] = current_signature
            st.session_state.pop("ingestion_results", None)
        except (InputError, ValueError) as exc:
            st.session_state.pop("ingestion_verification", None)
            st.error(str(exc))
        except Exception as exc:
            st.session_state.pop("ingestion_verification", None)
            st.error(f"A file could not be verified: {exc}")

    verification = st.session_state.get("ingestion_verification")
    verified_current = verification is not None and st.session_state.get("ingestion_signature") == current_signature
    if verification and not verified_current:
        st.warning("The upload configuration changed. Verify the current files again before harmonization.")
    if verified_current:
        for source, details in verification.items():
            _show_verification(source, details)

    st.markdown("## 3. Harmonize and deduplicate")
    rules_tab, schema_tab, linkage_tab, time_tab = st.tabs(
        ["Preprocessing rules", "Unified schema", "Record linkage", "Temporal cutoff"]
    )
    with rules_tab:
        st.markdown(
            """
#### Deterministic cleaning rules

- **Scopus authors:** split on semicolons, trim whitespace, and join with `; `.
- **WoS authors:** prefer semicolons; use commas only when no semicolon is present; join with `; `.
- **Scopus internal IDs:** remove numeric parenthetical codes such as `(57211158827)` from full names.
- **Cited references:** retain the original Scopus `References` or WoS `CR` text as `Cited References Raw`; when no valid exported count exists, count its non-empty semicolon-delimited entries separately.

These rules are applied consistently to author counts, collaboration networks, and later indicators.
            """
        )
    with schema_tab:
        st.markdown(
            """
#### Explicit schema mapping

Chronotome uses auditable Scopus → unified and WoS → unified dictionaries. Each final row records the selected primary source in `Primary Database`, every contributing database in the `Databases` list, and every contributing input filename in the `Source Files` list.

The result audit will show every source field, its unified name, whether it was present, its populated-row count, and whether it is retained in the final schema.
            """
        )
    with linkage_tab:
        st.markdown(
            """
#### Prioritized data fusion

1. Sort duplicate candidates by `Cited by` descending, with original row order as the stable tie-breaker.
2. Normalize DOI labels and resolver URLs, Unicode, case, whitespace, and conservative trailing citation punctuation.
3. Keep the most-cited row as the primary record and fill only its missing metadata from other rows in that DOI group.
4. For records without a usable DOI, deduplicate only when both a usable normalized title and publication year are present. Incomplete title-year records remain separate.

The result audit reports both removed records and missing metadata cells recovered from secondary DOI records.
            """
        )
    with time_tab:
        st.markdown(
            """
#### Indexing-lag correction

When enabled, Chronotome keeps only records where `Publication Year < cutoff year`. Use the current system year for automatic operation or provide the collection year for a reproducible manual cutoff. Disable the filter for a pure merge-and-deduplicate export.
            """
        )
    st.markdown("### Ingestion settings")
    set_left, set_mid, set_right = st.columns(3)
    enable_time_filter = set_left.checkbox(
        "Exclude collection year and later", value=bool(DEFAULT_CONFIG["enable_time_filter"]),
        key="ingestion_time_filter",
        help="Use this to avoid incomplete indexing for the current collection year.",
    )
    cutoff_source = set_mid.radio(
        "Cutoff source", ["Manual collection year", "Current system year"],
        disabled=not enable_time_filter, key="ingestion_cutoff_source",
    )
    collection_year = set_right.number_input(
        "Collection / cutoff year", 1900, datetime.now().year + 5, datetime.now().year,
        disabled=not enable_time_filter or cutoff_source == "Current system year",
        key="ingestion_collection_year",
    )
    processing_signature = current_signature + (
        enable_time_filter,
        cutoff_source if enable_time_filter else "Disabled",
        int(collection_year) if enable_time_filter and cutoff_source == "Manual collection year" else None,
    )
    st.write(
        "The harmonization step maps both database schemas to Chronotome's common columns, "
        "keeps the most-cited DOI record as the fusion base, fills its missing metadata from "
        "duplicates, aggregates database and source-file provenance, and checks no-DOI records "
        "only when both normalized title and publication year are available."
    )
    if st.button("Harmonize and deduplicate", type="primary", disabled=not verified_current):
        try:
            with st.spinner("Harmonizing schemas, fusing duplicates, and preparing PRISMA…"):
                new_result = run_ingestion(
                    scopus_files=scopus_files, wos_files=wos_files, modes=modes,
                    config={"enable_time_filter": enable_time_filter,
                            "collection_year": (int(collection_year) if enable_time_filter and
                                                cutoff_source == "Manual collection year" else None)},
                )
                clear_downstream_state("ingestion")
                st.session_state["ingestion_results"] = new_result
                st.session_state["ingestion_result_signature"] = processing_signature
            st.success("Harmonization and deduplication complete.")
        except (InputError, ValueError, KeyError) as exc:
            st.error(f"Chronotome could not complete ingestion: {exc}")
        except Exception as exc:
            st.error(f"The export contains an unexpected value: {exc}")

    results = st.session_state.get("ingestion_results")
    results_current = results is not None and st.session_state.get("ingestion_result_signature") == processing_signature
    if results and not results_current:
        st.warning("Results shown previously belong to another upload configuration. Run harmonization again.")
    if not results_current:
        return

    for warning in results["warnings"]:
        st.warning(warning)
    st.markdown("## 4. Preprocessing results, PRISMA and final dataset")
    cleaning_result_tab, schema_result_tab, dedup_result_tab, temporal_result_tab, prisma_tab, dataset_tab, downloads_tab = st.tabs(
        ["Cleaning audit", "Schema audit", "Deduplication", "Temporal filter", "PRISMA", "Final dataset", "Downloads"]
    )
    with cleaning_result_tab:
        st.markdown("#### Source preprocessing summary")
        st.dataframe(results["preprocessing_audit"]["source_summary"], width="stretch", hide_index=True)
        st.caption(
            "Changed author strings are formatting changes only. Reference counts describe the breadth of the cited intellectual base; they are not a quality metric."
        )
    with schema_result_tab:
        st.markdown("#### Source-to-unified mapping audit")
        mapping = results["preprocessing_audit"]["schema_mapping"]
        database = st.selectbox("Show mapping for", sorted(mapping["Database"].unique()), key="mapping_database")
        st.dataframe(mapping[mapping["Database"] == database], width="stretch", hide_index=True)
        with st.expander("Final ordered unified schema"):
            st.dataframe(results["preprocessing_audit"]["final_schema"], width="stretch", hide_index=True)
    with dedup_result_tab:
        st.markdown("#### Hierarchical deduplication and fusion audit")
        st.dataframe(results["deduplication_audit"]["summary"], width="stretch", hide_index=True)
        st.markdown("#### Matching rules")
        st.dataframe(results["deduplication_audit"]["rules"], width="stretch", hide_index=True)
        enrichment = results["deduplication_audit"]["enrichment_by_column"]
        if enrichment.empty:
            st.info("No missing metadata cells were filled during DOI fusion.")
        else:
            st.markdown("#### Metadata recovered from DOI duplicates")
            st.dataframe(enrichment, width="stretch", hide_index=True)
    with temporal_result_tab:
        st.dataframe(results["temporal_audit"], width="stretch", hide_index=True)
        if not results["config"]["enable_time_filter"]:
            st.warning("The time filter was disabled. The latest year may be incomplete in annual production plots.")
    with prisma_tab:
        st.code(results["prisma_text"], language=None)
        st.dataframe(results["prisma_table"], width="stretch", hide_index=True)
        report = results["prisma"]
        expected = report["merged_total"] - report["removed_by_doi"] - report["removed_by_title_year"] - report["excluded_by_time_filter"]
        if expected == report["final_total"]:
            st.success("PRISMA arithmetic check passed.")
        else:
            st.warning("PRISMA arithmetic requires review; download the duplicate-detail table.")
    with dataset_tab:
        st.metric("Final unique records", f"{len(results['processed_data']):,}")
        st.dataframe(results["processed_data"].head(100), width="stretch", hide_index=True)
        if not results["duplicate_doi_records"].empty:
            with st.expander("DOI duplicate records used in data fusion"):
                st.dataframe(results["duplicate_doi_records"].head(100), width="stretch", hide_index=True)
    with downloads_tab:
        exports = results["exports"]
        st.download_button(
            "Download all ingestion outputs (ZIP)", exports["chronotome_ingestion_outputs.zip"],
            "chronotome_ingestion_outputs.zip", "application/zip", type="primary",
        )
        st.download_button(
            "Download final dataset (CSV)", exports["merged_bibliometric_dataset.csv"],
            "merged_bibliometric_dataset.csv", "text/csv",
        )
        st.download_button(
            "Download final dataset (Excel)", exports["merged_bibliometric_dataset.xlsx"],
            "merged_bibliometric_dataset.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Download PRISMA textual report", exports["prisma_text_report.txt"],
            "prisma_text_report.txt", "text/plain",
        )
        for name, content in exports.items():
            if name.startswith("stitched_") and name.endswith(".csv"):
                st.download_button(f"Download {name}", content, name, "text/csv", key=f"result-{name}")
    if st.button("Continue to institutional and geographic entity resolution", type="primary"):
        navigate_to_page("Entity resolution")
