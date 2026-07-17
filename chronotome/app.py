"""Installed Streamlit entry point for Chronotome."""

from __future__ import annotations

import streamlit as st

from chronotome_ui.advanced_analyses import render_advanced_analyses
from chronotome_ui.branding import apply_brand_theme, render_sidebar_brand
from chronotome_ui.corpus_bibliometrics import render_corpus_bibliometrics
from chronotome_ui.dataframe_display import install_safe_dataframe_display
from chronotome_ui.entity_resolution import render_entity_resolution
from chronotome_ui.full_workflow import render_full_workflow
from chronotome_ui.geographic_analysis import render_geographic_analysis
from chronotome_ui.home import render_home
from chronotome_ui.ingestion import render_ingestion
from chronotome_ui.institutional_analysis import render_institutional_analysis
from chronotome_ui.local_installation import render_local_installation
from chronotome_ui.navigation import scroll_to_top
from chronotome_ui.thematic_analysis import render_thematic_analysis


WORKFLOW_PAGES = [
    "Home", "Local installation", "Data ingestion", "Entity resolution", "Corpus & production",
    "Geographic analysis", "Advanced analyses", "Thematic analysis",
    "Institutional analysis", "Full workflow",
]


def _sidebar_page_changed() -> None:
    """Scroll only when the user deliberately changes workflow pages in the sidebar."""
    st.session_state["_chronotome_scroll_top"] = True


def main() -> None:
    """Configure and render the Chronotome single-page workflow."""
    st.set_page_config(page_title="Chronotome", page_icon="⏳", layout="wide")
    install_safe_dataframe_display()
    apply_brand_theme()
    top_scroll_mount = st.empty()
    st.markdown('<span id="chronotome-page-top"></span>', unsafe_allow_html=True)

    if "chronotome_page" not in st.session_state:
        st.session_state["chronotome_page"] = "Home"
    requested_page = st.session_state.pop("_chronotome_navigate_to", None)
    if requested_page:
        st.session_state["chronotome_page"] = requested_page

    with st.sidebar:
        render_sidebar_brand()
        page = st.radio(
            "Workflow", WORKFLOW_PAGES,
            key="chronotome_page",
            on_change=_sidebar_page_changed,
        )

    should_scroll_top = st.session_state.pop("_chronotome_scroll_top", False)

    if page == "Home":
        render_home()
    elif page == "Local installation":
        render_local_installation()
    elif page == "Data ingestion":
        render_ingestion()
    elif page == "Entity resolution":
        render_entity_resolution()
    elif page == "Corpus & production":
        render_corpus_bibliometrics()
    elif page == "Geographic analysis":
        render_geographic_analysis()
    elif page == "Advanced analyses":
        render_advanced_analyses()
    elif page == "Thematic analysis":
        render_thematic_analysis()
    elif page == "Institutional analysis":
        render_institutional_analysis()
    else:
        render_full_workflow()

    if should_scroll_top:
        with top_scroll_mount:
            scroll_to_top(token=page)


if __name__ == "__main__":
    main()
