"""Part 4 institutional productivity, collaboration, and community analysis."""

from __future__ import annotations

import hashlib
import io

import pandas as pd
import streamlit as st

from chronotome_core import (
    run_institutional_analysis, run_institutional_community_visualization,
    run_topic_institutional_analysis,
)
from chronotome_ui.figure_controls import render_customizable_figure
from chronotome_ui.figure_preview import render_svg


ANALYSIS_LABELS = {
    "Global_All": "Global — All publications",
    "Global_MCP": "Global — MCP (multi-country publications)",
    "Global_SCP": "Global — SCP (single-country publications)",
    "EU_All": "EU-only — All publications",
    "EU_MCP": "EU-only — MCP (intra-EU international publications)",
    "EU_SCP": "EU-only — SCP (domestic publications)",
}


def _section(number: int, title: str, caption: str | None = None):
    st.markdown("---")
    st.markdown(f"## {number}. {title}")
    if caption:
        st.caption(caption)


def _read_handoff(upload) -> pd.DataFrame:
    content = upload.getvalue()
    if upload.name.lower().endswith((".xlsx", ".xls")):
        frame = pd.read_excel(io.BytesIO(content))
    else:
        frame = pd.read_csv(io.BytesIO(content), low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _select_dataset():
    geographic = st.session_state.get("geographic_analysis_results")
    options = []
    if geographic is not None:
        options.append("Use current geographic-analysis dataset")
    options.append("Upload the post-geographic Chronotome dataset")
    selected = st.radio("Institutional dataset", options, horizontal=True, key="institutional-dataset-source")
    if selected.startswith("Use current"):
        data = geographic.get("data", pd.DataFrame())
        return data, (
            "geographic", st.session_state.get("geographic_analysis_signature"),
            len(data), tuple(data.columns),
        )

    upload = st.file_uploader(
        "Upload `article_summary_with_country_classification.csv` or `.xlsx`",
        type=["csv", "xlsx", "xls"], key="institutional-handoff-upload",
        help="Use the file exported by Geographic Analysis; the basename is intentionally unchanged.",
    )
    if upload is None:
        return None, None
    expected = "article_summary_with_country_classification"
    basename = upload.name.rsplit(".", 1)[0]
    if basename != expected:
        st.error(
            f"Expected `{expected}.csv` or `{expected}.xlsx`, but received `{upload.name}`. "
            "Keeping this filename fixed prevents accidental use of an earlier workflow dataset."
        )
        return None, None
    signature = (upload.name, len(upload.getvalue()), hashlib.sha256(upload.getvalue()).hexdigest())
    if st.session_state.get("institutional-upload-signature") != signature:
        st.session_state["institutional-upload-data"] = _read_handoff(upload)
        st.session_state["institutional-upload-signature"] = signature
    return st.session_state["institutional-upload-data"], ("post-geographic-upload", *signature)


def _render_figure(exports: dict, basename: str, prefix: str):
    figure = st.session_state.get("_institutional_current_figures", {}).get(basename)
    render_customizable_figure(
        exports, basename, prefix, figure=figure,
        missing_message="No network figure could be produced for this filtered dataset.",
    )


def _network_svg_export(entry: dict, analysis_name: str) -> bytes | None:
    """Return the exported primary network SVG for a completed scope."""
    result = entry.get("result", {})
    exports = result.get("exports", {})
    suffix = f"_{analysis_name}.svg"
    candidates = sorted(
        path for path in exports
        if path.startswith("Plots/Collaboration_Network_Top_") and path.endswith(suffix)
    )
    return exports[candidates[0]] if candidates else None


def _matches_dataset(entry: dict, dataset_signature) -> bool:
    """Recognize current and pre-comparison cache entries for this corpus."""
    if not isinstance(entry, dict):
        return False
    if "dataset_signature" in entry:
        return entry["dataset_signature"] == dataset_signature
    signature = entry.get("signature", ())
    return len(signature) > 1 and signature[1] == dataset_signature


def _render_network_comparison(cache: dict, dataset_signature, *, section_number: int = 6) -> None:
    """Show two already-generated network figures without rerunning analyses."""
    _section(
        section_number,
        "Compare two institutional networks",
        "Choose two completed scopes. The comparison preserves each network's original layout and styling.",
    )
    comparable = {
        name: entry
        for name, entry in cache.items()
        if _matches_dataset(entry, dataset_signature)
        and _network_svg_export(entry, name) is not None
    }
    if len(comparable) < 2:
        st.caption("Generate two institutional scopes to compare their network figures side by side.")
        return
    options = list(comparable)
    controls_left, controls_right = st.columns(2)
    with controls_left:
        left_name = st.selectbox(
            "First network",
            options,
            format_func=lambda key: ANALYSIS_LABELS[key],
            key="institutional-compare-left",
        )
    with controls_right:
        right_default = 1 if len(options) > 1 else 0
        right_name = st.selectbox(
            "Second network",
            options,
            index=right_default,
            format_func=lambda key: ANALYSIS_LABELS[key],
            key="institutional-compare-right",
        )

    if left_name == right_name:
        st.info("Choose two different scopes to compare their networks.")
        return

    left_figure = _network_svg_export(comparable[left_name], left_name)
    right_figure = _network_svg_export(comparable[right_name], right_name)
    if left_figure is None or right_figure is None:
        st.warning("One selected scope has no collaboration network figure to compare.")
        return

    # Intentionally render only the original network figures here: no tables,
    # metrics, downloads, or style controls are included in the comparison.
    figure_left, figure_right = st.columns(2)
    with figure_left:
        render_svg(left_figure)
    with figure_right:
        render_svg(right_figure)


def _matching_topic_dataset(data: pd.DataFrame):
    final = st.session_state.get("final_topic_model_results")
    if not final:
        return None
    candidate = final.get("data", pd.DataFrame())
    if candidate.empty or "Dominant_Topic" not in candidate or "Institutions_Extracted" not in candidate:
        return None
    if len(candidate) != len(data):
        return None
    for column in ("DOI", "Title"):
        if column in candidate and column in data:
            left = set(candidate[column].dropna().astype(str).str.strip())
            right = set(data[column].dropna().astype(str).str.strip())
            if left and left == right:
                return candidate
    return candidate if tuple(candidate.index) == tuple(data.index) else None


def render_institutional_analysis():
    st.title("Institutional Analysis")
    st.markdown(
        "Part 4 ranks institutional productivity and maps collaboration for six complementary scopes: "
        "Global or EU-only, each using all publications, MCP publications, or SCP publications."
    )
    st.info(
        "Choose one network scope at a time. Chronotome exports the institutional ranking, "
        "collaboration graph, network tables, and optional community visualization for that scope."
    )

    _section(1, "Select the post-geographic dataset")
    try:
        data, dataset_signature = _select_dataset()
    except Exception as exc:
        st.error(f"The institutional handoff dataset could not be read: {exc}")
        data, dataset_signature = None, None
    if data is None:
        return
    if "Institutions_Extracted" not in data:
        st.error(
            "`Institutions_Extracted` is missing. Use the current entity-resolved geographic dataset or "
            "the unchanged `article_summary_with_country_classification` export."
        )
        return
    institution_coverage = data["Institutions_Extracted"].astype(str).str.len().gt(2)
    country_coverage = data.get("Countries_Extracted", pd.Series([[]] * len(data))).astype(str).str.len().gt(2)
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", f"{len(data):,}")
    c2.metric("Institution coverage", f"{institution_coverage.mean() * 100:.1f}%")
    c3.metric("Country coverage", f"{country_coverage.mean() * 100:.1f}%")

    _section(2, "Choose one institutional network")
    analysis_name = st.selectbox(
        "Analysis scope", list(ANALYSIS_LABELS),
        format_func=lambda key: ANALYSIS_LABELS[key], key="institutional-analysis-mode",
    )
    with st.expander("How the six scopes are defined"):
        st.markdown(
            "- **Global — All:** every publication.\n"
            "- **Global — MCP:** papers containing at least two countries.\n"
            "- **Global — SCP:** papers containing exactly one country.\n"
            "- **EU-only:** every affiliation country on the paper must belong to the EU27.\n"
            "- **EU-only — MCP:** international collaboration wholly inside the EU27.\n"
            "- **EU-only — SCP:** domestic papers from one EU27 country."
        )
    setting_left, setting_right = st.columns(2)
    top_n_plot = setting_left.number_input(
        "Institutions shown in network", min_value=5, max_value=100, value=30,
        help="Top institutions by publication volume.", key="institutional-top-n-plot",
    )
    max_institutions = setting_right.number_input(
        "Mega-consortium exclusion threshold", min_value=2, max_value=500, value=50,
        help="Papers above this institution count are excluded only from edge construction.",
        key="institutional-max-institutions",
    )
    signature = (
        "institutional-v1", dataset_signature, analysis_name,
        int(top_n_plot), int(max_institutions),
    )
    cache = st.session_state.setdefault("institutional-analysis-cache", {})
    cached = cache.get(analysis_name)
    current = cached is not None and cached.get("signature") == signature
    if st.button("Generate institutional network", type="primary", key="generate-institutional-network"):
        try:
            with st.spinner(f"Building {ANALYSIS_LABELS[analysis_name]} institutional outputs…"):
                result = run_institutional_analysis(
                    data, analysis_name=analysis_name, top_n_list=1000,
                    top_n_plot=int(top_n_plot),
                    max_institutions_per_paper=int(max_institutions),
                )
            cache[analysis_name] = {
                "signature": signature,
                "dataset_signature": dataset_signature,
                "result": result,
            }
            # Keep completed scopes for visual comparison, but never retain
            # results from a different post-geographic corpus in session.
            for cached_name, cached_entry in list(cache.items()):
                if not _matches_dataset(cached_entry, dataset_signature):
                    cache.pop(cached_name, None)
            current = True
        except (ValueError, KeyError) as exc:
            st.error(f"Institutional analysis could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected institution value stopped the analysis: {exc}")
    if not current:
        _render_network_comparison(cache, dataset_signature, section_number=3)
        st.caption("Choose a scope and settings, then generate its institutional network when you are ready.")
        return
    result = cache[analysis_name]["result"]
    st.session_state["institutional-active-signature"] = signature
    st.session_state["institutional-analysis-results"] = result
    for warning in result["warnings"]:
        st.warning(warning)
    tables, exports, metadata = result["tables"], result["exports"], result["metadata"]
    st.session_state["_institutional_current_figures"] = result.get("figures", {})

    _section(3, "Institutional overview", ANALYSIS_LABELS[analysis_name])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filtered articles", f"{metadata['articles']:,}")
    c2.metric("Unique institutions", f"{metadata['institutions']:,}")
    c3.metric("Collaboration links", f"{metadata['network_edges']:,}")
    c4.metric("Mega-consortia excluded", f"{metadata['excluded_large_papers']:,}")
    st.dataframe(tables["analysis_summary"], width="stretch", hide_index=True)

    _section(4, "Most productive institutions")
    st.dataframe(tables["institution_ranking"].head(15), width="stretch", hide_index=True)
    ranking_basename = f"Top_10_Institutions_By_Publications_{analysis_name}"
    _render_figure(exports, ranking_basename, f"institution-ranking-{analysis_name}")
    with st.expander("Complete institutional ranking"):
        st.dataframe(tables["institution_ranking"], width="stretch", hide_index=True)

    _section(5, "Institutional collaboration network",
             "Node size = weighted collaboration strength; node color = degree centrality; edge width = collaboration strength.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Full network nodes", f"{metadata['network_nodes']:,}")
    c2.metric("Full network edges", f"{metadata['network_edges']:,}")
    c3.metric("Displayed nodes", f"{metadata['displayed_nodes']:,}")
    network_basename = f"Collaboration_Network_Top_{int(top_n_plot)}_{analysis_name}"
    if f"Plots/{network_basename}.svg" in exports:
        _render_figure(exports, network_basename, f"institution-network-{analysis_name}")
    else:
        st.warning("This scope contains no multi-institution edges to draw.")

    _render_network_comparison(cache, dataset_signature)

    _section(7, "Community visualization (optional)",
             "Color = community; node size = full-network collaboration strength; dark edges = within-community ties.")
    community_cache = st.session_state.setdefault("institutional-community-cache", {})
    cached_community = community_cache.get(analysis_name)
    st.caption("This runs deterministic weighted Louvain community detection for the selected network.")
    button_label = "Regenerate communities :D" if cached_community else "Generate communities :D"
    if metadata["network_edges"] == 0:
        st.caption("Community detection requires at least one collaboration edge.")
    elif st.button(button_label, type="primary", key=f"generate-communities-{analysis_name}"):
        try:
            default_community_top_n = 50 if analysis_name.startswith("Global") else 30
            with st.spinner(f"Detecting and arranging {analysis_name} communities…"):
                community_result = run_institutional_community_visualization(
                    result, top_n_to_plot=default_community_top_n,
                )
            community_cache[analysis_name] = {
                "signature": signature,
                "result": community_result,
            }
            for cached_name in list(community_cache):
                if cached_name != analysis_name:
                    community_cache.pop(cached_name, None)
            cached_community = community_cache[analysis_name]
        except (ValueError, KeyError) as exc:
            st.error(f"Communities could not be generated: {exc}")
        except Exception as exc:
            st.error(f"An unexpected network value stopped community generation: {exc}")
    if cached_community and cached_community.get("signature") == signature:
        community_result = cached_community["result"]
        st.session_state["_institutional_current_figures"] = community_result.get("figures", {})
        for warning in community_result["warnings"]:
            st.warning(warning)
        community_metadata = community_result["metadata"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Communities", f"{community_metadata['communities_full']:,}")
        c2.metric("Displayed institutions", f"{community_metadata['nodes_displayed']:,}")
        c3.metric("Partition source", community_metadata["community_source"])
        _render_figure(
            community_result["exports"], community_result["basename"],
            f"institution-community-{analysis_name}",
        )
        st.dataframe(community_result["tables"]["community_summary"], width="stretch", hide_index=True)
        with st.expander("Complete institution-to-community membership"):
            st.dataframe(
                community_result["tables"]["community_membership"],
                width="stretch", hide_index=True,
            )
        community_archive = f"chronotome_institutional_communities_{analysis_name}.zip"
        community_workbook = f"Results/Institutional_Communities_{analysis_name}.xlsx"
        left, right = st.columns(2)
        left.download_button(
            "Download community visualization package (ZIP)",
            community_result["exports"][community_archive], community_archive,
            "application/zip", key=f"community-zip-{analysis_name}",
        )
        right.download_button(
            "Download community membership (Excel)",
            community_result["exports"][community_workbook], community_workbook.split("/")[-1],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"community-xlsx-{analysis_name}",
        )

    _section(8, "Network and collaboration data")
    with st.expander("Collaboration pair counts", expanded=True):
        st.dataframe(tables["collaboration_counts"].head(250), width="stretch", hide_index=True)
    left, right = st.columns(2)
    with left:
        st.markdown("#### Network nodes")
        st.dataframe(tables["network_nodes"].head(250), width="stretch", hide_index=True)
    with right:
        st.markdown("#### Network edges")
        st.dataframe(tables["network_edges"].head(250), width="stretch", hide_index=True)

    _section(9, "Downloads", "Every selected scope has its own complete, reproducible output package.")
    archive = f"chronotome_institutional_{analysis_name}_outputs.zip"
    workbook = f"Results/Institutional_Analysis_{analysis_name}.xlsx"
    left, right = st.columns(2)
    left.download_button(
        "Download complete institutional analysis (ZIP)", exports[archive], archive,
        "application/zip", type="primary",
    )
    right.download_button(
        "Download all institutional tables (Excel)", exports[workbook], workbook.split("/")[-1],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    graphml = f"Results/network_data_{analysis_name}.graphml"
    st.download_button(
        "Download full network for Gephi/Cytoscape (GraphML)", exports[graphml], graphml.split("/")[-1],
        "application/graphml+xml",
    )

    _section(10, "Thematic–institutional networks (optional)",
             "Build a separate institutional network for one LDA topic only when final thematic results match this corpus.")
    topic_data = _matching_topic_dataset(data)
    if topic_data is None:
        st.caption("No matching final LDA topic dataset is currently in session. This does not affect the six core analyses.")
    else:
        topics = sorted(topic_data["Dominant_Topic"].dropna().unique(), key=lambda value: str(value))
        selected_topic = st.selectbox("Topic", topics, key="institutional-topic-selection")
        topic_key = str(selected_topic).replace(".", "_")
        topic_cache = st.session_state.setdefault("institutional-topic-cache", {})
        if st.button(f"Generate Topic {selected_topic} institutional network", key="run-topic-institutional"):
            try:
                with st.spinner(f"Building the Topic {selected_topic} institutional network…"):
                    topic_cache[topic_key] = run_topic_institutional_analysis(
                        topic_data, selected_topic, top_n_plot=25,
                        max_institutions_per_paper=int(max_institutions),
                    )
                    for cached_topic in list(topic_cache):
                        if cached_topic != topic_key:
                            topic_cache.pop(cached_topic, None)
            except (ValueError, KeyError) as exc:
                st.error(f"Topic network could not run: {exc}")
            except Exception as exc:
                st.error(f"An unexpected value stopped the topic network: {exc}")
        topic_result = topic_cache.get(topic_key)
        if topic_result:
            topic_name = topic_result["metadata"]["analysis_name"]
            st.session_state["_institutional_current_figures"] = topic_result.get("figures", {})
            st.dataframe(topic_result["tables"]["institution_ranking"].head(15), width="stretch", hide_index=True)
            _render_figure(
                topic_result["exports"], f"Top_10_Institutions_By_Publications_{topic_name}",
                f"topic-inst-ranking-{topic_key}",
            )
            topic_network = f"Collaboration_Network_Top_25_{topic_name}"
            if f"Plots/{topic_network}.svg" in topic_result["exports"]:
                _render_figure(topic_result["exports"], topic_network, f"topic-inst-network-{topic_key}")
            topic_archive = f"chronotome_institutional_{topic_name}_outputs.zip"
            st.download_button(
                f"Download Topic {selected_topic} institutional package (ZIP)",
                topic_result["exports"][topic_archive], topic_archive, "application/zip",
            )
