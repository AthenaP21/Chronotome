"""Responsive, resolution-independent figure previews for Streamlit."""

from __future__ import annotations

import streamlit as st


def render_svg(svg_bytes: bytes) -> None:
    """Embed trusted Matplotlib SVG output at the available page width."""
    svg = svg_bytes.decode("utf-8")
    start = svg.find("<svg")
    if start < 0:
        raise ValueError("The generated figure does not contain an SVG root element.")
    svg = svg[start:]
    svg = svg.replace(
        "<svg ",
        '<svg style="width:100%;height:auto;display:block;" ',
        1,
    )
    st.markdown(
        f'<div style="width:100%;overflow-x:auto;">{svg}</div>',
        unsafe_allow_html=True,
    )
