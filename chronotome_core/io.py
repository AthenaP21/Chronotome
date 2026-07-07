"""Fault-tolerant readers and validation for Scopus and Web of Science exports."""

from __future__ import annotations

import io
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xls", ".xlsx"}


class InputError(ValueError):
    """Raised when an uploaded bibliometric export cannot be used."""


@dataclass
class LoadedFile:
    """A parsed upload together with its detected bibliographic source."""

    name: str
    source: str
    data: pd.DataFrame
    parse_strategy: str = ""
    extension: str = ""
    part_number: int | None = None
    series_name: str | None = None


SCHEMA_FIELDS = {
    "Scopus": {
        "required": {"Title"},
        "recommended": {
            "Authors", "Author full names", "Source title", "Year", "Cited by", "DOI",
            "Abstract", "Author Keywords", "Index Keywords", "Document Type",
            "Affiliations", "References",
        },
    },
    "WoS": {
        "required": {"Article Title"},
        "required_alternatives": ({"TI"},),
        "recommended": {
            "Authors", "Author Full Names", "Source Title", "Publication Year",
            "Times Cited, WoS Core", "Times Cited, All Databases", "DOI", "Abstract",
            "Author Keywords", "Keywords Plus", "Document Type", "Addresses", "CR",
        },
    },
}


def _bytes(uploaded_file) -> tuple[str, bytes]:
    name = getattr(uploaded_file, "name", "upload.csv")
    if isinstance(uploaded_file, (bytes, bytearray)):
        return name, bytes(uploaded_file)
    if hasattr(uploaded_file, "getvalue"):
        return name, uploaded_file.getvalue()
    if hasattr(uploaded_file, "read"):
        pos = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
        content = uploaded_file.read()
        if pos is not None and hasattr(uploaded_file, "seek"):
            uploaded_file.seek(pos)
        return name, content
    raise InputError("The uploaded object is not a readable file.")


def parse_wos_plaintext(content: bytes) -> pd.DataFrame:
    """Parse tagged WoS plain text (PT/AU/TI/.../ER) into records."""
    text = content.decode("utf-8", errors="replace")
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    current_tag: str | None = None
    for line in text.splitlines():
        if line.startswith("ER"):
            if current:
                records.append(current)
            current, current_tag = {}, None
        elif re.match(r"^[A-Z][A-Z0-9] ", line):
            current_tag = line[:2]
            current[current_tag] = line[3:]
        elif line.startswith("   ") and current_tag:
            current[current_tag] += " " + line.strip()
    if current:
        records.append(current)
    return pd.DataFrame(records)


def read_uploaded_file_detailed(uploaded_file) -> tuple[pd.DataFrame, str]:
    """Read an upload and report the parser strategy that succeeded."""
    name, content = _bytes(uploaded_file)
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise InputError(
            f"Unsupported file type '{suffix or 'unknown'}'. Upload CSV, TXT, XLS, or XLSX."
        )
    bio = io.BytesIO(content)
    errors: list[str] = []
    if suffix in {".xls", ".xlsx"}:
        try:
            return pd.read_excel(bio), "Excel workbook"
        except Exception as exc:
            errors.append(f"Excel reader: {exc}")
            bio.seek(0)
            try:
                return pd.read_csv(bio, sep="\t", on_bad_lines="skip", quoting=3), "Tab-delimited fallback"
            except Exception as exc2:
                errors.append(f"tab fallback: {exc2}")
    elif suffix == ".csv":
        for sep in (",", "\t"):
            bio.seek(0)
            try:
                frame = pd.read_csv(bio, sep=sep, on_bad_lines="skip", low_memory=False)
                if frame.shape[1] > 1:
                    strategy = "Comma-delimited CSV" if sep == "," else "Tab-delimited CSV fallback"
                    return frame, strategy
            except Exception as exc:
                errors.append(f"CSV separator {sep!r}: {exc}")
    else:
        try:
            frame = pd.read_csv(bio, sep="\t", on_bad_lines="skip", quoting=3, low_memory=False)
            if frame.shape[1] > 1:
                return frame, "Tab-delimited text"
        except Exception as exc:
            errors.append(f"tab reader: {exc}")
        frame = parse_wos_plaintext(content)
        if not frame.empty:
            return frame, "Tagged WoS plaintext"
    detail = "; ".join(errors[-2:])
    raise InputError(f"Could not read '{name}'. Confirm it is a valid bibliometric export. {detail}")


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Read CSV, tab text, XLS, or XLSX using the notebook's fallback order."""
    return read_uploaded_file_detailed(uploaded_file)[0]


def detect_source(columns: Iterable[str]) -> str:
    """Detect Scopus or WoS from the original export column names."""
    cols = {str(c).strip() for c in columns}
    scopus_signals = {"Title", "Author full names", "Source title", "Year", "Cited by", "Index Keywords", "Art. No.", "Affiliations", "References"}
    wos_signals = {"Article Title", "Source Title", "Publication Year", "Times Cited, WoS Core", "WoS Categories", "Addresses", "CR", "TI", "SO", "AU"}
    scopus_score = len(cols & scopus_signals)
    wos_score = len(cols & wos_signals)
    if scopus_score == wos_score == 0:
        raise InputError(
            "The columns do not look like a Scopus or Web of Science export. "
            "Export the full bibliographic record and cited references."
        )
    return "Scopus" if scopus_score > wos_score else "WoS"


def load_uploads(uploaded_files) -> list[LoadedFile]:
    """Read one or more uploads and concatenate split files within each source."""
    files = uploaded_files if isinstance(uploaded_files, (list, tuple)) else [uploaded_files]
    loaded: list[LoadedFile] = []
    for item in files:
        frame, strategy = read_uploaded_file_detailed(item)
        if frame.empty:
            raise InputError(f"'{getattr(item, 'name', 'upload')}' contains no records.")
        frame.columns = [str(c).strip() for c in frame.columns]
        name = getattr(item, "name", "upload")
        loaded.append(LoadedFile(name, detect_source(frame.columns), frame, strategy, Path(name).suffix.lower()))
    return loaded


def _has_required_fields(columns: set[str], source: str) -> bool:
    schema = SCHEMA_FIELDS[source]
    if schema["required"].issubset(columns):
        return True
    return any(option.issubset(columns) for option in schema.get("required_alternatives", ()))


def _schema_coverage(columns: set[str], source: str) -> tuple[int, int, float]:
    recommended = SCHEMA_FIELDS[source]["recommended"]
    present = len(columns & recommended)
    return present, len(recommended), present / len(recommended) * 100


def _appendage_identity(filename: str) -> tuple[str, int, str]:
    match = re.match(r"^(.*)_(\d+)\.(xls|xlsx|txt|csv)$", Path(filename).name, re.IGNORECASE)
    if not match:
        raise InputError(
            f"Appendage file '{filename}' must end in _NUMBER followed by .csv, .txt, .xls, or .xlsx."
        )
    return match.group(1), int(match.group(2)), "." + match.group(3).lower()


def inspect_source_uploads(uploaded_files, source: str, mode: str = "single") -> dict:
    """Validate source-specific uploads and return rich ingestion signals.

    In appendage mode, filenames must share one base and extension and end in a
    numeric part suffix. Parts are returned in numeric order.
    """
    if source not in SCHEMA_FIELDS:
        raise InputError(f"Unknown bibliographic source: {source}")
    files = list(uploaded_files or [])
    if not files:
        raise InputError(f"Upload at least one {source} file.")
    if mode == "single" and len(files) != 1:
        raise InputError(f"Single-file mode accepts exactly one {source} file. Choose Appendage for split exports.")
    if mode == "appendage" and len(files) < 2:
        raise InputError(f"Appendage mode requires at least two numbered {source} files.")

    identities = []
    if mode == "appendage":
        identities = [_appendage_identity(getattr(item, "name", "upload")) for item in files]
        bases = {base.lower() for base, _, _ in identities}
        extensions = {ext for _, _, ext in identities}
        parts = [part for _, part, _ in identities]
        if len(bases) != 1:
            raise InputError(f"{source} appendage files belong to different filename series: {sorted(bases)}")
        if len(extensions) != 1:
            raise InputError(f"{source} appendage files must use the same extension; found {sorted(extensions)}.")
        if len(parts) != len(set(parts)):
            raise InputError(f"{source} appendage contains duplicate part numbers.")
        ordered = sorted(zip(files, identities), key=lambda pair: pair[1][1])
    else:
        ordered = [(files[0], (Path(getattr(files[0], "name", "upload")).stem, 0,
                               Path(getattr(files[0], "name", "upload")).suffix.lower()))]

    loaded: list[LoadedFile] = []
    file_rows: list[dict] = []
    warnings: list[str] = []
    content_hashes: set[str] = set()
    first_columns: set[str] | None = None
    for item, (series, part, extension) in ordered:
        name, content = _bytes(item)
        digest = hashlib.sha256(content).hexdigest()
        if digest in content_hashes:
            warnings.append(f"'{name}' has identical content to another uploaded file.")
        content_hashes.add(digest)
        frame, strategy = read_uploaded_file_detailed(item)
        if frame.empty:
            raise InputError(f"'{name}' contains no records.")
        frame.columns = [str(column).strip() for column in frame.columns]
        columns = set(frame.columns)
        detected = detect_source(columns)
        required_ok = _has_required_fields(columns, source)
        if detected != source:
            raise InputError(
                f"'{name}' was uploaded as {source}, but its columns look like {detected}. Move it to the {detected} uploader."
            )
        if not required_ok:
            required = "Title" if source == "Scopus" else "Article Title (or TI in tagged text)"
            raise InputError(f"'{name}' is missing the required {source} title field: {required}.")
        present, expected, coverage = _schema_coverage(columns, source)
        columns_match = first_columns is None or columns == first_columns
        if first_columns is not None and not columns_match:
            missing = sorted(first_columns - columns)
            added = sorted(columns - first_columns)
            warnings.append(
                f"'{name}' has a different schema from the first {source} part "
                f"(missing: {missing or 'none'}; additional: {added or 'none'})."
            )
        first_columns = columns if first_columns is None else first_columns
        loaded.append(LoadedFile(name, source, frame, strategy, extension, part or None, series))
        file_rows.append({
            "File": name, "Part": part if mode == "appendage" else "—", "Extension": extension,
            "Parser": strategy, "Detected source": detected, "Rows": len(frame), "Columns": len(frame.columns),
            "Required title": "Present", "Recommended fields": f"{present}/{expected}",
            "Schema coverage": f"{coverage:.0f}%", "Matches first schema": "Yes" if columns_match else "No",
            "Status": "Ready" if columns_match else "Ready with warning",
        })

    if mode == "appendage":
        parts = [item.part_number for item in loaded]
        expected_parts = list(range(min(parts), max(parts) + 1))
        missing_parts = sorted(set(expected_parts) - set(parts))
        if missing_parts:
            warnings.append(f"{source} appendage part sequence has gaps: missing {missing_parts}.")
        if min(parts) != 1:
            warnings.append(f"{source} appendage starts at part {min(parts)}, not part 1.")

    combined = pd.concat([item.data for item in loaded], ignore_index=True, sort=False)
    year_column = "Year" if source == "Scopus" else ("Publication Year" if "Publication Year" in combined else "PY")
    years = pd.to_numeric(combined.get(year_column, pd.Series(dtype=float)), errors="coerce").dropna()
    doi_column = "DOI" if "DOI" in combined else ("DI" if "DI" in combined else None)
    dois = combined[doi_column].astype("string").str.strip() if doi_column else pd.Series(dtype="string")
    title_column = "Title" if source == "Scopus" else ("Article Title" if "Article Title" in combined else "TI")
    affiliation_column = "Affiliations" if source == "Scopus" else ("Addresses" if "Addresses" in combined else "C1")
    summary = {
        "Source": source, "Mode": "Appendage" if mode == "appendage" else "Single file",
        "Files": len(loaded), "Records": len(combined), "Columns (union)": len(combined.columns),
        "Year range": f"{int(years.min())}–{int(years.max())}" if not years.empty else "Not detected",
        "Titles present": int(combined[title_column].notna().sum()) if title_column in combined else 0,
        "DOI coverage": f"{dois.notna().mean() * 100:.1f}%" if doi_column else "Not available",
        "Raw duplicate DOI rows": int(dois[dois.notna() & dois.ne("")].duplicated(keep=False).sum()) if doi_column else 0,
        "Affiliation coverage": (
            f"{combined[affiliation_column].notna().mean() * 100:.1f}%" if affiliation_column in combined else "Not available"
        ),
    }
    return {"loaded": loaded, "combined": combined, "files": pd.DataFrame(file_rows),
            "summary": summary, "warnings": warnings}


def combine_by_source(loaded: list[LoadedFile]) -> dict[str, pd.DataFrame]:
    """Stack uploaded split exports by detected database, preserving file order."""
    result: dict[str, pd.DataFrame] = {}
    for source in ("Scopus", "WoS"):
        parts = [item.data for item in loaded if item.source == source]
        if parts:
            result[source] = pd.concat(parts, ignore_index=True, sort=False)
    return result


def inspect_uploads(uploaded_files) -> dict:
    """Return pre-analysis metadata for Streamlit without changing the data."""
    loaded = load_uploads(uploaded_files)
    sources = combine_by_source(loaded)
    records = sum(len(frame) for frame in sources.values())
    columns = sorted({col for frame in sources.values() for col in frame.columns})
    year_values = []
    for source, frame in sources.items():
        year_col = "Year" if source == "Scopus" else "Publication Year"
        if year_col in frame:
            year_values.extend(pd.to_numeric(frame[year_col], errors="coerce").dropna().tolist())
    return {
        "records": records,
        "columns": columns,
        "sources": {key: len(value) for key, value in sources.items()},
        "year_range": (int(min(year_values)), int(max(year_values))) if year_values else None,
        "files": [{"name": item.name, "source": item.source, "records": len(item.data)} for item in loaded],
    }
