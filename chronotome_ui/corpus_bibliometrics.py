"""Guided page for notebook sections 9 and 11–16."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from chronotome_core import run_corpus_bibliometrics
from chronotome_ui.figure_preview import render_svg


def _select_dataset():
    entity_results = st.session_state.get("entity_resolution_results")
    if entity_results is None:
        st.warning("Complete Institutional and Geographic Entity Resolution before corpus analysis.")
        if st.button("Go to entity resolution", key="corpus-go-entity"):
            st.session_state["_chronotome_navigate_to"] = "Entity resolution"
            st.rerun()
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


def _render_figure(exports: dict, basename: str):
    """Render a sharp vector preview, then expose PNG, SVG, and PDF."""
    png_path = f"Plots/{basename}.png"
    svg_path = f"Plots/{basename}.svg"
    if png_path in exports:
        if svg_path in exports:
            render_svg(exports[svg_path])
        else:
            st.image(exports[png_path], width="stretch")
        _figure_downloads(exports, basename)


def _section(number: int, title: str, caption: str | None = None):
    st.markdown("---")
    st.markdown(f"## {number}. {title}")
    if caption:
        st.caption(caption)


def render_corpus_bibliometrics():
    """Render descriptive/evaluative corpus analyses with exact notebook figures."""
    st.title("Corpus Characteristics and Production Trends")
    st.markdown(
        "Phase 2 begins with the collection's scale, temporal boundaries, growth dynamics, "
        "time-normalized citation impact, document structure, and author performance."
    )
    st.info(
        "Figures on this page reproduce the notebook's sizes, colors, annotations, axes, grids, "
        "legends, and layouts. Downloads use **600-DPI PNG** and **vector PDF**."
    )

    st.markdown("## 1. Analytical environment")
    with st.expander("Publication-ready plotting configuration", expanded=False):
        st.code(
            """Style: seaborn-v0_8-whitegrid
Figure preview DPI: 150
Publication PNG DPI: 600
Vector export: PDF
Font family: sans-serif
Global color cycle: 5 samples from Matplotlib Cividis (0.0 → 0.9)
Grid alpha: 0.3""",
            language=None,
        )
        st.write(
            "The downloadable ZIP mirrors the notebook's reproducible folder structure with "
            "separate `Plots/` and `Results/` directories."
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
    with st.sidebar:
        st.markdown("### Phase 2 settings")
        cutoff_year = st.number_input(
            "Citation annualization cutoff year", min_value=1900,
            max_value=datetime.now().year + 5, value=default_cutoff,
            help="Used for citation age in the accumulated-prestige versus velocity figure.",
            key="corpus_cutoff_year",
        )
        st.caption("Author rankings use the notebook default: Top 10.")
        min_source_papers = st.number_input(
            "Minimum papers for journal MNCS ranking", min_value=1, max_value=100,
            value=5, key="source_min_papers",
        )
        max_source_title_length = st.number_input(
            "Maximum journal-title length in plots", min_value=10, max_value=100,
            value=30, key="source_title_length",
        )
    analysis_signature = (
        "svg-preview-v1", dataset_signature, int(cutoff_year), 10,
        int(min_source_papers), int(max_source_title_length),
    )

    results = st.session_state.get("corpus_bibliometrics_results")
    current = results is not None and st.session_state.get("corpus_bibliometrics_signature") == analysis_signature
    if data is not None and not current:
        try:
            with st.spinner("Computing corpus metrics and rendering publication-grade figures…"):
                result = run_corpus_bibliometrics(
                    data, cutoff_year=int(cutoff_year), top_n=10,
                    min_source_papers=int(min_source_papers),
                    max_source_title_length=int(max_source_title_length),
                )
                st.session_state["corpus_bibliometrics_results"] = result
                st.session_state["corpus_bibliometrics_signature"] = analysis_signature
                results = result
                current = True
        except (ValueError, KeyError) as exc:
            st.error(f"Corpus analysis could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected value stopped corpus analysis: {exc}")

    if not current:
        return
    for warning in results["warnings"]:
        st.warning(warning)

    tables, figures, exports = results["tables"], results["figures"], results["exports"]
    _section(3, "Corpus summary", "Core scale, coverage, citation, source, and resource descriptors.")
    st.markdown("#### Main dataset information")
    st.dataframe(tables["main_information_summary"], use_container_width=True, hide_index=True)
    with st.expander("Computational resource audit"):
        st.dataframe(tables["dataframe_memory_audit"], use_container_width=True, hide_index=True)

    _section(4, "Time-normalized citations (MNCS)",
             "The benchmark is the uploaded corpus, not the full Scopus or Web of Science database.")
    st.latex(r"MNCS_{paper} = \frac{Citations_{paper}}{AverageCitations_{publication\ year}}")
    st.dataframe(tables["mncs_yearly_baselines"], use_container_width=True, hide_index=True)
    preview = [column for column in ["Title", "Publication Year", "Cited by", "MNCS"] if column in results["data"]]
    with st.expander("Article-level MNCS preview"):
        st.dataframe(results["data"][preview].head(50), use_container_width=True, hide_index=True)

    _section(5, "Document typology", "Standardized structural morphology of the corpus.")
    st.dataframe(tables["document_type_summary"], use_container_width=True, hide_index=True)
    _render_figure(exports, "document_types")

    _section(6, "Author productivity and impact",
             f"Author analysis column: {results['author_column'] or 'Not available'}")
    author_table = tables["author_metrics_complete"]
    if not author_table.empty:
        st.markdown("#### Top authors by volume")
        st.dataframe(
            author_table.sort_values(["Total_Papers", "Total_Citations"], ascending=False).head(10),
            use_container_width=True, hide_index=True,
        )
        _render_figure(exports, "author_productivity_ranking")
        st.markdown("#### Top authors by fractionalized contribution and MNCS")
        st.dataframe(
            author_table.sort_values(["Fractional_Credit", "Avg_MNCS"], ascending=False).head(10),
            use_container_width=True, hide_index=True,
        )
        _render_figure(exports, "author_impact_panel_chart")

    _section(7, "Annual scientific production", "Gap-filled annual output and linear growth reliability.")
    st.dataframe(tables["annual_scientific_production"].tail(20), use_container_width=True, hide_index=True)
    st.dataframe(tables["growth_regression_statistics"], use_container_width=True, hide_index=True)
    _render_figure(exports, "annual_scientific_production")

    _section(8, "Citation impact dynamics",
             "Accumulated citation prestige compared with annualized citation velocity.")
    st.dataframe(tables["citation_dynamics"].tail(20), use_container_width=True, hide_index=True)
    _render_figure(exports, "citation_dynamics_dual_axis")

    _section(9, "Source impact analysis",
             "H-, G-, M-indices and MNCS are local to this corpus, not global JCR or SJR metrics.")
    source_stats = tables.get("all_sources_ranked", pd.DataFrame())
    if source_stats.empty:
        st.warning("No source-level results were available.")
    else:
        with st.expander("Complete source-level bibliometric indices"):
            st.dataframe(source_stats, use_container_width=True, hide_index=True)
        st.markdown("#### Descriptive indicators")
        _render_figure(exports, "composite_top_sources_descriptive")
        ranking_items = (
            ("Volume", "top_sources_by_volume"),
            ("Local H-index", "top_sources_by_h_index"),
            ("Local G-index", "top_sources_by_g_index"),
            ("Local M-index", "top_sources_by_m_index"),
            ("MNCS efficiency", "top_sources_by_mncs"),
        )
        for label, key in ranking_items:
            st.markdown(f"#### {label}")
            st.dataframe(tables.get(key, pd.DataFrame()), use_container_width=True, hide_index=True)
        if "Plots/top_10_journals_impact_analysis.png" in exports:
            st.markdown("#### Accumulated prestige versus normalized efficiency")
            _render_figure(exports, "top_10_journals_impact_analysis")

    _section(10, "Downloads", "Complete publication-grade figures, tables, and enriched analysis data.")
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
        st.session_state["_chronotome_navigate_to"] = "Geographic analysis"
        st.rerun()
