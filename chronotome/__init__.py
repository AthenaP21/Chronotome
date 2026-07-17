"""Chronotome's local application launcher and reusable bibliometric workflow."""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["run_chronotome", "__version__"]


def __getattr__(name: str):
    """Load the optional programmatic workflow API only when it is requested."""
    if name == "run_chronotome":
        from chronotome_core import run_chronotome

        return run_chronotome
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
