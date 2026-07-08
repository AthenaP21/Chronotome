"""In-memory CSV, figure, and ZIP exports for the Streamlit app."""

from __future__ import annotations

import io
import json
import zipfile
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterable

import pandas as pd


MAX_RASTER_SIDE_PX = 7200
_RASTER_DPI_LIMIT = ContextVar("chronotome_raster_dpi_limit", default=None)
_RASTER_SIDE_LIMIT = ContextVar("chronotome_raster_side_limit", default=MAX_RASTER_SIDE_PX)
_LIST_LIKE_TYPES = (list, dict, tuple, set)


def _exportable_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Create only replacement columns needed for portable list-like values.

    A deep copy of a large article table can consume hundreds of megabytes.
    Shallow copying is safe here because converted columns are replaced rather
    than edited in place.
    """
    export = data.copy(deep=False)
    for column in data.columns:
        series = data[column]
        if series.dtype != "object":
            continue
        if not any(isinstance(value, _LIST_LIKE_TYPES) for value in series.array):
            continue
        export[column] = series.map(
            lambda value: json.dumps(
                list(value) if isinstance(value, set) else value, ensure_ascii=False
            ) if isinstance(value, _LIST_LIKE_TYPES) else value
        )
    return export


def dataframe_csv(data: pd.DataFrame) -> bytes:
    """Serialize a DataFrame as Excel-friendly UTF-8 CSV."""
    export = _exportable_frame(data)
    buffer = io.BytesIO()
    text = io.TextIOWrapper(buffer, encoding="utf-8-sig", newline="", write_through=True)
    export.to_csv(text, index=False)
    text.flush()
    text.detach()
    return buffer.getvalue()


def dataframe_excel(data: pd.DataFrame, sheet_name="Chronotome") -> bytes:
    """Serialize a DataFrame as an in-memory XLSX workbook."""
    export = _exportable_frame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


@contextmanager
def raster_export_policy(max_dpi=None, max_side_px=MAX_RASTER_SIDE_PX):
    """Temporarily bound raster exports without changing vector output or plot layout."""
    dpi_token = _RASTER_DPI_LIMIT.set(max_dpi)
    side_token = _RASTER_SIDE_LIMIT.set(max_side_px)
    try:
        yield
    finally:
        _RASTER_DPI_LIMIT.reset(dpi_token)
        _RASTER_SIDE_LIMIT.reset(side_token)


def effective_png_dpi(figure, requested_dpi=220, max_side_px=None) -> int:
    """Cap oversized raster canvases while retaining requested DPI for normal figures."""
    policy_dpi = _RASTER_DPI_LIMIT.get()
    if policy_dpi is not None:
        requested_dpi = min(int(requested_dpi), int(policy_dpi))
    if max_side_px is None:
        max_side_px = _RASTER_SIDE_LIMIT.get()
    width, height = map(float, figure.get_size_inches())
    longest_inches = max(width, height, 1e-9)
    bounded = int(max_side_px / longest_inches)
    return max(150, min(int(requested_dpi), bounded))


def figure_png(figure, dpi=220, max_side_px=None) -> bytes:
    """Render PNG bytes with a publication-grade bounded pixel canvas."""
    buffer = io.BytesIO()
    figure.savefig(
        buffer, format="png",
        dpi=effective_png_dpi(figure, dpi, max_side_px=max_side_px),
        bbox_inches="tight",
    )
    return buffer.getvalue()


def release_figures(figures: Iterable) -> None:
    """Close figures and drop cached Agg renderers after all exports are complete."""
    import matplotlib.pyplot as plt
    from matplotlib.backend_bases import FigureCanvasBase

    for figure in figures:
        if figure is None:
            continue
        plt.close(figure)
        canvas = getattr(figure, "canvas", None)
        if canvas is not None and hasattr(canvas, "renderer"):
            try:
                canvas.renderer = None
            except Exception:
                pass
        # Preserve axes/artists for lightweight introspection while releasing
        # the backend-specific pixel renderer retained by FigureCanvasAgg.
        FigureCanvasBase(figure)


def figure_pdf(figure) -> bytes:
    """Render a Matplotlib figure to PDF bytes."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="pdf", bbox_inches="tight")
    return buffer.getvalue()


def figure_svg(figure) -> bytes:
    """Render a resolution-independent SVG for sharp browser previews."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight")
    return buffer.getvalue()


def create_exports(processed_data, tables, figures) -> dict[str, bytes]:
    """Create individual files and a ZIP containing every generated output."""
    files: dict[str, bytes] = {"cleaned_bibliometric_dataset.csv": dataframe_csv(processed_data)}
    for name, table in tables.items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            files[f"tables/{name}.csv"] = dataframe_csv(table)
    for name, figure in figures.items():
        files[f"figures/{name}.png"] = figure_png(figure)
        files[f"figures/{name}.svg"] = figure_svg(figure)
        files[f"figures/{name}.pdf"] = figure_pdf(figure)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    files["chronotome_outputs.zip"] = buffer.getvalue()
    return files
