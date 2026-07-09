"""Chronotome brand styling."""

from __future__ import annotations

from pathlib import Path
import base64

import streamlit as st


BRAND = {
    "green": "#23443C",
    "green_dark": "#102720",
    "green_deep": "#17352F",
    "gold": "#C6A04A",
    "paper": "#F7F3E8",
    "paper_muted": "#D8CEB4",
    "text": "#263238",
    "burgundy": "#8A3A44",
}

def logo_path() -> Path:
    """Return the preferred logo path inside the repository."""
    root = Path(__file__).resolve().parents[1]
    preferred = root / "assets" / "chronotome-logo.png"
    if preferred.exists():
        return preferred
    return root / "chronotome-logo.png"


def apply_brand_theme() -> None:
    """Apply Chronotome's fixed dark archive interface."""
    st.markdown(
        f"""
        <style>
        :root {{
          --chronotome-bg: {BRAND["green_dark"]};
          --chronotome-surface: {BRAND["green"]};
          --chronotome-surface-soft: {BRAND["green_deep"]};
          --chronotome-text: {BRAND["paper"]};
          --chronotome-muted: {BRAND["paper_muted"]};
          --chronotome-primary: {BRAND["gold"]};
          --chronotome-secondary: {BRAND["paper"]};
          --chronotome-warning: {BRAND["burgundy"]};
        }}
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        section.main {{
          background: var(--chronotome-bg);
          color: var(--chronotome-text);
        }}
        [data-testid="stSidebar"] {{
          background: {BRAND["green"]};
          border-right: 1px solid rgba(198, 160, 74, 0.40);
        }}
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"] {{
          background: {BRAND["green"]};
        }}
        .stApp p,
        .stApp span,
        .stApp label,
        .stApp li,
        .stApp div[data-testid="stMarkdownContainer"],
        .stApp [data-testid="stCaptionContainer"] {{
          color: var(--chronotome-text);
        }}
        .stApp small,
        .stApp .caption,
        .stApp [data-testid="stCaptionContainer"] {{
          color: var(--chronotome-muted);
        }}
        [data-testid="stSidebar"] * {{
          color: {BRAND["paper"]};
        }}
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {{
          color: {BRAND["paper"]};
        }}
        [data-testid="stSidebar"] [data-baseweb="radio"] label,
        [data-testid="stSidebar"] [data-baseweb="checkbox"] label {{
          color: {BRAND["paper"]};
        }}
        [data-testid="stSidebar"] [data-baseweb="radio"] div,
        [data-testid="stSidebar"] [data-baseweb="checkbox"] div {{
          border-color: {BRAND["gold"]};
        }}
        [data-testid="stSidebar"] [data-baseweb="select"],
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] textarea,
        .stApp [data-baseweb="select"],
        .stApp [data-baseweb="input"],
        .stApp textarea {{
          background-color: var(--chronotome-surface-soft);
          border-color: rgba(198, 160, 74, 0.65);
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] *,
        [data-testid="stSidebar"] [data-baseweb="input"] *,
        [data-testid="stSidebar"] textarea,
        .stApp [data-baseweb="select"] *,
        .stApp [data-baseweb="input"] *,
        .stApp textarea {{
          color: {BRAND["paper"]};
          -webkit-text-fill-color: {BRAND["paper"]};
        }}
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] .stCaptionContainer {{
          color: rgba(247, 243, 232, 0.82);
        }}
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] ul,
        div[data-baseweb="menu"],
        ul[role="listbox"],
        div[role="listbox"] {{
          background-color: #FFFDF6 !important;
        }}
        div[data-baseweb="popover"] *,
        div[data-baseweb="menu"] *,
        ul[role="listbox"] *,
        div[role="listbox"] *,
        div[role="option"],
        div[role="option"] * {{
          color: {BRAND["text"]} !important;
          -webkit-text-fill-color: {BRAND["text"]} !important;
        }}
        div[role="option"]:hover,
        div[role="option"][aria-selected="true"] {{
          background-color: rgba(198, 160, 74, 0.18) !important;
        }}
        [data-baseweb="select"] svg {{
          color: {BRAND["paper"]} !important;
          fill: {BRAND["paper"]} !important;
        }}
        h1, h2, h3 {{
          color: var(--chronotome-primary);
        }}
        h4, h5, h6 {{
          color: var(--chronotome-secondary);
        }}
        hr {{
          border-color: rgba(198, 160, 74, 0.26);
        }}
        [data-testid="stExpander"] {{
          background: rgba(23, 53, 47, 0.82);
          border: 1px solid rgba(198, 160, 74, 0.22);
          border-radius: 0.75rem;
        }}
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary * {{
          color: var(--chronotome-text);
        }}
        div[data-testid="stMetric"] {{
          background: rgba(23, 53, 47, 0.90);
          border: 1px solid rgba(198, 160, 74, 0.24);
          border-radius: 0.85rem;
          padding: 0.65rem 0.8rem;
        }}
        div[data-testid="stMetric"] * {{
          color: var(--chronotome-text);
        }}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
          color: var(--chronotome-primary);
        }}
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {{
          background-color: var(--chronotome-primary);
          border-color: var(--chronotome-primary);
          color: {BRAND["green_dark"]};
          font-weight: 700;
        }}
        .stButton > button,
        .stDownloadButton > button {{
          background-color: rgba(16, 39, 32, 0.72);
          border-color: rgba(198, 160, 74, 0.45);
          color: var(--chronotome-text);
        }}
        .stButton > button:hover,
        .stDownloadButton > button:hover {{
          border-color: var(--chronotome-secondary);
          color: var(--chronotome-primary);
        }}
        [data-testid="stAlert"] {{
          background: rgba(247, 243, 232, 0.08);
          color: var(--chronotome-text);
          border-color: rgba(198, 160, 74, 0.25);
        }}
        [data-testid="stDataFrame"] {{
          background: #FFFDF6;
          border-radius: 0.65rem;
          overflow: hidden;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """Render the compact brand block reserved for the main workflow sidebar."""
    path = logo_path()
    if path.exists():
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        st.markdown(
            f"""
            <div style="
                background:rgba(247,243,232,0.92);
                border:1px solid rgba(198,160,74,0.55);
                border-radius:18px;
                padding:0.75rem 0.9rem;
                margin:0.25rem 0 1.15rem 0;
                box-shadow:0 10px 28px rgba(0,0,0,0.16);">
                <img src="data:image/png;base64,{encoded}" style="width:100%;display:block;" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="
                font-size:1.55rem;font-weight:750;letter-spacing:0.02em;
                color:{BRAND["green"]};margin-bottom:0.1rem;">
                Chronotome
            </div>
            <div style="color:{BRAND["gold"]};font-size:0.85rem;margin-bottom:0.65rem;">
                bibliometric time maps
            </div>
            """,
            unsafe_allow_html=True,
        )
