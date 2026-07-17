"""Session-state lifecycle helpers for bounded-memory analytical handoffs."""

from __future__ import annotations

import gc

import streamlit as st


_GROUPS = {
    "entity": (
        "entity_resolution_results", "entity_resolution_signature",
    ),
    "corpus": (
        "corpus_bibliometrics_results", "corpus_bibliometrics_signature",
    ),
    "geographic": (
        "geographic_analysis_results", "geographic_analysis_signature",
        "geographic_case_result", "geographic_case_token", "geographic_view",
    ),
    "advanced": (
        "advanced_component_results",
    ),
    "thematic": (
        "thematic_preprocessing_results", "thematic_preprocessing_signature",
        "topic_evaluation_results", "topic_evaluation_signature",
        "final_topic_model_results", "advanced_thematic_results",
        "advanced_thematic_signature",
    ),
    "institutional": (
        "institutional-analysis-cache", "institutional-analysis-results",
        "institutional-active-signature", "institutional-topic-cache",
        "institutional-community-cache", "institutional-view",
    ),
    "full": (
        "full_workflow_results", "full_workflow_signature",
    ),
}

_ORDER = ("entity", "corpus", "geographic", "advanced", "thematic", "institutional", "full")


def clear_downstream_state(after_stage: str) -> None:
    """Drop stale results after a newly completed upstream stage."""
    start = {
        "ingestion": 0, "entity": 1, "corpus": 2, "geographic": 3,
        "advanced": 4, "thematic": 5,
    }.get(after_stage)
    if start is None:
        return
    for group in _ORDER[start:]:
        for key in _GROUPS[group]:
            st.session_state.pop(key, None)
    gc.collect()
