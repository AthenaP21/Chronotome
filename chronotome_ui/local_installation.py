"""User-facing guidance for running Chronotome privately on a local computer."""

from __future__ import annotations

import streamlit as st


def render_local_installation() -> None:
    """Render practical, security-conscious local installation guidance."""
    st.title("Chronotome Local Studio")
    st.markdown(
        "Run Chronotome privately on your own computer. Your bibliographic files stay on "
        "your machine and the local launcher binds the app to **127.0.0.1** only."
    )

    st.info(
        "Recommended setup: Python 3.11, a virtual environment, and a copy of the official "
        "Chronotome repository or release."
    )

    st.markdown("## 1. Get a trusted copy")
    st.markdown(
        "Download a tagged release from the official Chronotome GitHub repository, or clone it "
        "over HTTPS. Avoid ZIP files, installers, or commands shared by unknown forks."
    )
    st.code(
        "git clone https://github.com/AthenaP21/Chronotome.git\n"
        "cd Chronotome",
        language="bash",
    )
    st.caption(
        "If a release includes a checksum or signed tag, verify it before installing. "
        "Only maintainers with reviewed repository access can publish official releases."
    )

    st.markdown("## 2. Install on macOS or Linux")
    st.code(
        "python3.11 -m venv .venv\n"
        "source .venv/bin/activate\n"
        "python -m pip install --upgrade pip\n"
        "python -m pip install --only-binary=:all: .",
        language="bash",
    )

    st.markdown("## 3. Install on Windows")
    st.code(
        "py -3.11 -m venv .venv\n"
        ".venv\\Scripts\\Activate.ps1\n"
        "python -m pip install --upgrade pip\n"
        "python -m pip install --only-binary=:all: .",
        language="powershell",
    )
    st.caption(
        "If PowerShell blocks activation, open PowerShell as your own user and run "
        "`Set-ExecutionPolicy -Scope Process RemoteSigned`, then activate the environment again."
    )

    st.markdown("## 4. Start Chronotome")
    st.code("chronotome", language="bash")
    st.write(
        "The launcher opens Chronotome at `http://127.0.0.1:8501`. Leave the terminal open while "
        "you work; use `Ctrl+C` there to stop the app."
    )
    with st.expander("Alternative: start the Streamlit file directly"):
        st.code(
            "streamlit run app.py --server.address 127.0.0.1 --server.port 8501",
            language="bash",
        )

    st.markdown("## Everyday use")
    first, second = st.columns(2)
    with first:
        st.markdown("### macOS / Linux")
        st.code("cd Chronotome\nsource .venv/bin/activate\nchronotome", language="bash")
    with second:
        st.markdown("### Windows")
        st.code("cd Chronotome\n.venv\\Scripts\\Activate.ps1\nchronotome", language="powershell")

    st.markdown("## Privacy and security")
    st.markdown(
        "- The local launcher accepts only `127.0.0.1`, so the app is not exposed to your local network.\n"
        "- Chronotome does not require API keys and does not upload your corpus to a remote service.\n"
        "- The package uses standard static Python packaging metadata—there is no custom install script or shell command execution.\n"
        "- Install into a dedicated virtual environment and keep your operating system, Python, and packages updated.\n"
        "- Do not install a modified copy of Chronotome unless you trust and review its source code."
    )

    st.markdown("## If something goes wrong")
    st.markdown(
        "- **`python3.11` or `py -3.11` is not found:** install Python 3.11 from python.org, then reopen the terminal.\n"
        "- **Port 8501 is busy:** start with `chronotome --port 8502`.\n"
        "- **A binary package is unavailable:** remove `--only-binary=:all:` only after confirming the package name and version from a trusted source.\n"
        "- **The app does not open:** visit `http://127.0.0.1:8501` manually while the terminal process is running."
    )
