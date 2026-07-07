"""Guided page for notebook Sections 17–18 country analysis."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from chronotome_core import run_country_case_study, run_geographic_bibliometrics
from chronotome_ui.figure_preview import render_svg


def _select_dataset():
    corpus_results = st.session_state.get("corpus_bibliometrics_results")
    if corpus_results is None or "Countries_Extracted" not in corpus_results.get("data", pd.DataFrame()):
        st.warning("Complete Corpus Characteristics and Production Trends before geographic analysis.")
        if st.button("Go to corpus and production", key="geographic-go-corpus"):
            st.session_state["_chronotome_navigate_to"] = "Corpus & production"
            st.rerun()
        return None, None
    data = corpus_results["data"]
    st.success(f"Using the current corpus dataset with MNCS: {len(data):,} documents.")
    return data, (
        "corpus", st.session_state.get("corpus_bibliometrics_signature"),
        len(data), tuple(data.columns),
    )


def _figure_downloads(exports: dict, basename: str):
    svg_path = f"Plots/{basename}.svg"
    columns = st.columns(3 if svg_path in exports else 2)
    left, right = columns[0], columns[-1]
    left.download_button(
        "Download 600-DPI PNG", exports[f"Plots/{basename}.png"], f"{basename}.png", "image/png",
        key=f"geo-png-{basename}",
    )
    if svg_path in exports:
        columns[1].download_button(
            "Download vector SVG", exports[svg_path], f"{basename}.svg", "image/svg+xml",
            key=f"geo-svg-{basename}",
        )
    right.download_button(
        "Download vector PDF", exports[f"Plots/{basename}.pdf"], f"{basename}.pdf", "application/pdf",
        key=f"geo-pdf-{basename}",
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


def _matching_entity_affiliations(data: pd.DataFrame):
    """Return current exploded affiliations only when they match the selected articles."""
    entity_results = st.session_state.get("entity_resolution_results")
    if not entity_results:
        return None
    summary = entity_results.get("article_summary", pd.DataFrame())
    affiliations = entity_results.get("affiliations", pd.DataFrame())
    if summary.empty or affiliations.empty or len(summary) != len(data):
        return None
    compared = False
    for key in ("DOI", "Title"):
        if key in summary.columns and key in data.columns:
            compared = True
            left = set(summary[key].dropna().astype(str).str.strip())
            right = set(data[key].dropna().astype(str).str.strip())
            if left and left == right:
                return affiliations
    if compared:
        return None
    return affiliations if tuple(summary.index) == tuple(data.index) else None


def _render_country_case_study(case_result: dict):
    """Render one focused country dashboard with a reversible back action."""
    country = case_result["country"]
    safe_name = case_result["safe_country_name"]
    if st.button("← Back to geographic analysis and choose another country", type="primary"):
        st.session_state["geographic_view"] = "overview"
        st.session_state["country_selector_epoch"] = st.session_state.get("country_selector_epoch", 0) + 1
        st.session_state.pop("geographic_case_result", None)
        st.session_state.pop("geographic_case_token", None)
        st.session_state["_chronotome_scroll_top"] = True
        st.rerun()

    st.title(f"Country Case Study: {country}")
    st.caption("Notebook Sections 20–21 · temporal dashboard and statistical field guide")
    for warning in case_result["warnings"]:
        st.warning(warning)
    metadata = case_result["metadata"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Publication appearances", f"{metadata['total_publication_appearances']:,}")
    c2.metric("Unique papers", f"{metadata['unique_papers']:,}")
    c3.metric("Productivity rank", f"#{metadata['overall_rank']} of {metadata['total_countries']}")
    c4.metric("Productivity cohort", metadata["category"].replace("Category ", "Tier "))

    tables, exports = case_result["tables"], case_result["exports"]
    _section(1, "Deep-dive dashboard", "National trajectory, cohort peers, global leaders, and rank evolution.")
    case_svg_path = f"Plots/{safe_name}_Deep_Dive_Analysis.svg"
    if case_svg_path in exports:
        render_svg(exports[case_svg_path])
    else:
        st.image(exports[f"Plots/{safe_name}_Deep_Dive_Analysis.png"], width="stretch")
    has_case_svg = case_svg_path in exports
    case_columns = st.columns(3 if has_case_svg else 2)
    left, right = case_columns[0], case_columns[-1]
    left.download_button(
        "Download publication-grade PNG (300 DPI)",
        exports[f"Plots/{safe_name}_Deep_Dive_Analysis.png"],
        f"{safe_name}_Deep_Dive_Analysis.png", "image/png",
    )
    if has_case_svg:
        case_columns[1].download_button(
            "Download vector SVG", exports[case_svg_path],
            f"{safe_name}_Deep_Dive_Analysis.svg", "image/svg+xml",
        )
    right.download_button(
        "Download vector PDF", exports[f"Plots/{safe_name}_Deep_Dive_Analysis.pdf"],
        f"{safe_name}_Deep_Dive_Analysis.pdf", "application/pdf",
    )

    _section(2, "Statistical report", "Paper-level provenance, venue, morphology, and conference structure.")
    summary_display = tables["country_case_summary"].copy()
    summary_display["Value"] = summary_display["Value"].astype(str)
    st.dataframe(summary_display, use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    with left:
        st.markdown("#### Database provenance")
        st.dataframe(tables["database_provenance"], use_container_width=True, hide_index=True)
        st.markdown("#### Top journals and sources")
        st.dataframe(tables["top_journals"], use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Document morphology")
        st.dataframe(tables["document_types"], use_container_width=True, hide_index=True)
        st.markdown("#### Conference participation")
        st.dataframe(tables["top_conferences"], use_container_width=True, hide_index=True)

    _section(3, "Institutions and collaboration partners")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Leading affiliated institutions")
        st.dataframe(tables["top_institutions"], use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### International collaboration partners")
        st.dataframe(tables["collaboration_partners"], use_container_width=True, hide_index=True)

    _section(4, "Keywords and funding")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Author keywords")
        st.dataframe(tables["author_keywords"], use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Funding organizations")
        st.dataframe(tables["funding_organizations"], use_container_width=True, hide_index=True)

    _section(5, "Timeline and rank")
    st.markdown("#### Year-by-year publication and citation summary")
    st.dataframe(tables["yearly_statistical_summary"], use_container_width=True, hide_index=True)
    st.markdown("#### Global rank evolution")
    st.dataframe(tables["country_rank_evolution"], use_container_width=True, hide_index=True)
    with st.expander("Productivity cohort membership"):
        st.dataframe(tables["country_productivity_categories"], use_container_width=True, hide_index=True)

    _section(6, "Downloads", "Complete dashboard, report, and tabular case-study package.")
    st.download_button(
        "Download complete country case study (ZIP)",
        exports[f"{safe_name}_Chronotome_Case_Study.zip"],
        f"{safe_name}_Chronotome_Case_Study.zip", "application/zip", type="primary",
    )
    st.download_button(
        "Download statistical field guide (TXT)",
        exports[f"Results/{safe_name}_Statistical_Report.txt"],
        f"{safe_name}_Statistical_Report.txt", "text/plain",
    )
    st.download_button(
        "Download all case-study tables (Excel)",
        exports[f"Results/{safe_name}_Country_Case_Study.xlsx"],
        f"{safe_name}_Country_Case_Study.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if st.button("Choose another country", key="case-study-bottom-back"):
        st.session_state["geographic_view"] = "overview"
        st.session_state["country_selector_epoch"] = st.session_state.get("country_selector_epoch", 0) + 1
        st.session_state.pop("geographic_case_result", None)
        st.session_state.pop("geographic_case_token", None)
        st.session_state["_chronotome_scroll_top"] = True
        st.rerun()
def render_geographic_analysis():
    """Render notebook-faithful country collaboration, impact, and network analyses."""
    if (
        st.session_state.get("geographic_view") == "case"
        and st.session_state.get("geographic_case_result") is not None
    ):
        _render_country_case_study(st.session_state["geographic_case_result"])
        return

    st.title("Geographic Distribution and Collaboration Patterns")
    st.markdown(
        "Sections 17–18 examine where the corpus is produced, whether each publication is domestic "
        "or international, how volume compares with time-normalized impact, and how international "
        "collaboration is structured."
    )
    st.info(
        "This is a separate analytical phase from journal/source impact. Figures preserve the notebook's "
        "Cividis colors, dimensions, annotations, axes, legends, and panel layouts."
    )

    st.markdown("## 1. Select the entity-resolved dataset")
    try:
        data, dataset_signature = _select_dataset()
    except Exception as exc:
        st.error(f"The geographic dataset could not be read: {exc}")
        data, dataset_signature = None, None
    case_affiliations = None
    case_affiliation_signature = None
    if data is not None:
        if "Countries_Extracted" not in data.columns:
            st.error(
                "The dataset is missing `Countries_Extracted`. Run Entity resolution first or upload "
                "`final_article_summary_with_countries.csv/.xlsx`."
            )
            data = None
        else:
            detected = data["Countries_Extracted"].apply(
                lambda value: bool(value) and str(value).strip() not in ("", "[]", "nan")
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Articles", f"{len(data):,}")
            c2.metric("With country metadata", f"{int(detected.sum()):,}")
            c3.metric("Country coverage", f"{detected.mean() * 100:.1f}%")
            missing = [column for column in ("Publication Year", "Cited by") if column not in data.columns]
            if missing:
                st.warning(
                    f"Optional impact fields missing: {', '.join(missing)}. "
                    "Country collaboration can still run, but impact values may use safe fallbacks."
                )
            with st.expander("Institution data for country case studies"):
                case_affiliations = _matching_entity_affiliations(data)
                if case_affiliations is not None:
                    case_affiliation_signature = ("entity-affiliations", len(case_affiliations))
                    st.success(
                        "The matching affiliation-level entity-resolution table was detected automatically."
                    )
                else:
                    st.caption(
                        "No matching affiliation-level table is currently in session. Country analysis will continue; "
                        "run Entity Resolution in this workflow first to include domestic institution rankings in case studies."
                    )

    with st.sidebar:
        st.markdown("### Geographic settings")
        collaboration_top_n = st.number_input(
            "Countries in SCP/MCP plot", min_value=1, max_value=50, value=10,
            help="Notebook default: Top 10 by article appearances.", key="geo_collaboration_top_n",
        )
        impact_top_n = st.number_input(
            "Countries in impact plot", min_value=1, max_value=50, value=15,
            help="Notebook default: Top 15 by MNCS after the minimum-paper filter.", key="geo_impact_top_n",
        )
        min_papers = st.number_input(
            "Minimum papers for country impact", min_value=1, max_value=100, value=5,
            help="Reduces unstable MNCS rankings from countries with very few papers.", key="geo_min_papers",
        )
        exclude_unknown = st.checkbox(
            "Exclude Unknown from rankings", value=True,
            help="Unknown records remain in the audit and article-level export.", key="geo_exclude_unknown",
        )
        st.markdown("#### Advanced country analysis")
        advanced_min_publications = st.number_input(
            "Minimum papers for performance matrix", min_value=1, max_value=100, value=5,
            help="Notebook default: 5 publications.", key="geo_advanced_min_pubs",
        )
        citation_top_n = st.number_input(
            "Countries in citation distribution", min_value=1, max_value=50, value=15,
            help="Notebook default: Top 15 by total citations.", key="geo_citation_top_n",
        )
        network_top_n = st.number_input(
            "Countries in collaboration network", min_value=2, max_value=100, value=30,
            help="Notebook default: Top 30 by weighted degree.", key="geo_network_top_n",
        )
        top_k_edges = st.number_input(
            "Strongest ties retained per country", min_value=1, max_value=20, value=5,
            help="Notebook default: Top 5 edges per node.", key="geo_top_k_edges",
        )
        with st.expander("Network layout setting"):
            network_iterations = st.number_input(
                "Spring-layout iterations", min_value=25, max_value=1000, value=250, step=25,
                help="Lower this for faster rendering on very large networks.", key="geo_network_iterations",
            )
    analysis_signature = (
        "svg-preview-v1", dataset_signature, int(collaboration_top_n), int(impact_top_n),
        int(min_papers), bool(exclude_unknown), int(advanced_min_publications),
        int(citation_top_n), int(network_top_n), int(top_k_edges), int(network_iterations),
    )

    results = st.session_state.get("geographic_analysis_results")
    current = results is not None and st.session_state.get("geographic_analysis_signature") == analysis_signature
    if data is not None and not current:
        try:
            with st.spinner("Classifying SCP/MCP records and rendering publication-grade country figures…"):
                result = run_geographic_bibliometrics(
                    data,
                    collaboration_top_n=int(collaboration_top_n),
                    impact_top_n=int(impact_top_n),
                    min_papers=int(min_papers),
                    exclude_unknown=bool(exclude_unknown),
                    advanced_min_publications=int(advanced_min_publications),
                    citation_top_n=int(citation_top_n),
                    network_top_n=int(network_top_n),
                    top_k_edges_per_node=int(top_k_edges),
                    network_layout_iterations=int(network_iterations),
                )
                st.session_state["geographic_analysis_results"] = result
                st.session_state["geographic_analysis_signature"] = analysis_signature
                results = result
                current = True
        except (ValueError, KeyError) as exc:
            st.error(f"Geographic analysis could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected country value stopped geographic analysis: {exc}")

    if not current:
        return
    for warning in results["warnings"]:
        st.warning(warning)

    tables, figures, exports = results["tables"], results["figures"], results["exports"]
    metadata = results["metadata"]
    _section(2, "Geographic overview", "Article-level country coverage and SCP/MCP classification.")
    with st.expander("Reproducible classification and counting rules"):
        st.markdown(
            """
- **SCP:** exactly one unique detected country on the article.
- **MCP:** two or more unique detected countries on the article.
- **Unknown:** no usable detected country; excluded from rankings by default but retained for auditing.
- Country production uses **full counting**: one MCP article contributes once to every participating country.
- Country MNCS is the mean of article-level, corpus-internal year-normalized citation scores.
            """
        )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Articles analyzed", f"{metadata['articles_analyzed']:,}")
    c2.metric("Active countries", f"{metadata['active_countries']:,}")
    c3.metric("SCP articles", f"{metadata['scp_articles']:,}")
    c4.metric("MCP articles", f"{metadata['mcp_articles']:,}")
    st.dataframe(tables["country_classification_summary"], use_container_width=True, hide_index=True)
    if metadata["unknown_articles"]:
        st.caption(f"Unknown-country articles retained for audit: {metadata['unknown_articles']:,}.")

    _section(3, "SCP/MCP collaboration", "Country production split between domestic and international papers.")
    st.dataframe(tables["top_countries_by_volume"], use_container_width=True, hide_index=True)
    _render_figure(exports, "top_10_countries_collaboration")
    with st.expander("Complete country collaboration table"):
        st.dataframe(tables["country_collaboration_summary"], use_container_width=True, hide_index=True)

    _section(4, "Country impact",
             "MNCS is normalized against publication-year averages inside this corpus, not a global database.")
    impact_table = tables["top_countries_by_mncs"]
    if impact_table.empty:
        st.warning("No country met the configured minimum-paper threshold.")
    else:
        st.dataframe(impact_table, use_container_width=True, hide_index=True)
        _render_figure(exports, "country_impact_comparison")
    with st.expander("Complete country volume and impact table"):
        st.dataframe(tables["country_master_stats"], use_container_width=True, hide_index=True)

    _section(5, "Citation prestige", "Accumulated citation distribution across the most-cited countries.")
    st.dataframe(tables["top_countries_by_total_citations"], use_container_width=True, hide_index=True)
    _render_figure(exports, "Country_Citation_Impact_Distribution")

    _section(6, "Scientometric performance matrix",
             "X = log publication volume; Y and color = internal MNCS; bubble area = accumulated citations.")
    if "Plots/Scientometric_Performance_Matrix_Productivity_vs_Impact.png" in exports:
        _render_figure(exports, "Scientometric_Performance_Matrix_Productivity_vs_Impact")
        with st.expander("Countries included in the matrix"):
            st.dataframe(tables["country_performance_matrix_data"], use_container_width=True, hide_index=True)
    else:
        st.warning("No country met the configured minimum-publication threshold.")

    _section(7, "International collaboration network",
             "Node size = weighted collaboration degree; node color = MNCS; strongest configured ties are shown.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Full-network countries", f"{metadata['network_countries']:,}")
    c2.metric("Full-network links", f"{metadata['network_links']:,}")
    c3.metric("Displayed countries", f"{metadata['displayed_network_countries']:,}")
    if "Plots/International_Collaboration_Network_Topology.png" in exports:
        _render_figure(exports, "International_Collaboration_Network_Topology")
        with st.expander("Network nodes"):
            st.dataframe(tables["international_collaboration_nodes"], use_container_width=True, hide_index=True)
        with st.expander("Network edges"):
            st.dataframe(tables["international_collaboration_edges"], use_container_width=True, hide_index=True)
    else:
        st.warning("No multi-country links were available for a collaboration network.")

    _section(8, "Analysis data", "Article-level country classification and normalized-impact preview.")
    preview_columns = [
        column for column in (
            "Title", "Publication Year", "Countries_Extracted", "Country_Classification", "Cited by", "MNCS"
        ) if column in results["data"].columns
    ]
    st.dataframe(results["data"][preview_columns].head(200), use_container_width=True, hide_index=True)

    _section(9, "Downloads", "Complete publication-grade figures, tables, networks, and classified data.")
    st.download_button(
        "Download all Sections 17–18 outputs (ZIP)",
        exports["chronotome_geographic_distribution_outputs.zip"],
        "chronotome_geographic_distribution_outputs.zip", "application/zip", type="primary",
    )
    st.download_button(
        "Download all geographic tables (Excel)",
        exports["Results/geographic_distribution_tables.xlsx"],
        "geographic_distribution_tables.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    for filename, label in (
        ("international_collaboration_nodes.csv", "Network nodes (CSV)"),
        ("international_collaboration_edges.csv", "Network edges (CSV)"),
        ("top_countries_by_total_citations.csv", "Top countries by citations (CSV)"),
    ):
        path = f"Results/{filename}"
        if path in exports:
            st.download_button(f"Download {label}", exports[path], filename, "text/csv", key=f"geo-{filename}")
    st.download_button(
        "Download country collaboration summary (CSV)", exports["Results/country_collaboration_summary.csv"],
        "country_collaboration_summary.csv", "text/csv",
    )
    st.download_button(
        "Download country master statistics (CSV)", exports["Results/country_master_stats.csv"],
        "country_master_stats.csv", "text/csv",
    )
    st.download_button(
        "Download classified article summary (Excel)",
        exports["Results/article_summary_with_country_classification.xlsx"],
        "article_summary_with_country_classification.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    _section(10, "Country case study",
             "Choose one extracted country, then open its temporal dashboard and statistical field guide.")
    country_selector = results["tables"]["country_master_stats"].sort_values(
        ["Articles", "Country"], ascending=[False, True]
    )
    country_options = country_selector["Country"].astype(str).tolist()
    selector_epoch = st.session_state.get("country_selector_epoch", 0)
    selected_country = st.selectbox(
        "Country to analyze", country_options, index=None,
        placeholder="Select a country…", key=f"country-case-dropdown-{selector_epoch}",
    )
    if selected_country:
        selected_row = country_selector[country_selector["Country"].astype(str) == selected_country].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Publication appearances", f"{int(selected_row['Articles']):,}")
        c2.metric("MCP share", f"{float(selected_row['MCP %']):.1f}%")
        c3.metric("MNCS", f"{float(selected_row['MNCS']):.2f}")
        if st.button(f"Open {selected_country} case study", type="primary"):
            case_token = (analysis_signature, case_affiliation_signature, selected_country)
            try:
                with st.spinner(f"Building the {selected_country} country case study…"):
                    case_result = run_country_case_study(
                        results["data"], results["exploded_countries"],
                        results["tables"]["country_master_stats"], selected_country,
                        affiliations=case_affiliations,
                    )
                    st.session_state["geographic_case_result"] = case_result
                    st.session_state["geographic_case_token"] = case_token
                    st.session_state["geographic_view"] = "case"
                    st.session_state["_chronotome_scroll_top"] = True
                st.rerun()
            except (ValueError, KeyError) as exc:
                st.error(f"The {selected_country} case study could not run: {exc}")
            except Exception as exc:
                st.error(f"An unexpected value stopped the {selected_country} case study: {exc}")

    st.caption("Section 19 (longitudinal productivity cohorts) remains the next separate build step.")
    st.markdown("---")
    if st.button("Continue to advanced analyses", type="primary", key="geographic-to-advanced"):
        st.session_state["_chronotome_navigate_to"] = "Advanced analyses"
        st.rerun()
