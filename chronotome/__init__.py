"""Chronotome's local application launcher and reusable bibliometric workflow."""

from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["DEFAULT_CONFIG", "resolve_config", "run_chronotome", "__version__"]


def __getattr__(name: str):
    """Load the optional programmatic workflow API only when it is requested."""
    if name in {"DEFAULT_CONFIG", "resolve_config", "run_chronotome"}:
        from chronotome_core import DEFAULT_CONFIG, resolve_config, run_chronotome

        return {
            "DEFAULT_CONFIG": DEFAULT_CONFIG,
            "resolve_config": resolve_config,
            "run_chronotome": run_chronotome,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
