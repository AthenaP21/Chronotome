"""One-click background execution of the complete modern Chronotome workflow."""

from __future__ import annotations

import hashlib
import gc
from datetime import datetime

import streamlit as st

from chronotome_core import run_all_workflow


def _section(number: int, title: str, caption: str | None = None):
    st.markdown("---")
    st.markdown(f"## {number}. {title}")
    if caption:
        st.caption(caption)


def _files(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _source_upload(source: str):
    mode_label = st.radio(
        f"{source} mode", ["Single file", "Appendage (split export)"],
        horizontal=True, key=f"full-{source}-mode",
    )
    appendage = mode_label.startswith("Appendage")
    uploaded = st.file_uploader(
        f"Upload {source} {'parts' if appendage else 'export'}",
        type=["csv", "txt", "xls", "xlsx"], accept_multiple_files=appendage,
        key=f"full-{source}-upload",
    )
    return _files(uploaded), "appendage" if appendage else "single"


def _file_signature(files):
    return tuple(
        (item.name, len(item.getvalue()), hashlib.sha256(item.getvalue()).hexdigest())
        for item in files
    )


def render_full_workflow():
    st.title("Full Chronotome Workflow")
    st.markdown(
        "Run the complete modern workflow in the background—from data ingestion and entity resolution "
        "through corpus, geographic, advanced, thematic, institutional, and community analyses."
    )
    st.info(
        "This is the one-click route for users who want every result without visiting each page. "
        "It packages the workflow outputs into one downloadable ZIP when the background run finishes."
    )

    _section(1, "Choose the workflow input")
    current_ingestion = st.session_state.get("ingestion_results")
    options = []
    if current_ingestion is not None:
        options.append("Reuse the current completed ingestion result")
    options.append("Upload raw Scopus and/or Web of Science exports")
    source_choice = st.radio("Workflow starting point", options, horizontal=True, key="full-workflow-source")

    ingestion_result = current_ingestion if source_choice.startswith("Reuse") else None
    scopus_files, wos_files = [], []
    modes = {"Scopus": "single", "WoS": "single"}
    if ingestion_result is not None:
        st.success(f"Using the current ingestion result: {len(ingestion_result['processed_data']):,} documents.")
    else:
        selected_sources = st.multiselect(
            "Database exports", ["Scopus", "Web of Science"],
            default=["Scopus", "Web of Science"], key="full-workflow-databases",
        )
        left, right = st.columns(2)
        with left:
            st.markdown("#### Scopus")
            if "Scopus" in selected_sources:
                scopus_files, modes["Scopus"] = _source_upload("Scopus")
            else:
                st.caption("Not selected")
        with right:
            st.markdown("#### Web of Science")
            if "Web of Science" in selected_sources:
                wos_files, modes["WoS"] = _source_upload("WoS")
            else:
                st.caption("Not selected")
        if scopus_files or wos_files:
            st.success(f"Ready to process {len(scopus_files) + len(wos_files)} uploaded file(s).")

    _section(2, "Background workflow settings",
             "Topic counts are selected automatically; all six institutional modes and community plots are included.")
    with st.sidebar:
        st.markdown("### Full workflow settings")
        enable_time_filter = st.checkbox(
            "Exclude collection year and later", value=True, key="full-time-filter",
        )
        collection_year = st.number_input(
            "Collection / cutoff year", min_value=1900, max_value=datetime.now().year + 5,
            value=datetime.now().year, disabled=not enable_time_filter, key="full-cutoff-year",
        )
        top_n = st.number_input("Ranking size", min_value=5, max_value=50, value=10, key="full-top-n")
        min_papers = st.number_input(
            "Minimum papers for impact rankings", min_value=1, max_value=100,
            value=5, key="full-min-papers",
        )
        institutional_top_n = st.number_input(
            "Institutions in standard network plots", min_value=5, max_value=100,
            value=30, key="full-institutional-top-n",
        )
        max_institutions = st.number_input(
            "Mega-consortium exclusion threshold", min_value=2, max_value=500,
            value=50, key="full-max-institutions",
        )

    config = {
        "enable_time_filter": bool(enable_time_filter),
        "collection_year": int(collection_year) if enable_time_filter else None,
        "top_n": int(top_n), "min_source_papers": int(min_papers),
        "country_min_papers": int(min_papers),
        "institutional_top_n_plot": int(institutional_top_n),
        "max_institutions_per_paper": int(max_institutions),
        # Deliberately fixed: automatic topic selection, no search-string removal.
        "topic_k_values": list(range(3, 11)), "run_topic_institutional": True,
        "community_top_n_global": 50, "community_top_n_eu": 30,
    }
    if ingestion_result is not None:
        input_signature = (
            "current-ingestion", len(ingestion_result["processed_data"]),
            tuple(ingestion_result["processed_data"].columns),
            st.session_state.get("ingestion_signature"),
        )
        can_run = True
    else:
        input_signature = (
            "raw-uploads", _file_signature(scopus_files), _file_signature(wos_files),
            modes["Scopus"], modes["WoS"],
        )
        can_run = bool(scopus_files or wos_files)
    workflow_signature = (input_signature, tuple((key, str(value)) for key, value in config.items()))

    _section(3, "Run the complete workflow")
    st.markdown(
        "The process may take time on large corpora because it evaluates LDA and NMF candidates, "
        "builds topic-specific institutional networks, and renders six institutional community maps."
    )
    if st.button("Run all workflow", type="primary", disabled=not can_run, key="run-all-workflow"):
        try:
            # Do not keep a previous master archive resident while creating its replacement.
            st.session_state.pop("full_workflow_results", None)
            st.session_state.pop("full_workflow_signature", None)
            gc.collect()
            with st.status("Running the complete Chronotome workflow…", expanded=True) as status:
                def progress(stage, state, detail=""):
                    symbol = {"running": "⏳", "complete": "✅", "skipped": "⚠️"}.get(state, "•")
                    message = f"{symbol} **{stage}**"
                    if detail:
                        message += f" — {detail}"
                    status.write(message)

                result = run_all_workflow(
                    scopus_files=scopus_files, wos_files=wos_files, modes=modes,
                    config=config, ingestion_result=ingestion_result,
                    progress_callback=progress,
                )
                status.update(label="Complete Chronotome workflow finished.", state="complete", expanded=False)
            st.session_state["full_workflow_results"] = result
            st.session_state["full_workflow_signature"] = workflow_signature
            st.success("Every available stage has been packaged into one download.")
        except (ValueError, KeyError) as exc:
            st.error(f"The complete workflow could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected value stopped the complete workflow: {exc}")

    results = st.session_state.get("full_workflow_results")
    current = results is not None and st.session_state.get("full_workflow_signature") == workflow_signature
    if results is not None and not current:
        st.warning("The workflow input or settings changed. Run the workflow again to refresh the package.")
    if not current:
        return

    _section(4, "Workflow completion report")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final documents", f"{results['metadata']['documents']:,}")
    c2.metric("Packaged files", f"{results['metadata']['packaged_files']:,}")
    completed = int((results["manifest"]["Status"] == "Complete").sum())
    c3.metric("Completed stages", f"{completed:,}")
    c4.metric("Final process memory", f"{results['metadata']['final_rss_mb']:,.0f} MB")
    st.dataframe(results["manifest"], width="stretch", hide_index=True)
    if results["warnings"]:
        with st.expander(f"Workflow warnings ({len(results['warnings'])})"):
            for warning in results["warnings"]:
                st.warning(warning)

    _section(5, "Download every result")
    st.download_button(
        "Download complete workflow — all Excel files and plots (ZIP)",
        results["exports"]["chronotome_complete_background_workflow.zip"],
        "chronotome_complete_background_workflow.zip", "application/zip", type="primary",
    )
    st.download_button(
        "Download workflow manifest (Excel)",
        results["exports"]["full_workflow_manifest.xlsx"],
        "full_workflow_manifest.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
