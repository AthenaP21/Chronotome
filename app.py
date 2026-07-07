"""Chronotome Streamlit application entry point."""

import streamlit as st

from chronotome_ui.home import render_home
from chronotome_ui.ingestion import render_ingestion
from chronotome_ui.entity_resolution import render_entity_resolution
from chronotome_ui.corpus_bibliometrics import render_corpus_bibliometrics
from chronotome_ui.geographic_analysis import render_geographic_analysis
from chronotome_ui.advanced_analyses import render_advanced_analyses
from chronotome_ui.thematic_analysis import render_thematic_analysis
from chronotome_ui.institutional_analysis import render_institutional_analysis
from chronotome_ui.full_workflow import render_full_workflow
from chronotome_ui.navigation import scroll_to_top

st.set_page_config(page_title="Chronotome", page_icon="⏳", layout="wide")

if "chronotome_page" not in st.session_state:
    st.session_state["chronotome_page"] = "Home"
requested_page = st.session_state.pop("_chronotome_navigate_to", None)
if requested_page:
    st.session_state["chronotome_page"] = requested_page

with st.sidebar:
    st.title("Chronotome")
    page = st.radio(
        "Workflow", ["Home", "Data ingestion", "Entity resolution", "Corpus & production",
                     "Geographic analysis", "Advanced analyses", "Thematic analysis",
                     "Institutional analysis", "Full workflow"],
        key="chronotome_page",
    )
    st.caption("Scopus + Web of Science · No OpenAlex integration")

if st.session_state.pop("_chronotome_scroll_top", False) or st.session_state.get("_chronotome_last_page") != page:
    scroll_to_top()
    st.session_state["_chronotome_last_page"] = page

if page == "Home":
    render_home()
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
