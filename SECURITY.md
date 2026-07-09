# Security policy

## Local-first design

Chronotome is designed to run locally. The installed `chronotome` launcher binds
Streamlit to `127.0.0.1` and disables Streamlit usage-statistics collection. The
application does not require API keys or call external bibliographic services.

Uploaded bibliographic files are processed in the local Python process. Treat
untrusted data as data: do not install packages, run scripts, or open macros
that arrive alongside an export.

## Safe installation

- Obtain source code only from the official repository or a reviewed release.
- Use Python 3.11 or 3.12 inside a dedicated virtual environment.
- Install with `python -m pip install --only-binary=:all: .` where wheels are
  available. This avoids executing third-party dependency build scripts.
- Do not install from an unreviewed fork, arbitrary `git+https` URL, or a
  copied shell command.
- The package uses static `pyproject.toml` metadata; it intentionally has no
  `setup.py`, install hook, or custom build command.

## Maintainer safeguards

Code alone cannot prevent a compromised account from publishing a malicious
release. Repository maintainers should enable GitHub branch protection on the
default branch, require pull-request review and passing CI, restrict who can
create releases, protect tags, and enable Dependabot/security alerts.

Before publishing, review the exact diff, verify that package dependencies have
not gained direct URLs or VCS requirements, run the test suite, and build the
wheel from a clean checkout.

## Reporting a vulnerability

Do not publish a suspected vulnerability in a public issue first. Contact the
maintainers privately through the repository owner's verified contact channel,
including a concise reproduction and the affected Chronotome version. They can
coordinate a fix and disclosure.
