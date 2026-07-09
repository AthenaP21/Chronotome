"""Chronotome landing page."""

import streamlit as st

from chronotome_ui.navigation import navigate_to_page


def render_home():
    """Render project context, outputs, archive information, and citation."""
    st.title("Chronotome: A Reproducible Bibliometric Workflow")
    st.markdown(
        "Chronotome is an end-to-end, reproducible workflow for bibliometric and "
        "scientometric analysis using **Scopus** and **Web of Science** exports."
    )

    st.markdown("### What you get at the end")
    first, second, third = st.columns(3)
    with first:
        st.markdown("#### Merged research corpus")
        st.write("A harmonized and deduplicated bibliographic dataset, exportable as CSV and Excel.")
    with second:
        st.markdown("#### Transparent screening")
        st.write("PRISMA-style counts from identification through deduplication to the included dataset.")
    with third:
        st.markdown("#### Reproducible analyses")
        st.write("Country, journal, impact, thematic, and collaboration analyses with publication-grade figures.")

    st.info(
        "**New to bibliometrics?** Start with Data ingestion. Chronotome replaces local file paths "
        "and code switches with guided controls, validation messages, and downloads."
    )

    st.divider()
    st.markdown("## Open-science release (Zenodo)")
    st.markdown(
        "Chronotome is part of the **Chronotome / Open Bibliometrics** open-science release "
        "archived on Zenodo."
    )
    st.link_button("Open Zenodo record — DOI 10.5281/zenodo.17514930", "https://doi.org/10.5281/zenodo.17514930")

    archive, resource = st.columns([1, 1])
    with archive:
        st.markdown("### What the archive contains")
        st.write("The reproducible workflow and supporting resources.")
    with resource:
        st.markdown("### Curated entity resolution")
        st.write(
            "`institutions.json` provides the curated institution alias map used by Chronotome's "
            "entity-resolution step. It is bundled with this app."
        )

    st.markdown("### Suggested citation")
    st.code(
        "Popescu-Apreutesei, L.-E., & Iosupescu, M.-S. (2025). "
        "Chronotome. Zenodo. https://doi.org/10.5281/zenodo.17514930",
        language=None,
    )

    st.divider()
    if st.button("Start data ingestion", type="primary"):
        navigate_to_page("Data ingestion")
