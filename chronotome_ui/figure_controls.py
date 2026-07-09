"""Reusable per-figure controls for Chronotome graph previews."""

from __future__ import annotations

import copy
import textwrap

import streamlit as st

from chronotome_core.export import figure_pdf, figure_png, figure_svg, logo_watermark_policy
from chronotome_ui.figure_preview import render_svg


def _default_title(figure) -> str:
    if getattr(figure, "_suptitle", None) is not None:
        return figure._suptitle.get_text()
    for axis in figure.axes:
        title = axis.get_title()
        if title:
            return title
    return ""


def _set_title(figure, title: str) -> None:
    if getattr(figure, "_suptitle", None) is not None:
        figure._suptitle.set_text(title)
        return
    for axis in figure.axes:
        if axis.get_title():
            axis.set_title(title)
            return
    if figure.axes:
        figure.axes[0].set_title(title)


def _wrap(text: str, length: int) -> str:
    text = str(text)
    if length <= 0 or len(text) <= length:
        return text
    return "\n".join(textwrap.wrap(text, width=length, break_long_words=False))


def _apply_label_wrapping(figure, length: int) -> None:
    for axis in figure.axes:
        for label in axis.get_xticklabels():
            label.set_text(_wrap(label.get_text(), length))
        for label in axis.get_yticklabels():
            label.set_text(_wrap(label.get_text(), length))


def customized_figure(figure, prefix: str, *, show_controls: bool = True):
    """Return a copy of a figure after optional title and label edits."""
    edited = copy.deepcopy(figure)
    default_title = _default_title(edited)
    wrap_length = 0
    title_enabled = False
    title_value = default_title

    if show_controls:
        with st.expander("Customize this graph", expanded=False):
            wrap_length = st.number_input(
                "Wrap long labels after",
                min_value=0, max_value=120, value=0,
                help="Use 0 to keep labels exactly as generated.",
                key=f"{prefix}-wrap",
            )
            title_enabled = st.toggle(
                "Edit graph title",
                value=False,
                key=f"{prefix}-title-enabled",
            )
            title_value = st.text_area(
                "Graph title",
                value=default_title,
                disabled=not title_enabled,
                height=90,
                key=f"{prefix}-title",
            )

    if int(wrap_length) > 0:
        _apply_label_wrapping(edited, int(wrap_length))
    if title_enabled:
        _set_title(edited, title_value)
    try:
        edited.tight_layout()
    except Exception:
        pass
    return edited


def render_customizable_figure(
    exports: dict,
    basename: str,
    prefix: str,
    figure=None,
    missing_message: str = "No figure could be produced for this dataset.",
) -> None:
    """Render a figure with optional per-user customizations and full downloads."""
    png_path = f"Plots/{basename}.png"
    svg_path = f"Plots/{basename}.svg"
    pdf_path = f"Plots/{basename}.pdf"
    if png_path not in exports and svg_path not in exports:
        st.warning(missing_message)
        return

    customize = False
    if figure is not None:
        customize = st.toggle(
            "Customize title and labels",
            value=False,
            key=f"{prefix}-customize",
            help="The graph keeps its original colors. Use this only if you want to edit the title or wrap long labels.",
        )

    if figure is not None and customize:
        edited = customized_figure(figure, prefix, show_controls=True)
        with logo_watermark_policy(True):
            svg_bytes = figure_svg(edited)
            png_bytes = figure_png(edited, dpi=600)
            pdf_bytes = figure_pdf(edited)
        render_svg(svg_bytes)
        left, middle, right = st.columns(3)
        left.download_button(
            "Download 600-DPI PNG",
            png_bytes,
            f"{basename}.png",
            "image/png",
            key=f"{prefix}-custom-png",
        )
        middle.download_button(
            "Download vector SVG",
            svg_bytes,
            f"{basename}.svg",
            "image/svg+xml",
            key=f"{prefix}-custom-svg",
        )
        right.download_button(
            "Download vector PDF",
            pdf_bytes,
            f"{basename}.pdf",
            "application/pdf",
            key=f"{prefix}-custom-pdf",
        )
        return

    if svg_path in exports:
        render_svg(exports[svg_path])
    else:
        st.image(exports[png_path], width="stretch")
    columns = st.columns(3 if svg_path in exports else 2)
    left, right = columns[0], columns[-1]
    left.download_button(
        "Download 600-DPI PNG",
        exports[png_path],
        f"{basename}.png",
        "image/png",
        key=f"{prefix}-png",
    )
    if svg_path in exports:
        columns[1].download_button(
            "Download vector SVG",
            exports[svg_path],
            f"{basename}.svg",
            "image/svg+xml",
            key=f"{prefix}-svg",
        )
    if pdf_path in exports:
        right.download_button(
            "Download vector PDF",
            exports[pdf_path],
            f"{basename}.pdf",
            "application/pdf",
            key=f"{prefix}-pdf",
        )
