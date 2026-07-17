"""Guided page for corpus characteristics and production trends."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from chronotome_core import run_corpus_bibliometrics
from chronotome_core.runner import DEFAULT_CONFIG
from chronotome_ui.figure_controls import render_customizable_figure
from chronotome_ui.figure_preview import render_svg
from chronotome_ui.navigation import navigate_to_page
from chronotome_ui.state import clear_downstream_state


def _select_dataset():
    entity_results = st.session_state.get("entity_resolution_results")
    if entity_results is None:
        st.warning("Complete Institutional and Geographic Entity Resolution before corpus analysis.")
        if st.button("Go to entity resolution", key="corpus-go-entity"):
            navigate_to_page("Entity resolution")
        return None, None
    data = entity_results["article_summary"]
    st.success(f"Using the current entity-resolved article summary: {len(data):,} documents.")
    return data, (
        "entity", st.session_state.get("entity_resolution_signature"),
        len(data), tuple(data.columns),
    )


def _figure_downloads(exports: dict, basename: str):
    svg_path = f"Plots/{basename}.svg"
    columns = st.columns(3 if svg_path in exports else 2)
    left, right = columns[0], columns[-1]
    left.download_button(
        "Download 600-DPI PNG", exports[f"Plots/{basename}.png"], f"{basename}.png", "image/png",
        key=f"png-{basename}",
    )
    if svg_path in exports:
        columns[1].download_button(
            "Download vector SVG", exports[svg_path], f"{basename}.svg", "image/svg+xml",
            key=f"svg-{basename}",
        )
    right.download_button(
        "Download vector PDF", exports[f"Plots/{basename}.pdf"], f"{basename}.pdf", "application/pdf",
        key=f"pdf-{basename}",
    )


def _render_figure(exports: dict, basename: str, figure=None):
    """Render a sharp vector preview, then expose PNG, SVG, and PDF."""
    render_customizable_figure(exports, basename, f"corpus-{basename}", figure=figure)


def _section(number: int, title: str, caption: str | None = None):
    st.markdown("---")
    st.markdown(f"## {number}. {title}")
    if caption:
        st.caption(caption)


def render_corpus_bibliometrics():
    """Render descriptive/evaluative corpus analyses."""
    st.title("Corpus Characteristics and Production Trends")
    st.markdown(
        "This analysis covers the collection's scale, temporal boundaries, growth dynamics, "
        "corpus-internal year-normalized citation impact, document structure, and author performance."
    )
    st.info(
        "Results include corpus scale, document structure, authorship, annual production, "
        "citation dynamics, source impact, and PNG, SVG, and PDF figures."
    )

    st.markdown("## 1. Analytical environment")
    with st.expander("Figure export settings", expanded=False):
        st.code(
            """Style: seaborn-v0_8-whitegrid
Figure preview DPI: 150
Publication PNG DPI: 600
Vector export: PDF
Font family: sans-serif
Grid alpha: 0.3""",
            language=None,
        )
        st.write(
            "The ZIP stores figures in `Plots/` and tables in `Results/`."
        )

    st.markdown("## 2. Select the analysis dataset")
    try:
        data, dataset_signature = _select_dataset()
    except Exception as exc:
        st.error(f"The analysis dataset could not be read: {exc}")
        data, dataset_signature = None, None
    if data is not None:
        required = [column for column in ("Publication Year", "Cited by") if column not in data]
        c1, c2, c3 = st.columns(3)
        c1.metric("Documents", f"{len(data):,}")
        c2.metric("Columns", f"{len(data.columns):,}")
        c3.metric("Memory", f"{data.memory_usage(deep=True).sum() / 1024:.1f} KB")
        if required:
            st.error(f"Required columns missing: {', '.join(required)}")
            data = None

    default_cutoff = datetime.now().year
    ingestion_results = st.session_state.get("ingestion_results")
    if ingestion_results:
        configured = ingestion_results.get("config", {}).get("collection_year")
        if configured:
            default_cutoff = int(configured)
    st.markdown("### Corpus analysis settings")
    settings_left, settings_mid, settings_right = st.columns(3)
    cutoff_year = settings_left.number_input(
        "Citation annualization cutoff year", min_value=1900,
        max_value=datetime.now().year + 5, value=default_cutoff,
        help="Used for citation age in the accumulated-prestige versus velocity figure.",
        key="corpus_cutoff_year",
    )
    min_source_papers = settings_mid.number_input(
        "Minimum papers for source MNCS ranking", min_value=1, max_value=100,
        value=int(DEFAULT_CONFIG["min_source_papers"]), key="source_min_papers",
    )
    max_source_title_length = settings_right.number_input(
        "Maximum source-title length in generated plots", min_value=10, max_value=160,
        value=int(DEFAULT_CONFIG["max_source_title_length"]), key="source_title_length",
        help="Use a larger value to keep more of long journal/source names in the generated figure.",
    )
    generate_analysis = st.button(
        "Generate corpus analysis",
        type="primary",
        disabled=data is None,
        key="generate-corpus-analysis",
    )
    analysis_signature = (
        "svg-preview-v1", dataset_signature, int(cutoff_year), int(DEFAULT_CONFIG["top_n"]),
        int(min_source_papers), int(max_source_title_length),
    )

    results = st.session_state.get("corpus_bibliometrics_results")
    current = results is not None and st.session_state.get("corpus_bibliometrics_signature") == analysis_signature
    if generate_analysis and data is not None:
        try:
            with st.spinner("Computing corpus metrics and figures…"):
                result = run_corpus_bibliometrics(
                    data, cutoff_year=int(cutoff_year), top_n=int(DEFAULT_CONFIG["top_n"]),
                    min_source_papers=int(min_source_papers),
                    max_source_title_length=int(max_source_title_length),
                )
                clear_downstream_state("corpus")
                st.session_state["corpus_bibliometrics_results"] = result
                st.session_state["corpus_bibliometrics_signature"] = analysis_signature
                results = result
                current = True
        except (ValueError, KeyError) as exc:
            st.error(f"Corpus analysis could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected value stopped corpus analysis: {exc}")

    if not current:
        if data is not None:
            st.info("Set the analysis options above, then select Generate corpus analysis to create the results.")
        return
    for warning in results["warnings"]:
        st.warning(warning)

    tables, figures, exports = results["tables"], results["figures"], results["exports"]
    _section(3, "Corpus summary", "Core scale, coverage, citation, source, and resource descriptors.")
    st.markdown("#### Main dataset information")
    st.dataframe(tables["main_information_summary"], width="stretch", hide_index=True)
    with st.expander("Memory use"):
        st.dataframe(tables["dataframe_memory_audit"], width="stretch", hide_index=True)

    _section(4, "Corpus-internal year-normalized citation score (MNCS)",
             "Each paper is divided by the mean citation count of retained Chronotome corpus papers from the same publication year.")
    st.latex(r"MNCS_{paper} = \frac{Citations_{paper}}{Mean\ citations_{same\ corpus\ year}}")
    st.caption(
        "MNCS is undefined when the publication year, citation count, or a positive same-year corpus mean is unavailable. "
        "It is a corpus-internal measure; no external benchmark is used."
    )
    st.dataframe(tables["mncs_yearly_baselines"], width="stretch", hide_index=True)
    preview = [column for column in ["Title", "Publication Year", "Cited by", "MNCS"] if column in results["data"]]
    with st.expander("Article-level MNCS preview"):
        st.dataframe(results["data"][preview].head(50), width="stretch", hide_index=True)

    _section(5, "Document typology", "Standardized structural morphology of the corpus.")
    st.dataframe(tables["document_type_summary"], width="stretch", hide_index=True)
    _render_figure(exports, "document_types", figures.get("document_types"))

    author_sources = results.get("author_source_counts", {})
    _section(
        6,
        "Author productivity and impact",
        (
            "Author names are selected per paper: "
            f"{author_sources.get('usable_full_names', 0):,} rows used full names; "
            f"{author_sources.get('used_abbreviated_names', 0):,} used abbreviated names; "
            f"{author_sources.get('unusable_rows', 0):,} had no usable author text."
        ),
    )
    author_table = tables["author_metrics_complete"]
    if not author_table.empty:
        st.markdown("#### Top authors by volume")
        st.dataframe(
            author_table.sort_values(["Total_Papers", "Total_Citations"], ascending=False).head(10),
            width="stretch", hide_index=True,
        )
        _render_figure(exports, "author_productivity_ranking", figures.get("author_productivity_ranking"))
        st.markdown("#### Top authors by fractionalized contribution and MNCS")
        author_impact_table = author_table.dropna(subset=["Avg_MNCS"])
        if author_impact_table.empty:
            st.info("No author MNCS ranking is available because MNCS is undefined for this corpus.")
        else:
            st.dataframe(
                author_impact_table.sort_values(
                    ["Fractional_Credit", "Avg_MNCS"], ascending=False
                ).head(10),
                width="stretch", hide_index=True,
            )
            _render_figure(exports, "author_impact_panel_chart", figures.get("author_impact_panel_chart"))

    _section(7, "Annual scientific production", "Gap-filled annual output and linear growth reliability.")
    st.dataframe(tables["annual_scientific_production"].tail(20), width="stretch", hide_index=True)
    st.dataframe(tables["growth_regression_statistics"], width="stretch", hide_index=True)
    _render_figure(exports, "annual_scientific_production", figures.get("annual_scientific_production"))

    _section(8, "Citation impact dynamics",
             "Accumulated citation prestige compared with annualized citation velocity.")
    st.dataframe(tables["citation_dynamics"].tail(20), width="stretch", hide_index=True)
    _render_figure(exports, "citation_dynamics_dual_axis", figures.get("citation_dynamics_dual_axis"))

    _section(9, "Source impact analysis",
             "H-, G-, and M-indices are local to this corpus; MNCS is the corpus-internal year-normalized citation score.")
    source_stats = tables.get("all_sources_ranked", pd.DataFrame())
    if source_stats.empty:
        st.warning("No source-level results were available.")
    else:
        with st.expander("Complete source-level bibliometric indices"):
            st.dataframe(source_stats, width="stretch", hide_index=True)
        st.markdown("#### Descriptive indicators")
        _render_figure(exports, "composite_top_sources_descriptive", figures.get("composite_top_sources_descriptive"))
        ranking_items = (
            ("Volume", "top_sources_by_volume"),
            ("Local H-index", "top_sources_by_h_index"),
            ("Local G-index", "top_sources_by_g_index"),
            ("Local M-index", "top_sources_by_m_index"),
            ("MNCS efficiency", "top_sources_by_mncs"),
        )
        for label, key in ranking_items:
            st.markdown(f"#### {label}")
            st.dataframe(tables.get(key, pd.DataFrame()), width="stretch", hide_index=True)
        if "Plots/top_10_journals_impact_analysis.png" in exports:
            st.markdown("#### Accumulated prestige versus normalized efficiency")
            _render_figure(exports, "top_10_journals_impact_analysis", figures.get("top_10_journals_impact_analysis"))

    _section(10, "Downloads", "Figures, tables, and enriched analysis data.")
    st.download_button(
        "Download all Phase 2 outputs (ZIP)", exports["chronotome_corpus_bibliometrics_outputs.zip"],
        "chronotome_corpus_bibliometrics_outputs.zip", "application/zip", type="primary",
    )
    st.download_button(
        "Download all tables (Excel workbook)", exports["Results/descriptive_bibliometrics_tables.xlsx"],
        "descriptive_bibliometrics_tables.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button(
        "Download dataset with MNCS (CSV)", exports["Results/bibliometric_dataset_with_mncs.csv"],
        "bibliometric_dataset_with_mncs.csv", "text/csv",
    )
    st.download_button(
        "Download dataset with MNCS (Excel)", exports["Results/bibliometric_dataset_with_mncs.xlsx"],
        "bibliometric_dataset_with_mncs.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("---")
    if st.button("Continue to geographic analysis", type="primary", key="corpus-to-geographic"):
        navigate_to_page("Geographic analysis")
