"""Safe localhost-only launcher for the installed Chronotome application."""

from __future__ import annotations

import argparse
from importlib.resources import as_file, files
import subprocess
import sys


def _port(value: str) -> int:
    """Validate a user-selected localhost port."""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be a whole number.") from exc
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1024 and 65535.")
    return port


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chronotome",
        description="Start Chronotome locally at http://127.0.0.1:<port>.",
    )
    parser.add_argument(
        "--port", type=_port, default=8501,
        help="Local port to use (default: 8501).",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Keep the browser closed; open the local URL yourself.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Launch Streamlit without a shell and never expose it beyond localhost."""
    options = _parser().parse_args(argv)
    app_resource = files("chronotome").joinpath("app.py")
    with as_file(app_resource) as app_path:
        command = [
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.address=127.0.0.1",
            f"--server.port={options.port}",
            "--browser.gatherUsageStats=false",
            f"--server.headless={'true' if options.no_browser else 'false'}",
        ]
        return subprocess.call(command)
