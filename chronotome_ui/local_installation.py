"""Installation and command reference for the published Chronotome package."""

from __future__ import annotations

import streamlit as st


def render_local_installation() -> None:
    """Display installation, update, launch, and removal commands."""
    st.title("Install Chronotome locally")
    st.markdown(
        "Chronotome is available from the Python Package Index (PyPI). "
        "The application runs at `http://127.0.0.1:8501` on your computer."
    )
    st.link_button(
        "View Chronotome on PyPI",
        "https://pypi.org/project/chronotome/",
    )

    st.markdown("## 1. Check Python 3.11")
    st.markdown("### macOS or Linux")
    st.code("python3.11 --version", language="bash")
    st.markdown("### Windows")
    st.code("py -3.11 --version", language="powershell")
    st.write(
        "The command should print a version beginning with `Python 3.11`. "
        "If it is not available, install Python 3.11 from "
        "[python.org](https://www.python.org/downloads/) and reopen the terminal."
    )

    st.markdown("## 2. Create a virtual environment")
    st.markdown("A virtual environment keeps Chronotome and its dependencies separate from other Python projects.")
    macos, windows = st.columns(2)
    with macos:
        st.markdown("### macOS or Linux")
        st.code(
            "python3.11 -m venv .venv\n"
            "source .venv/bin/activate\n"
            "python --version",
            language="bash",
        )
    with windows:
        st.markdown("### Windows PowerShell")
        st.code(
            "py -3.11 -m venv .venv\n"
            ".venv\\Scripts\\Activate.ps1\n"
            "python --version",
            language="powershell",
        )
    st.caption("After activation, `python --version` should report Python 3.11.x.")

    st.markdown("## 3. Update pip")
    st.code(
        "python -m pip --version\n"
        "python -m pip install --upgrade pip",
        language="bash",
    )

    st.markdown("## 4. Install Chronotome")
    st.code(
        "python -m pip install chronotome\n"
        "python -m pip show chronotome",
        language="bash",
    )
    st.write("`pip show` prints the installed version and installation location.")

    st.markdown("## 5. Start Chronotome")
    st.code("chronotome", language="bash")
    st.write(
        "Open `http://127.0.0.1:8501` if the browser does not open automatically. "
        "Keep the terminal open while using the application and press `Ctrl+C` to stop it."
    )
    with st.expander("Alternative launch commands"):
        st.code(
            "python -m chronotome\n"
            "chronotome --port 8502\n"
            "chronotome --no-browser",
            language="bash",
        )

    st.markdown("## Update Chronotome")
    st.code("python -m pip install --upgrade chronotome", language="bash")

    st.markdown("## Uninstall Chronotome")
    st.code("python -m pip uninstall chronotome", language="bash")

    st.markdown("## Open Chronotome again later")
    macos, windows = st.columns(2)
    with macos:
        st.markdown("### macOS or Linux")
        st.code("source .venv/bin/activate\nchronotome", language="bash")
    with windows:
        st.markdown("### Windows PowerShell")
        st.code(".venv\\Scripts\\Activate.ps1\nchronotome", language="powershell")

    st.markdown("## Troubleshooting")
    st.markdown(
        "- **`python3.11` is not found on macOS or Linux:** install Python 3.11, then reopen the terminal.\n"
        "- **`py -3.11` is not found on Windows:** install Python 3.11 and enable the Python launcher during setup.\n"
        "- **PowerShell blocks activation:** run `Set-ExecutionPolicy -Scope Process RemoteSigned`, then activate the environment again.\n"
        "- **Port 8501 is already in use:** run `chronotome --port 8502`.\n"
        "- **The `chronotome` command is not found:** reactivate the virtual environment and run `python -m pip show chronotome`."
    )
