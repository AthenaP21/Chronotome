"""Small browser-navigation helpers shared by the Streamlit pages."""

from __future__ import annotations

import streamlit.components.v1 as components


def scroll_to_top(token: str | None = None) -> None:
    """Reset Streamlit's hosted scroll containers and the browser viewport.

    Hosted deployments can wrap Streamlit in slightly different DOM containers
    than local runs. The script therefore retries briefly and scrolls every
    plausible parent/document container instead of relying on one selector.
    """
    _ = token  # Kept for call-site clarity; older Streamlit components.html has no key argument.
    components.html(
        """
        <script>
        const scrollTopNow = () => {
          const parentWindow = window.parent || window;
          const doc = parentWindow.document;
          const selectors = [
            '[data-testid="stMain"]',
            '[data-testid="stAppViewContainer"]',
            '[data-testid="stVerticalBlock"]',
            'section.main',
            '.main',
            'main'
          ];
          const targets = new Set([
            parentWindow,
            doc.scrollingElement,
            doc.documentElement,
            doc.body,
            ...selectors.flatMap((selector) => Array.from(doc.querySelectorAll(selector)))
          ]);

          targets.forEach((target) => {
            if (!target) return;
            try {
              if (typeof target.scrollTo === 'function') {
                target.scrollTo({top: 0, left: 0, behavior: 'auto'});
              } else {
                target.scrollTop = 0;
                target.scrollLeft = 0;
              }
            } catch (error) {}
          });
        };

        scrollTopNow();
        [25, 100, 250, 500, 900].forEach((delay) => {
          window.setTimeout(scrollTopNow, delay);
        });
        </script>
        """,
        height=1,
        width=0,
    )
