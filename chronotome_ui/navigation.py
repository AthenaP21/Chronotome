"""Small browser-navigation helpers shared by the Streamlit pages."""

from __future__ import annotations

import json

import streamlit.components.v1 as components
import streamlit as st


def request_scroll_to_top(*, rerun: bool = True) -> None:
    """Ask the app shell to scroll to the top on the next render."""
    st.session_state["_chronotome_scroll_top"] = True
    if rerun:
        st.rerun()


def navigate_to_page(page: str) -> None:
    """Navigate to a workflow page and reset the viewport."""
    st.session_state["_chronotome_navigate_to"] = page
    st.session_state["_chronotome_scroll_top"] = True
    st.rerun()


def scroll_to_top(token: str | None = None) -> None:
    """Reset Streamlit's hosted scroll containers and the browser viewport."""
    token_json = json.dumps(str(token or "chronotome-scroll"))
    html = """
        <script>
        const chronotomeScrollToken = __CHRONOTOME_SCROLL_TOKEN__;
        const collectScrollableElements = (doc) => {
          const elements = Array.from(doc.querySelectorAll('*'));
          return elements.filter((element) => {
            try {
              const style = doc.defaultView.getComputedStyle(element);
              const overflowY = style.overflowY;
              return (
                element.scrollHeight > element.clientHeight &&
                ['auto', 'scroll', 'overlay'].includes(overflowY)
              );
            } catch (error) {
              return false;
            }
          });
        };

        const scrollTarget = (target) => {
          if (!target) return;
          try {
            if (typeof target.scrollTo === 'function') {
              target.scrollTo({top: 0, left: 0, behavior: 'auto'});
            } else {
              target.scrollTop = 0;
              target.scrollLeft = 0;
            }
          } catch (error) {}
        };

        const scrollTopNow = () => {
          const windows = [window, window.parent, window.top].filter(Boolean);
          const selectors = [
            '#chronotome-page-top',
            '[data-testid="stMainBlockContainer"]',
            '[data-testid="stDecoration"]',
            '[data-testid="stMain"]',
            '[data-testid="stAppViewContainer"]',
            '[data-testid="stVerticalBlock"]',
            '[data-testid="stApp"]',
            '.stMainBlockContainer',
            '.block-container',
            'section.main',
            '.main',
            'main'
          ];

          windows.forEach((targetWindow) => {
            try {
              const doc = targetWindow.document;
              const anchor = doc.querySelector('#chronotome-page-top');
              if (anchor && typeof anchor.scrollIntoView === 'function') {
                anchor.scrollIntoView({block: 'start', inline: 'nearest', behavior: 'auto'});
              }
              const targets = new Set([
                targetWindow,
                doc.scrollingElement,
                doc.documentElement,
                doc.body,
                ...selectors.flatMap((selector) => Array.from(doc.querySelectorAll(selector))),
                ...collectScrollableElements(doc)
              ]);
              targets.forEach(scrollTarget);
            } catch (error) {}
          });
        };

        scrollTopNow();
        </script>
        """.replace("__CHRONOTOME_SCROLL_TOKEN__", token_json)
    components.html(html, height=1, width=1)
