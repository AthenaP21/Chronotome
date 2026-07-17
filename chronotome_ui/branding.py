"""Chronotome brand styling."""

from __future__ import annotations

from pathlib import Path
import base64
import sys

import streamlit as st


BRAND = {
    "green": "#23443C",
    "green_dark": "#102720",
    "green_deep": "#17352F",
    "gold": "#C6A04A",
    "paper": "#F7F3E8",
    "paper_muted": "#D8CEB4",
    "burgundy": "#8A3A44",
}

LIGHT = {
    "background": "#F7F3E8",
    "surface": "#FFFFFF",
    "surface_soft": "#E9E2D2",
    "sidebar": "#DED6C3",
    "text": "#263238",
    "muted": "#59645F",
    "accent": "#23443C",
    "border": "#9B8B64",
}

def logo_path() -> Path:
    """Return the bundled logo, with repository paths retained for development."""
    packaged = Path(__file__).with_name("chronotome-logo.png")
    if packaged.exists():
        return packaged
    root = Path(__file__).resolve().parents[1]
    candidates = (
        Path(__file__).with_name("chronotome-logo.png"),
        root / "assets" / "chronotome-logo.png",
        root / "chronotome-logo.png",
        Path(sys.prefix) / "share" / "chronotome" / "chronotome-logo.png",
    )
    return next((path for path in candidates if path.exists()), candidates[2])


def apply_brand_theme() -> None:
    """Apply Chronotome's dark and light archive interfaces."""
    theme_type = getattr(getattr(st, "context", None), "theme", {}).get("type")
    light_active = theme_type == "light"
    active = LIGHT if light_active else {
        "background": BRAND["green_dark"],
        "surface": BRAND["green"],
        "surface_soft": BRAND["green_deep"],
        "sidebar": BRAND["green"],
        "text": BRAND["paper"],
        "muted": BRAND["paper_muted"],
        "accent": BRAND["gold"],
        "border": BRAND["gold"],
    }
    on_accent = LIGHT["background"] if light_active else BRAND["green_dark"]
    color_scheme = "light" if light_active else "dark"
    st.markdown(
        f"""
        <style>
        :root {{
          color-scheme: {color_scheme} !important;
          --chronotome-background: {active["background"]};
          --chronotome-surface: {active["surface"]};
          --chronotome-surface-soft: {active["surface_soft"]};
          --chronotome-sidebar: {active["sidebar"]};
          --chronotome-text: {active["text"]};
          --chronotome-muted: {active["muted"]};
          --chronotome-accent: {active["accent"]};
          --chronotome-on-accent: {on_accent};
          --chronotome-warning: {BRAND["burgundy"]};
          --background-color: {active["background"]} !important;
          --secondary-background-color: {active["surface_soft"]} !important;
          --text-color: {active["text"]} !important;
          --primary-color: {active["accent"]} !important;
        }}
        [data-theme="dark"] {{
          color-scheme: dark !important;
          --chronotome-background: {BRAND["green_dark"]};
          --chronotome-surface: {BRAND["green"]};
          --chronotome-surface-soft: {BRAND["green_deep"]};
          --chronotome-text: {BRAND["paper"]};
          --chronotome-muted: {BRAND["paper_muted"]};
          --chronotome-accent: {BRAND["gold"]};
          --chronotome-on-accent: {BRAND["green_dark"]};
          --chronotome-warning: {BRAND["burgundy"]};
          --background-color: {BRAND["green_dark"]} !important;
          --secondary-background-color: {BRAND["green_deep"]} !important;
          --text-color: {BRAND["paper"]} !important;
          --primary-color: {BRAND["gold"]} !important;
        }}
        [data-theme="light"] {{
          color-scheme: light !important;
          --chronotome-background: {LIGHT["background"]};
          --chronotome-surface: {LIGHT["surface"]};
          --chronotome-surface-soft: {LIGHT["surface_soft"]};
          --chronotome-sidebar: {LIGHT["sidebar"]};
          --chronotome-text: {LIGHT["text"]};
          --chronotome-muted: {LIGHT["muted"]};
          --chronotome-accent: {LIGHT["accent"]};
          --chronotome-on-accent: {LIGHT["background"]};
          --chronotome-warning: {BRAND["burgundy"]};
          --background-color: {LIGHT["background"]} !important;
          --secondary-background-color: {LIGHT["surface_soft"]} !important;
          --text-color: {LIGHT["text"]} !important;
          --primary-color: {LIGHT["accent"]} !important;
        }}
        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        section.main {{
          background: var(--chronotome-background) !important;
          color: var(--chronotome-text);
        }}
        [data-testid="stHeader"],
        [data-testid="stToolbar"] {{
          background: transparent !important;
          color: var(--chronotome-text) !important;
        }}
        [data-testid="stSidebar"] {{
          background: var(--chronotome-sidebar, {BRAND["green"]});
          border-right: 1px solid rgba(198, 160, 74, 0.40);
        }}
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"] {{
          background: var(--chronotome-sidebar, {BRAND["green"]});
        }}
        .stApp p,
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
          color: var(--chronotome-text);
        }}
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {{
          color: var(--chronotome-text);
        }}
        [data-testid="stSidebar"] [data-baseweb="radio"] label,
        [data-testid="stSidebar"] [data-baseweb="checkbox"] label {{
          color: var(--chronotome-text);
        }}
        [data-testid="stSidebar"] [data-baseweb="radio"] div,
        [data-testid="stSidebar"] [data-baseweb="checkbox"] div {{
          border-color: var(--chronotome-accent);
        }}
        [data-testid="stSidebar"] [data-baseweb="select"],
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] textarea,
        .stApp [data-baseweb="select"],
        .stApp [data-baseweb="input"],
        .stApp textarea,
        .stApp input,
        .stApp [data-testid="stNumberInput"] > div,
        .stApp [data-testid="stTextInput"] > div {{
          background-color: var(--chronotome-surface-soft) !important;
          border-color: rgba(198, 160, 74, 0.65);
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] *,
        [data-testid="stSidebar"] [data-baseweb="input"] *,
        [data-testid="stSidebar"] textarea,
        .stApp [data-baseweb="select"] *,
        .stApp [data-baseweb="input"] *,
        .stApp textarea,
        .stApp input {{
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
          caret-color: var(--chronotome-accent);
          opacity: 1 !important;
        }}
        .stApp [data-baseweb="select"] > div,
        .stApp [data-baseweb="select"] [role="combobox"],
        .stApp [data-baseweb="select"] [data-baseweb="tag"],
        .stApp [data-testid="stSelectbox"] > div > div,
        .stApp [data-testid="stMultiSelect"] > div > div {{
          background-color: var(--chronotome-surface-soft) !important;
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
          opacity: 1 !important;
        }}
        .stApp input::placeholder,
        .stApp textarea::placeholder {{
          color: var(--chronotome-muted) !important;
          -webkit-text-fill-color: var(--chronotome-muted) !important;
          opacity: 0.82 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] .stCaptionContainer {{
          color: var(--chronotome-muted);
        }}
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] ul,
        div[data-baseweb="menu"],
        ul[role="listbox"],
        div[role="listbox"] {{
          background-color: var(--chronotome-surface-soft) !important;
          border-color: rgba(198, 160, 74, 0.55) !important;
        }}
        div[data-baseweb="popover"] *,
        div[data-baseweb="menu"] *,
        ul[role="listbox"] *,
        div[role="listbox"] *,
        div[role="option"],
        div[role="option"] * {{
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
          opacity: 1 !important;
        }}
        div[role="option"]:hover,
        div[role="option"][aria-selected="true"] {{
          background-color: rgba(198, 160, 74, 0.22) !important;
        }}
        [data-baseweb="select"] svg {{
          color: var(--chronotome-text) !important;
          fill: var(--chronotome-text) !important;
        }}
        h1, h2, h3 {{
          color: var(--chronotome-accent);
        }}
        h4, h5, h6 {{
          color: var(--chronotome-text);
        }}
        .stApp a {{
          color: var(--chronotome-accent);
        }}
        .stApp a:hover {{
          color: var(--chronotome-text);
        }}
        .stLinkButton > a,
        [data-testid="stLinkButton"] > a {{
          background-color: var(--chronotome-surface-soft) !important;
          border: 1px solid rgba(198, 160, 74, 0.65) !important;
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
          text-decoration: none !important;
        }}
        .stLinkButton > a *,
        [data-testid="stLinkButton"] > a * {{
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
          opacity: 1 !important;
        }}
        .stLinkButton > a:hover,
        [data-testid="stLinkButton"] > a:hover {{
          border-color: var(--chronotome-accent) !important;
          color: var(--chronotome-accent) !important;
        }}
        .stLinkButton > a:hover *,
        [data-testid="stLinkButton"] > a:hover * {{
          color: var(--chronotome-accent) !important;
          -webkit-text-fill-color: var(--chronotome-accent) !important;
        }}
        hr {{
          border-color: rgba(198, 160, 74, 0.26);
        }}
        [data-testid="stExpander"] {{
          background: var(--chronotome-surface-soft);
          border: 1px solid rgba(198, 160, 74, 0.22);
          border-radius: 0.75rem;
        }}
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary * {{
          color: var(--chronotome-text);
        }}
        [data-testid="stForm"] {{
          background: var(--chronotome-surface-soft);
          border-color: rgba(198, 160, 74, 0.28);
        }}
        div[data-testid="stMetric"] {{
          background: var(--chronotome-surface-soft);
          border: 1px solid rgba(198, 160, 74, 0.24);
          border-radius: 0.85rem;
          padding: 0.65rem 0.8rem;
        }}
        div[data-testid="stMetric"] * {{
          color: var(--chronotome-text);
        }}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
          color: var(--chronotome-accent);
        }}
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {{
          background-color: var(--chronotome-accent);
          border-color: var(--chronotome-accent);
          color: var(--chronotome-on-accent);
          font-weight: 700;
        }}
        .stButton > button[kind="primary"] *,
        .stDownloadButton > button[kind="primary"] * {{
          color: var(--chronotome-on-accent) !important;
        }}
        .stButton > button,
        .stDownloadButton > button {{
          background-color: var(--chronotome-surface-soft);
          border-color: rgba(198, 160, 74, 0.45);
          color: var(--chronotome-text);
        }}
        .stButton > button:hover,
        .stDownloadButton > button:hover {{
          border-color: var(--chronotome-text);
          color: var(--chronotome-accent);
        }}
        .stButton > button:not([kind="primary"]) *,
        .stDownloadButton > button:not([kind="primary"]) * {{
          color: var(--chronotome-text) !important;
        }}
        [data-testid="stAlert"] {{
          background: var(--chronotome-surface-soft);
          color: var(--chronotome-text);
          border-color: rgba(198, 160, 74, 0.25);
        }}
        [data-testid="stDataFrame"] {{
          background: var(--chronotome-surface-soft);
          border-radius: 0.65rem;
          overflow: hidden;
        }}
        [data-testid="stTable"] {{
          background: var(--chronotome-surface-soft) !important;
          color: var(--chronotome-text) !important;
        }}
        [data-testid="stCode"],
        [data-testid="stCode"] pre,
        [data-testid="stCode"] code {{
          background: var(--chronotome-surface-soft) !important;
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
        }}
        [data-testid="stFileUploaderDropzone"] {{
          background: var(--chronotome-surface-soft) !important;
          border-color: rgba(198, 160, 74, 0.45) !important;
          color: var(--chronotome-text) !important;
        }}
        [data-testid="stFileUploaderDropzone"] * {{
          color: var(--chronotome-text) !important;
        }}
        [data-baseweb="tab-list"] {{
          background: transparent !important;
        }}
        [data-baseweb="tab"] {{
          color: var(--chronotome-muted) !important;
        }}
        [data-baseweb="tab"][aria-selected="true"] {{
          color: var(--chronotome-text) !important;
          border-bottom-color: var(--chronotome-accent) !important;
        }}
        [data-testid="stCheckbox"] label,
        [data-testid="stRadio"] label,
        [data-testid="stToggle"] label {{
          color: var(--chronotome-text) !important;
        }}
        [data-testid="stCheckbox"] label *,
        [data-testid="stRadio"] label *,
        [data-testid="stToggle"] label * {{
          color: var(--chronotome-text) !important;
          -webkit-text-fill-color: var(--chronotome-text) !important;
          opacity: 1 !important;
        }}

        /* Streamlit renders menus and tooltips in a portal. These explicit
           light-mode rules prevent dark-theme component defaults from leaking
           into the light interface. */
        [data-theme="light"] [data-testid="stSidebar"],
        [data-theme="light"] [data-testid="stSidebarContent"] {{
          background: {LIGHT["sidebar"]} !important;
        }}
        [data-theme="light"] div[data-baseweb="popover"],
        [data-theme="light"] div[data-baseweb="popover"] ul,
        [data-theme="light"] div[data-baseweb="menu"],
        [data-theme="light"] ul[role="listbox"],
        [data-theme="light"] div[role="listbox"] {{
          background: {LIGHT["surface"]} !important;
          border-color: {LIGHT["border"]} !important;
        }}
        [data-theme="light"] div[data-baseweb="popover"] *,
        [data-theme="light"] div[data-baseweb="menu"] *,
        [data-theme="light"] ul[role="listbox"] *,
        [data-theme="light"] div[role="listbox"] *,
        [data-theme="light"] div[role="option"],
        [data-theme="light"] div[role="option"] * {{
          color: {LIGHT["text"]} !important;
          -webkit-text-fill-color: {LIGHT["text"]} !important;
          opacity: 1 !important;
        }}
        [data-theme="light"] div[role="option"]:hover,
        [data-theme="light"] div[role="option"][aria-selected="true"] {{
          background: {LIGHT["surface_soft"]} !important;
        }}
        [data-theme="light"] [data-testid="stDataFrame"],
        [data-theme="light"] [data-testid="stTable"] {{
          background: {LIGHT["surface"]} !important;
          color: {LIGHT["text"]} !important;
        }}
        [data-theme="light"] [data-testid="stAlert"] {{
          background: {LIGHT["surface"]} !important;
          color: {LIGHT["text"]} !important;
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
                color:{BRAND["paper"]};margin-bottom:0.1rem;">
                Chronotome
            </div>
            <div style="color:{BRAND["gold"]};font-size:0.85rem;margin-bottom:0.65rem;">
                bibliometric time maps
            </div>
            """,
            unsafe_allow_html=True,
        )
