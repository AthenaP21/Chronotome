"""Opt-in final summary and advanced evaluative bibliometrics page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from chronotome_core import run_advanced_analyses
from chronotome_ui.figure_controls import render_customizable_figure
from chronotome_ui.navigation import navigate_to_page


def _figure_downloads(exports: dict, basename: str, prefix: str):
    svg_path = f"Plots/{basename}.svg"
    columns = st.columns(3 if svg_path in exports else 2)
    left, right = columns[0], columns[-1]
    left.download_button(
        "Download 600-DPI PNG", exports[f"Plots/{basename}.png"],
        f"{basename}.png", "image/png", key=f"{prefix}-png",
    )
    if svg_path in exports:
        columns[1].download_button(
            "Download vector SVG", exports[svg_path],
            f"{basename}.svg", "image/svg+xml", key=f"{prefix}-svg",
        )
    right.download_button(
        "Download vector PDF", exports[f"Plots/{basename}.pdf"],
        f"{basename}.pdf", "application/pdf", key=f"{prefix}-pdf",
    )


def _render_figure(exports: dict, basename: str, prefix: str):
    """Render a sharp vector preview and expose every publication format."""
    figure = st.session_state.get("_advanced_current_figures", {}).get(basename)
    render_customizable_figure(
        exports, basename, prefix, figure=figure,
        missing_message="The analysis completed, but no figure was produced for the available data.",
    )


def _section(number: int, title: str, caption: str | None = None):
    """Use the same full-width numbered-section rhythm as Geographic analysis."""
    st.markdown("---")
    st.markdown(f"## {number}. {title}")
    if caption:
        st.caption(caption)


def _component_result(key: str, label: str, data: pd.DataFrame, results: dict):
    """Generate one analysis on demand and retain it independently."""
    button_label = f"Regenerate {label}" if key in results else f"Generate {label}"
    if st.button(button_label, type="primary", key=f"generate-advanced-{key}"):
        try:
            with st.spinner(f"Generating {label}…"):
                results[key] = run_advanced_analyses(
                    data, analyses=[key], include_dataset=False
                )
                results[key].pop("data", None)
            st.success(f"{label.capitalize()} complete.")
        except (ValueError, KeyError) as exc:
            st.error(f"{label.capitalize()} could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected value stopped {label}: {exc}")
    result = results.get(key)
    if result:
        for warning in result["warnings"]:
            st.warning(warning)
    return result


def _common_downloads(result: dict, key: str):
    exports = result["exports"]
    st.download_button(
        "Download this analysis (ZIP)", exports["chronotome_advanced_analyses_outputs.zip"],
        f"chronotome_{key}_outputs.zip", "application/zip", key=f"advanced-{key}-zip",
    )
    st.download_button(
        "Download this analysis's tables (Excel)", exports["Results/advanced_bibliometric_tables.xlsx"],
        f"chronotome_{key}_tables.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"advanced-{key}-xlsx",
    )


def render_advanced_analyses():
    """Render each completed-workflow analysis as an independent opt-in action."""
    st.title("Advanced Analyses and Final Dataset Summary")
    st.markdown(
        "Choose the analyses you need. Each section has its own generation button, retained result, "
        "graph controls, and publication-grade downloads."
    )
    st.info(
        "This phase follows Geographic analysis so its final summary can include international "
        "collaboration alongside source, author, keyword, citation, and document-type structure."
    )

    geographic_results = st.session_state.get("geographic_analysis_results")
    if geographic_results is None:
        st.warning("Run Geographic analysis before using these completed-workflow analyses.")
        if st.button("Go to geographic analysis", type="primary"):
            navigate_to_page("Geographic analysis")
        return
    data = geographic_results.get("data", pd.DataFrame())
    if data.empty:
        st.error("The current geographic result does not contain an analysis dataset.")
        return
    missing = [column for column in ("Publication Year", "Cited by", "Source Title") if column not in data]
    if missing:
        st.error("Required advanced-analysis columns missing: " + ", ".join(missing))
        return

    st.markdown("### Completed-workflow dataset")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents", f"{len(data):,}")
    c2.metric("Active countries", f"{geographic_results['metadata'].get('active_countries', 0):,}")
    c3.metric("MCP articles", f"{geographic_results['metadata'].get('mcp_articles', 0):,}")
    c4.metric("Columns", f"{len(data.columns):,}")

    signature = (
        "svg-preview-v1", st.session_state.get("geographic_analysis_signature"),
        len(data), tuple(data.columns),
    )
    if st.session_state.get("advanced_components_signature") != signature:
        st.session_state["advanced_component_results"] = {}
        st.session_state["advanced_components_signature"] = signature
    component_results = st.session_state.setdefault("advanced_component_results", {})

    _section(1, "Final main information about the dataset",
             "Designed for direct reuse in a paper's Dataset / Descriptive Statistics section.")
    result = _component_result("summary", "final dataset summary", data, component_results)
    if result:
        tables, exports = result["tables"], result["exports"]
        st.dataframe(tables["final_main_summary"], width="stretch", hide_index=True)
        st.markdown("#### Document-type snapshot")
        st.dataframe(tables["document_type_snapshot"], width="stretch", hide_index=True)
        st.download_button(
            "Download final summary (CSV)", exports["Results/final_main_summary.csv"],
            "final_main_summary.csv", "text/csv", key="advanced-summary-csv",
        )
        _common_downloads(result, "summary")

    _section(2, "Most cited articles",
             "Ranks individual documents by accumulated citations within the current corpus.")
    result = _component_result("articles", "article impact ranking", data, component_results)
    if result:
        tables = result["tables"]
        st.dataframe(tables["top_10_most_cited_articles"], width="stretch", hide_index=True)
        with st.expander("Complete article citation ranking"):
            st.dataframe(tables["all_articles_ranked_by_citations"], width="stretch", hide_index=True)
        _common_downloads(result, "articles")

    _section(3, "Most influential authors",
             "Ranks authors by local H-index, accumulated citations, and publication volume.")
    result = _component_result("authors", "author impact ranking", data, component_results)
    if result:
        tables = result["tables"]
        st.caption(f"Author field used: {result['author_column'] or 'Unavailable'}")
        st.dataframe(tables["top_10_authors_by_impact"], width="stretch", hide_index=True)
        with st.expander("Complete author impact ranking"):
            st.dataframe(tables["all_authors_ranked_by_impact"], width="stretch", hide_index=True)
        _common_downloads(result, "authors")

    _section(4, "Bradford's Law of Scattering",
             "Identifies the core, middle, and peripheral source zones in the corpus.")
    result = _component_result("bradford", "Bradford scattering analysis", data, component_results)
    if result:
        tables, exports = result["tables"], result["exports"]
        st.session_state["_advanced_current_figures"] = result.get("figures", {})
        st.dataframe(tables["bradford_zone_summary"], width="stretch", hide_index=True)
        _render_figure(exports, "bradford_law_scattering", "advanced-bradford")
        with st.expander("Complete Bradford source table"):
            st.dataframe(tables["bradford_law_data"], width="stretch", hide_index=True)
        _common_downloads(result, "bradford")

    _section(5, "Emerging research fronts",
             "Finds highly cited recent papers using a rolling recent-publication window.")
    result = _component_result("hot", "hot-paper analysis", data, component_results)
    if result:
        tables = result["tables"]
        st.caption(f"Recent-paper window: {result['recent_year']}–present")
        if tables["top_10_hot_papers"].empty:
            st.info("No papers fall inside the recent-paper window.")
        else:
            st.dataframe(tables["top_10_hot_papers"], width="stretch", hide_index=True)
        with st.expander("Complete recent-paper ranking"):
            st.dataframe(tables["emerging_research_fronts_hot_papers"], width="stretch", hide_index=True)
        _common_downloads(result, "hot")

    _section(6, "Collaboration size versus citation impact",
             "Compares average citation performance across author-team size categories.")
    result = _component_result("team", "team-science analysis", data, component_results)
    if result:
        tables, exports = result["tables"], result["exports"]
        st.session_state["_advanced_current_figures"] = result.get("figures", {})
        st.dataframe(tables["collaboration_impact_team_size"], width="stretch", hide_index=True)
        _render_figure(exports, "collaboration_impact_team_size", "advanced-team")
        _common_downloads(result, "team")

    _section(7, "Bibliometric source landscape",
             "Bubble position uses log–log productivity and citation impact; size and color represent local H-index.")
    result = _component_result("landscape", "journal landscape", data, component_results)
    if result:
        tables, exports = result["tables"], result["exports"]
        st.session_state["_advanced_current_figures"] = result.get("figures", {})
        _render_figure(exports, "journal_landscape_cividis", "advanced-landscape")
        st.dataframe(tables["journal_landscape_data"], width="stretch", hide_index=True)
        _common_downloads(result, "landscape")

    st.markdown("---")
    if st.button("Continue to thematic analysis", type="primary", key="advanced-to-thematic"):
        navigate_to_page("Thematic analysis")
