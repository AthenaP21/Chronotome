"""Allow ``python -m chronotome`` to launch the local app."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
