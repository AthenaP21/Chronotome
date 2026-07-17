"""In-memory CSV, figure, and ZIP exports for the Streamlit app."""

from __future__ import annotations

import io
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import sys
from typing import Iterable

import pandas as pd

from .io import INTERNAL_SOURCE_FILE_COLUMN


MAX_RASTER_SIDE_PX = 7200
_RASTER_DPI_LIMIT = ContextVar("chronotome_raster_dpi_limit", default=None)
_RASTER_SIDE_LIMIT = ContextVar("chronotome_raster_side_limit", default=MAX_RASTER_SIDE_PX)
_LOGO_WATERMARK_ENABLED = ContextVar("chronotome_logo_watermark_enabled", default=True)
_LIST_LIKE_TYPES = (list, dict, tuple, set)
_DATABASE_EXPORT_ORDER = {"scopus": 0, "web of science": 1}


@contextmanager
def logo_watermark_policy(enabled=True):
    """Temporarily enable or disable logo watermarking for figure exports."""
    token = _LOGO_WATERMARK_ENABLED.set(bool(enabled))
    try:
        yield
    finally:
        _LOGO_WATERMARK_ENABLED.reset(token)


def _logo_watermark_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    candidates = (
        root / "assets" / "chronotome-logo.png",
        root / "chronotome-logo.png",
        Path(sys.prefix) / "share" / "chronotome" / "chronotome-logo.png",
    )
    return next((path for path in candidates if path.exists()), candidates[1])


@contextmanager
def _temporary_logo_watermark(figure):
    """Add a subtle logo watermark only while a figure is being exported."""
    watermark_axis = None
    path = _logo_watermark_path()
    if _LOGO_WATERMARK_ENABLED.get() and path.exists():
        try:
            import matplotlib.image as mpimg

            image = mpimg.imread(path)
            watermark_axis = figure.add_axes([0.855, 0.015, 0.125, 0.075], zorder=50)
            watermark_axis.imshow(image, alpha=0.18)
            watermark_axis.axis("off")
        except Exception:
            watermark_axis = None
    try:
        yield
    finally:
        if watermark_axis is not None:
            try:
                watermark_axis.remove()
            except Exception:
                pass


def _exportable_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Create only replacement columns needed for portable list-like values.

    A deep copy of a large article table can consume hundreds of megabytes.
    Shallow copying is safe here because converted columns are replaced rather
    than edited in place.
    """
    public_data = data.drop(columns=[INTERNAL_SOURCE_FILE_COLUMN], errors="ignore")
    export = public_data.copy(deep=False)
    for column in public_data.columns:
        series = public_data[column]
        if series.dtype != "object":
            continue
        if not any(isinstance(value, _LIST_LIKE_TYPES) for value in series.array):
            continue
        export[column] = series.map(
            lambda value: json.dumps(
                _deterministic_json_value(value, column=column),
                ensure_ascii=False,
                sort_keys=True,
            ) if isinstance(value, _LIST_LIKE_TYPES) else value
        )
    return export


def _deterministic_json_value(value, *, column: str | None = None):
    """Convert containers to stable JSON-compatible values without mutating them."""
    if isinstance(value, dict):
        return {
            str(key): _deterministic_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]).casefold())
        }
    if isinstance(value, set):
        items = sorted(value, key=lambda item: str(item).casefold())
        return [_deterministic_json_value(item) for item in items]
    if isinstance(value, (list, tuple)):
        items = list(value)
        if column == "Databases":
            seen = {}
            for item in items:
                text = str(item).strip()
                if text:
                    seen.setdefault(text.casefold(), text)
            items = sorted(
                seen.values(),
                key=lambda item: (_DATABASE_EXPORT_ORDER.get(item.casefold(), 99), item.casefold()),
            )
        elif column == "Source Files":
            seen = {}
            for item in items:
                text = str(item).strip()
                if text:
                    seen.setdefault(text.casefold(), text)
            items = list(seen.values())
        return [_deterministic_json_value(item) for item in items]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


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
    with _temporary_logo_watermark(figure):
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
    with _temporary_logo_watermark(figure):
        figure.savefig(buffer, format="pdf", bbox_inches="tight")
    return buffer.getvalue()


def figure_svg(figure) -> bytes:
    """Render a resolution-independent SVG for sharp browser previews."""
    buffer = io.BytesIO()
    with _temporary_logo_watermark(figure):
        figure.savefig(buffer, format="svg", bbox_inches="tight")
    return buffer.getvalue()
