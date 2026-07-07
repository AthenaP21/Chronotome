"""Small browser-navigation helpers shared by the Streamlit pages."""

from __future__ import annotations

import streamlit.components.v1 as components


def scroll_to_top() -> None:
    """Reset both the Streamlit scroll container and browser viewport."""
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const main = doc.querySelector('[data-testid="stMain"]') ||
                     doc.querySelector('[data-testid="stAppViewContainer"]');
        if (main) main.scrollTo({top: 0, left: 0, behavior: 'instant'});
        window.parent.scrollTo({top: 0, left: 0, behavior: 'instant'});
        </script>
        """,
        height=0,
        width=0,
    )
