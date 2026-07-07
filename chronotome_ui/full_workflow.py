"""Streamlit interface for the Chronotome bibliometric workflow."""

from __future__ import annotations

from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from chronotome_core import run_chronotome
from chronotome_core.export import dataframe_csv, figure_png, figure_svg
from chronotome_core.io import InputError, inspect_uploads
from chronotome_ui.figure_preview import render_svg

st.title("Full Chronotome workflow")
st.markdown(
    "A reproducible workflow for harmonizing **Scopus** and **Web of Science** exports, "
    "deduplicating records, and running the descriptive, impact, thematic, geographic, "
    "and institutional analyses from the original Chronotome notebook."
)

with st.sidebar:
    st.header("Configuration")
    st.caption("These controls expose values that were configurable or hardcoded in the notebook.")
    enable_time_filter = st.checkbox(
        "Exclude collection year and later", value=True,
        help="The notebook removes the collection year because indexing is usually incomplete."
    )
    collection_year = st.number_input(
        "Collection / cutoff year", min_value=1900, max_value=datetime.now().year + 5,
        value=datetime.now().year, step=1, disabled=not enable_time_filter,
    )
    top_n = st.slider("Ranking size", 5, 25, 10)
    min_papers = st.number_input("Minimum papers for impact rankings", 1, 100, 5)
    network_top_n = st.slider("Institutions shown in network plots", 10, 75, 30, 5)
    max_institutions = st.number_input(
        "Institution cap per paper", 5, 200, 50,
        help="The notebook caps institutions per paper at 50 before generating pairs."
    )
    st.divider()
    run_thematic = st.checkbox(
        "Run thematic analysis", value=True,
        help="Runs n-grams and the notebook's NMF topic-model branch. Large corpora take longer."
    )
    topic_count = st.slider("Number of NMF topics", 2, 20, 8, disabled=not run_thematic)
    auto_min_df = st.checkbox("Automatic minimum term frequency", value=True, disabled=not run_thematic)
    min_df = st.number_input("Minimum term frequency", 1, 100, 5, disabled=not run_thematic or auto_min_df)

st.subheader("1. Upload bibliometric exports")
st.info(
    "Upload one or more **Scopus or Web of Science exports** in CSV, TXT, XLS, or XLSX format. "
    "Use full bibliographic records with cited references when possible. Split exports from the "
    "same database may be selected together; Chronotome appends them before harmonization."
)
uploads = st.file_uploader(
    "Scopus / Web of Science files", type=["csv", "txt", "xls", "xlsx"],
    accept_multiple_files=True,
)

metadata = None
if uploads:
    try:
        metadata = inspect_uploads(uploads)
        st.success(f"Validated {len(uploads)} file(s). Detected {metadata['records']:,} records before deduplication.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Records", f"{metadata['records']:,}")
        c2.metric("Databases", ", ".join(metadata["sources"]) or "—")
        c3.metric("Year range", f"{metadata['year_range'][0]}–{metadata['year_range'][1]}" if metadata["year_range"] else "Not detected")
        source_fields = [c for c in metadata["columns"] if c in {"Source title", "Source Title", "Document Type", "Authors", "Affiliations", "Addresses"}]
        c4.metric("Detected key fields", len(source_fields))
        with st.expander("Detected files and columns"):
            st.dataframe(pd.DataFrame(metadata["files"]), use_container_width=True, hide_index=True)
            st.write(", ".join(metadata["columns"]))
    except InputError as exc:
        st.error(str(exc))

config = {
    "enable_time_filter": enable_time_filter,
    "collection_year": int(collection_year) if enable_time_filter else None,
    "top_n": int(top_n),
    "min_papers": int(min_papers),
    "network_top_n": int(network_top_n),
    "max_institutions_per_paper": int(max_institutions),
    "run_thematic": run_thematic,
    "topic_count": int(topic_count),
    "min_document_frequency": None if auto_min_df else int(min_df),
}

if st.button("Run analysis", type="primary", disabled=not uploads or metadata is None):
    try:
        with st.spinner("Running the Chronotome workflow…"):
            st.session_state["chronotome_results"] = run_chronotome(uploads, config)
        st.success("Analysis complete.")
    except (InputError, ValueError, KeyError) as exc:
        st.error(f"Chronotome could not run: {exc}")
    except Exception as exc:
        st.error(
            "The analysis stopped because this export contains an unexpected value. "
            f"Please verify the file and try again. Technical detail: {exc}"
        )

results = st.session_state.get("chronotome_results")
if results:
    for warning in results["warnings"]:
        st.warning(warning)

    st.subheader("2. Results")
    overview, data_tab, rankings, geography, institutions, themes, downloads = st.tabs(
        ["Overview", "Processed data", "Rankings & impact", "Countries", "Institutions", "Themes", "Downloads"]
    )
    tables, figures = results["tables"], results["figures"]

    with overview:
        st.markdown("#### Corpus summary")
        st.dataframe(tables["main_information_summary"], use_container_width=True, hide_index=True)
        st.markdown("#### PRISMA-style flow")
        st.dataframe(tables["prisma_report"], use_container_width=True, hide_index=True)
        cols = st.columns(2)
        for container, key in zip(cols, ["annual_scientific_production", "document_types"]):
            if key in figures:
                with container:
                    render_svg(figure_svg(figures[key]))
        if "citation_dynamics" in figures:
            render_svg(figure_svg(figures["citation_dynamics"]))

    with data_tab:
        st.caption(f"Showing the first 100 of {len(results['processed_data']):,} processed records.")
        st.dataframe(results["processed_data"].head(100), use_container_width=True, hide_index=True)
        st.download_button(
            "Download cleaned dataset", results["exports"]["cleaned_bibliometric_dataset.csv"],
            "cleaned_bibliometric_dataset.csv", "text/csv",
        )

    with rankings:
        for title, table_key, columns in [
            ("Most cited articles", "articles_ranked_by_citations", None),
            ("Author metrics", "author_metrics", ["Author", "Total_Papers", "Total_Citations", "Fractional_Credit", "Avg_MNCS", "h_index"]),
            ("Source metrics", "source_metrics", ["OriginalTitle", "Number_of_Publications", "Total_Citations", "h_index", "g_index", "m_index", "Avg_MNCS"]),
            ("Bradford scattering", "bradford", None),
            ("Recent highly cited papers", "hot_papers", None),
            ("Team-size impact", "team_size_impact", None),
        ]:
            table = tables[table_key]
            if not table.empty:
                st.markdown(f"#### {title}")
                shown = table[columns] if columns else table
                st.dataframe(shown.head(max(top_n, 10)), use_container_width=True, hide_index=True)
        for key in ("author_impact", "source_rankings", "bradford_scattering", "team_size_impact"):
            if key in figures:
                render_svg(figure_svg(figures[key]))

    with geography:
        if tables["country_metrics"].empty:
            st.warning("No countries could be extracted from the uploaded affiliations.")
        else:
            st.dataframe(tables["country_metrics"], use_container_width=True, hide_index=True)
            for key in ("country_collaboration", "country_impact"):
                if key in figures:
                    render_svg(figure_svg(figures[key]))

    with institutions:
        st.dataframe(tables["institution_network_summary"], use_container_width=True, hide_index=True)
        selected_network = st.selectbox("Network", list(results["networks"]))
        network = results["networks"][selected_network]
        c1, c2 = st.columns(2)
        c1.markdown("#### Institution ranking")
        c1.dataframe(network["ranking"].head(top_n), use_container_width=True, hide_index=True)
        c2.markdown("#### Strongest collaboration links")
        c2.dataframe(network["edges"].sort_values("Collaboration_Count", ascending=False).head(top_n), use_container_width=True, hide_index=True)
        figure_key = f"institution_network_{selected_network.lower()}"
        if figure_key in figures:
            render_svg(figure_svg(figures[figure_key]))

    with themes:
        if not results["config"]["run_thematic"]:
            st.info("Thematic analysis was disabled in the sidebar.")
        elif "topics" not in tables:
            st.warning("There was not enough repeated title/abstract/keyword text to fit a topic model.")
        else:
            st.markdown("#### NMF topics")
            st.dataframe(tables["topics"], use_container_width=True, hide_index=True)
            st.markdown("#### Topic impact")
            st.dataframe(tables["topic_impact"], use_container_width=True, hide_index=True)
            if "topic_evolution" in figures:
                render_svg(figure_svg(figures["topic_evolution"]))
            for key in ("unigrams", "bigrams", "trigrams"):
                st.markdown(f"#### {key.title()}")
                st.dataframe(tables[key].head(30), use_container_width=True, hide_index=True)

    with downloads:
        st.download_button(
            "Download all outputs (ZIP)", results["exports"]["chronotome_outputs.zip"],
            "chronotome_outputs.zip", "application/zip", type="primary",
        )
        st.markdown("#### Individual result tables")
        for key, table in tables.items():
            if isinstance(table, pd.DataFrame) and not table.empty:
                st.download_button(f"{key}.csv", dataframe_csv(table), f"{key}.csv", "text/csv", key=f"table-{key}")
        st.markdown("#### Individual figures")
        for key, figure in figures.items():
            st.download_button(f"{key}.png", figure_png(figure), f"{key}.png", "image/png", key=f"figure-{key}")
            st.download_button(
                f"{key}.svg", figure_svg(figure), f"{key}.svg", "image/svg+xml", key=f"figure-svg-{key}"
            )
