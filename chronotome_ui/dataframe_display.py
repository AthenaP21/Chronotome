"""Safe dataframe display helpers for hosted Streamlit runtimes."""

from __future__ import annotations

import json
from functools import wraps

import pandas as pd
import streamlit as st


_LIST_LIKE = (list, tuple, set, dict)
_PROVENANCE_LIST_COLUMNS = {"Databases", "Source Files"}


def _display_value(value):
    if isinstance(value, set):
        value = sorted(value)
    if isinstance(value, _LIST_LIKE):
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)
    return value


def _is_missing(value) -> bool:
    if isinstance(value, _LIST_LIKE):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def arrow_safe_frame(data):
    """Return a shallow display copy with Arrow-hostile object columns normalized."""
    if not isinstance(data, pd.DataFrame):
        return data
    display = data.copy(deep=False)
    for column in display.columns:
        series = display[column]
        if column in _PROVENANCE_LIST_COLUMNS:
            display[column] = series.map(
                lambda value: "; ".join(
                    str(item).strip()
                    for item in (sorted(value) if isinstance(value, set) else value)
                    if str(item).strip()
                )
                if isinstance(value, (list, tuple, set))
                else ("" if _is_missing(value) else str(value))
            )
            continue
        if series.dtype != "object":
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        has_list_like = non_null.map(lambda value: isinstance(value, _LIST_LIKE)).any()
        scalar_types = {
            type(value)
            for value in non_null.head(1000)
            if not isinstance(value, _LIST_LIKE)
        }
        if has_list_like or len(scalar_types) > 1:
            display[column] = series.map(
                lambda value: "" if _is_missing(value) else str(_display_value(value))
            )
    return display


def _normalize_dataframe_kwargs(kwargs: dict) -> dict:
    kwargs = dict(kwargs)
    if "use_container_width" in kwargs and "width" not in kwargs:
        kwargs["width"] = "stretch" if kwargs.pop("use_container_width") else "content"
    else:
        kwargs.pop("use_container_width", None)
    return kwargs


def install_safe_dataframe_display() -> None:
    """Patch Streamlit dataframe display once for cleaner hosted logs."""
    if getattr(st, "_chronotome_safe_dataframe_installed", False):
        return
    original_dataframe = st.dataframe

    @wraps(original_dataframe)
    def safe_dataframe(data=None, *args, **kwargs):
        return original_dataframe(arrow_safe_frame(data), *args, **_normalize_dataframe_kwargs(kwargs))

    st.dataframe = safe_dataframe
    st._chronotome_safe_dataframe_installed = True
