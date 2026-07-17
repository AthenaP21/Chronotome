"""Schema harmonization, deduplication, and entity extraction for Chronotome."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .io import INTERNAL_SOURCE_FILE_COLUMN, normalize_doi


DATABASE_DISPLAY_NAMES = {
    "Scopus": "Scopus",
    "WoS": "Web of Science",
}
DATABASE_ORDER = tuple(DATABASE_DISPLAY_NAMES.values())
_MISSING_TEXT_TOKENS = {"", "na", "n/a", "nan", "none", "null", "<na>"}

SCOPUS_MAP = {
    "Authors": "Authors", "Author full names": "Author Full Names", "Title": "Title",
    "Source title": "Source Title", "Year": "Publication Year", "Volume": "Volume",
    "Issue": "Issue", "Art. No.": "Article Number", "Page start": "Start Page",
    "Page end": "End Page", "Page count": "Number of Pages", "Cited by": "Cited by",
    "DOI": "DOI", "Abstract": "Abstract", "Author Keywords": "Author Keywords",
    "Index Keywords": "Keywords Plus", "Language of Original Document": "Language",
    "Document Type": "Document Type", "Conference name": "Conference Title",
    "Conference date": "Conference Date", "Conference location": "Conference Location",
    "Funding Details": "Funding Orgs", "Funding Texts": "Funding Text", "Publisher": "Publisher",
    "ISSN": "ISSN", "ISBN": "ISBN", "Abbreviated Source Title": "Journal Abbreviation",
    "Affiliations": "Affiliations", "References": "Cited References Raw",
    "Cited Reference Count": "Cited Reference Count",
    "Reference Count": "Cited Reference Count", "References Count": "Cited Reference Count",
}

WOS_MAP = {
    "Authors": "Authors", "Author Full Names": "Author Full Names", "Article Title": "Title",
    "Source Title": "Source Title", "Publication Year": "Publication Year", "Volume": "Volume",
    "Issue": "Issue", "Article Number": "Article Number", "Start Page": "Start Page",
    "End Page": "End Page", "Number of Pages": "Number of Pages",
    "Times Cited, WoS Core": "Cited by", "Times Cited, All Databases": "Cited by_All",
    "DOI": "DOI", "Abstract": "Abstract", "Author Keywords": "Author Keywords",
    "Keywords Plus": "Keywords Plus", "Language": "Language", "Document Type": "Document Type",
    "Conference Title": "Conference Title", "Conference Date": "Conference Date",
    "Conference Location": "Conference Location", "Funding Orgs": "Funding Orgs",
    "Funding Text": "Funding Text", "Publisher": "Publisher", "ISSN": "ISSN", "ISBN": "ISBN",
    "Journal Abbreviation": "Journal Abbreviation", "WoS Categories": "WoS Categories",
    "Web of Science Index": "Web of Science Index", "Research Areas": "Research Areas",
    "Addresses": "Affiliations", "Cited Reference Count": "Cited Reference Count",
    "Cited References Count": "Cited Reference Count",
    "CR": "Cited References Raw", "Cited References": "Cited References Raw",
    "Cited References Raw": "Cited References Raw",
    # Two-character fields emitted by the notebook's tagged WoS plaintext parser.
    "AU": "Authors", "AF": "Author Full Names", "TI": "Title", "SO": "Source Title",
    "PY": "Publication Year", "TC": "Cited by", "DI": "DOI", "AB": "Abstract",
    "DE": "Author Keywords", "ID": "Keywords Plus", "LA": "Language", "DT": "Document Type",
    "C1": "Affiliations", "PU": "Publisher", "SN": "ISSN", "NR": "Cited Reference Count",
}

FINAL_COLUMNS = [
    "Authors", "Author Full Names", "Title", "Source Title", "Publication Year", "Volume", "Issue",
    "Article Number", "Start Page", "End Page", "Number of Pages", "Cited by", "DOI", "Abstract",
    "Author Keywords", "Keywords Plus", "Language", "Document Type", "Conference Title", "Conference Date",
    "Conference Location", "Funding Orgs", "Funding Text", "Publisher", "ISSN", "ISBN",
    "Journal Abbreviation", "WoS Categories", "Web of Science Index", "Research Areas", "Affiliations",
    "Cited References Raw", "Cited Reference Count", "Primary Database", "Databases", "Source Files",
]


def _is_missing_scalar(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in _MISSING_TEXT_TOKENS
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, (bool, np.bool_)) else False


def normalize_title_key(value: object) -> str | pd.NA:
    """Normalize a usable title for conservative no-DOI duplicate matching."""
    if _is_missing_scalar(value):
        return pd.NA
    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    normalized = re.sub(r"[^a-z0-9]+", "", text)
    return normalized if normalized else pd.NA


def count_cited_references(raw: object) -> int | pd.NA:
    """Count semicolon-delimited references while distinguishing empty from missing."""
    if raw is None:
        return pd.NA
    try:
        missing = pd.isna(raw)
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, (bool, np.bool_)) and missing:
        return pd.NA
    text = str(raw).strip()
    if not text:
        return 0
    if text.casefold() in (_MISSING_TEXT_TOKENS - {""}):
        return pd.NA
    return sum(1 for reference in text.split(";") if reference.strip())


def _iter_provenance_values(value: object):
    if isinstance(value, (set, frozenset)):
        for item in sorted(value, key=lambda item: (str(item).casefold(), str(item))):
            yield from _iter_provenance_values(item)
    elif isinstance(value, (Sequence, np.ndarray, pd.Series)) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for item in value:
            yield from _iter_provenance_values(item)
    elif not _is_missing_scalar(value):
        text = str(value).strip()
        if text:
            yield text


def aggregate_provenance(values: Iterable[object], *, database=False) -> list[str]:
    """Deduplicate provenance safely and deterministically."""
    seen: dict[str, str] = {}
    for value in values:
        for text in _iter_provenance_values(value):
            canonical = DATABASE_DISPLAY_NAMES.get(text, text)
            if text == "Web of Science" or text.casefold() in {"wos", "web of science"}:
                canonical = "Web of Science"
            elif text.casefold() == "scopus":
                canonical = "Scopus"
            seen.setdefault(canonical.casefold(), canonical)
    if database:
        order = {name.casefold(): index for index, name in enumerate(DATABASE_ORDER)}
        return sorted(seen.values(), key=lambda item: (order.get(item.casefold(), len(order)), item.casefold()))
    return list(seen.values())


def select_author_text(frame: pd.DataFrame) -> pd.Series:
    """Select full author names per row, falling back to abbreviated names."""
    full_names = frame.get(
        "Author Full Names", pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    abbreviated = frame.get(
        "Authors", pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    full_text = full_names.astype("string")
    usable = full_names.notna() & full_text.str.strip().str.casefold().fillna("").ne("")
    usable &= ~full_text.str.strip().str.casefold().fillna("").isin(_MISSING_TEXT_TOKENS)
    return full_names.where(usable, abbreviated)


def author_source_counts(frame: pd.DataFrame) -> dict[str, int]:
    """Audit row-level author-name source selection."""
    full_names = frame.get(
        "Author Full Names", pd.Series(pd.NA, index=frame.index, dtype="object")
    ).astype("string")
    abbreviated = frame.get(
        "Authors", pd.Series(pd.NA, index=frame.index, dtype="object")
    ).astype("string")
    full_usable = full_names.notna() & full_names.str.strip().str.casefold().fillna("").ne("")
    full_usable &= ~full_names.str.strip().str.casefold().fillna("").isin(_MISSING_TEXT_TOKENS)
    abbreviated_usable = abbreviated.notna() & abbreviated.str.strip().str.casefold().fillna("").ne("")
    abbreviated_usable &= ~abbreviated.str.strip().str.casefold().fillna("").isin(_MISSING_TEXT_TOKENS)
    return {
        "usable_full_names": int(full_usable.sum()),
        "used_abbreviated_names": int((~full_usable & abbreviated_usable).sum()),
        "unusable_rows": int((~full_usable & ~abbreviated_usable).sum()),
    }

def clean_scopus_authors(authors_str) -> str:
    """Normalize Scopus authors to a consistent ``; `` delimiter."""
    if pd.isna(authors_str):
        return ""
    return "; ".join(author.strip() for author in str(authors_str).split(";") if author.strip())


def clean_wos_authors(authors_str) -> str:
    """Normalize WoS semicolon- or comma-delimited author strings."""
    if pd.isna(authors_str):
        return ""
    text = re.sub(r"\s+", " ", str(authors_str))
    if ";" in text:
        delimiter = ";"
    elif "," in text:
        delimiter = ","
    else:
        return text.strip()
    return "; ".join(author.strip() for author in text.split(delimiter) if author.strip())


def remove_id_codes_from_full_names(full_names_str) -> str:
    """Remove Scopus numeric author IDs such as ``(57211158827)``."""
    if pd.isna(full_names_str):
        return ""
    cleaned = re.sub(r"\(\d+\)", "", str(full_names_str))
    return re.sub(r"\s+", " ", cleaned).strip()


def scopus_cited_reference_count(ref_str) -> int:
    """Count semicolon-delimited references in a Scopus bibliography."""
    return count_cited_references(ref_str)


def wos_cited_reference_count(ref_str) -> int:
    """Count semicolon-delimited references in a WoS CR field."""
    return count_cited_references(ref_str)


def _coalesce_mapped_columns(raw: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Map source fields while coalescing established alternatives deterministically."""
    frame = pd.DataFrame(index=raw.index)
    for original, unified in mapping.items():
        if original not in raw.columns:
            continue
        if unified not in frame.columns:
            frame[unified] = raw[original]
        else:
            frame[unified] = frame[unified].where(frame[unified].notna(), raw[original])
    return frame


def _valid_reference_counts(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    valid = numeric.notna() & numeric.ge(0) & np.isclose(numeric, np.floor(numeric))
    return numeric.where(valid).astype("Int64")


def harmonize(sources: dict[str, pd.DataFrame], include_audit=False):
    """Map raw Scopus/WoS frames to the notebook's common schema."""
    frames, warnings = [], []
    source_audit_rows: list[dict] = []
    source_file_rows: list[dict] = []
    mapping_audit_rows: list[dict] = []
    prisma = {"scopus_initial": 0, "wos_initial": 0, "merged_total": 0, "removed_by_doi": 0,
              "records_with_doi": 0, "records_for_title_check": 0, "removed_by_title_year": 0,
              "excluded_by_time_filter": 0, "final_total": 0}
    for source, mapping in (("Scopus", SCOPUS_MAP), ("WoS", WOS_MAP)):
        if source not in sources:
            continue
        raw = sources[source].copy()
        raw_columns = set(raw.columns)
        prisma[f"{source.lower()}_initial"] = len(raw)
        title_options = ("Title",) if source == "Scopus" else ("Article Title", "TI")
        if not any(column in raw for column in title_options):
            raise ValueError(f"{source} export is missing required title column '{title_options[0]}'.")
        raw_author_column = "Authors" if "Authors" in raw else ("AU" if source == "WoS" and "AU" in raw else None)
        author_rows = 0
        author_rows_changed = 0
        if raw_author_column:
            before_authors = raw[raw_author_column].fillna("").astype(str)
            cleaner = clean_scopus_authors if source == "Scopus" else clean_wos_authors
            raw[raw_author_column] = raw[raw_author_column].apply(cleaner)
            author_rows = int(before_authors.str.strip().ne("").sum())
            author_rows_changed = int(before_authors.ne(raw[raw_author_column].fillna("").astype(str)).sum())
        author_ids_removed = 0
        if source == "Scopus" and "Author full names" in raw:
            author_ids_removed = int(raw["Author full names"].fillna("").astype(str).str.count(r"\(\d+\)").sum())
            raw["Author full names"] = raw["Author full names"].apply(remove_id_codes_from_full_names)
        if source == "WoS":
            if "Author Full Names" not in raw and "AF" not in raw:
                raw["Author Full Names"] = np.nan
            if "Times Cited, WoS Core" not in raw and "Times Cited, All Databases" in raw:
                mapping = dict(mapping)
                mapping["Times Cited, All Databases"] = "Cited by"
        existing = [column for column in mapping if column in raw]
        frame = _coalesce_mapped_columns(raw, mapping)

        raw_references = frame.get(
            "Cited References Raw", pd.Series(pd.NA, index=frame.index, dtype="object")
        )
        exported_counts = frame.get(
            "Cited Reference Count", pd.Series(pd.NA, index=frame.index, dtype="object")
        )
        numeric_counts = _valid_reference_counts(exported_counts)
        derived_counts = raw_references.map(count_cited_references).astype("Int64")
        frame["Cited References Raw"] = raw_references
        frame["Cited Reference Count"] = numeric_counts.where(numeric_counts.notna(), derived_counts)
        reference_rows = int(raw_references.notna().sum())
        total_references = int(frame["Cited Reference Count"].sum(skipna=True))

        database_name = DATABASE_DISPLAY_NAMES[source]
        frame["Primary Database"] = database_name
        frame["Databases"] = [[database_name] for _ in range(len(frame))]
        if INTERNAL_SOURCE_FILE_COLUMN in raw.columns:
            frame["Source Files"] = raw[INTERNAL_SOURCE_FILE_COLUMN].map(
                lambda value: aggregate_provenance([Path(str(value).replace("\\", "/")).name])
                if not _is_missing_scalar(value) else []
            )
            file_counts = raw[INTERNAL_SOURCE_FILE_COLUMN].map(
                lambda value: Path(str(value).replace("\\", "/")).name
                if not _is_missing_scalar(value) else pd.NA
            ).value_counts(dropna=True, sort=False)
            source_file_rows.extend({
                "Database": database_name, "Source File": filename, "Input records": int(count)
            } for filename, count in file_counts.items())
        else:
            frame["Source Files"] = [[] for _ in range(len(frame))]
        frames.append(frame)
        for original, unified in mapping.items():
            mapping_audit_rows.append({
                "Database": database_name, "Source field": original, "Unified field": unified,
                "Present in upload": "Yes" if original in raw_columns else "No",
                "Non-null values": int(raw[original].notna().sum()) if original in raw_columns else 0,
                "Retained in final schema": "Yes" if unified in FINAL_COLUMNS else "No",
            })
        source_audit_rows.append({
            "Database": database_name, "Input records": len(raw),
            "Input columns": len(raw_columns - {INTERNAL_SOURCE_FILE_COLUMN}),
            "Fields mapped": len(existing),
            "Fields not selected": len(raw_columns - set(mapping) - {INTERNAL_SOURCE_FILE_COLUMN}),
            "Author rows processed": author_rows, "Author strings changed": author_rows_changed,
            "Scopus author IDs removed": author_ids_removed, "Rows with references parsed": reference_rows,
            "Total cited references counted": total_references,
        })
    if not frames:
        raise ValueError("No Scopus or Web of Science records were loaded.")
    merged = pd.concat(frames, ignore_index=True, sort=False).reindex(columns=FINAL_COLUMNS)
    merged["Cited by"] = pd.to_numeric(merged["Cited by"], errors="coerce").astype("Float64")
    merged["Publication Year"] = pd.to_numeric(merged["Publication Year"], errors="coerce")
    prisma["merged_total"] = len(merged)
    for column in ("Publication Year", "Affiliations", "Abstract", "Document Type"):
        if merged[column].isna().all():
            warnings.append(f"'{column}' is unavailable; analyses that depend on it will be skipped.")
    if include_audit:
        audit = {
            "source_summary": pd.DataFrame(source_audit_rows),
            "source_files": pd.DataFrame(
                source_file_rows, columns=["Database", "Source File", "Input records"]
            ),
            "author_name_sources": pd.DataFrame([author_source_counts(merged)]),
            "schema_mapping": pd.DataFrame(mapping_audit_rows),
            "final_schema": pd.DataFrame({"Order": range(1, len(FINAL_COLUMNS) + 1), "Unified field": FINAL_COLUMNS}),
        }
        return merged, prisma, warnings, audit
    return merged, prisma, warnings


def _normalized_year_key(value: object) -> str | pd.NA:
    if _is_missing_scalar(value):
        return pd.NA
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric) or not np.isfinite(numeric) or float(numeric) != int(numeric):
        return pd.NA
    return str(int(numeric))


def _missing_for_fusion(value: object, column: str) -> bool:
    if column == "Cited References Raw":
        if value is None:
            return True
        try:
            missing = pd.isna(value)
        except (TypeError, ValueError):
            return False
        return bool(missing) if isinstance(missing, (bool, np.bool_)) else False
    if isinstance(value, (Sequence, set, frozenset, np.ndarray, pd.Series)) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return not any(True for _ in _iter_provenance_values(value))
    return _is_missing_scalar(value)


def _fuse_duplicate_group(group: pd.DataFrame, enrichment: Counter) -> pd.Series:
    """Keep the citation-prioritized primary row and fill only its missing cells."""
    primary = group.iloc[0].copy()
    original_order = group.sort_values("__chronotome_original_row__", kind="stable")
    primary["Databases"] = aggregate_provenance(original_order["Databases"], database=True)
    primary["Source Files"] = aggregate_provenance(original_order["Source Files"])
    for column in FINAL_COLUMNS:
        if column in {"Databases", "Source Files", "Primary Database"}:
            continue
        if not _missing_for_fusion(primary.get(column), column):
            continue
        for value in group[column].iloc[1:]:
            if not _missing_for_fusion(value, column):
                primary[column] = value
                enrichment[column] += 1
                break
    return primary


def deduplicate(merged: pd.DataFrame, prisma: dict, include_audit=False):
    """Fuse exact DOI or complete title-year matches with a stable primary row."""
    work = merged.copy().reset_index(drop=True)
    work["__chronotome_original_row__"] = np.arange(len(work), dtype=np.int64)
    raw_doi = work["DOI"].copy()
    work["DOI_norm"] = raw_doi.map(normalize_doi).astype("string")
    work["Title_norm"] = work["Title"].map(normalize_title_key).astype("string")
    work["Year_norm"] = work["Publication Year"].map(_normalized_year_key).astype("string")

    has_doi = work["DOI_norm"].notna()
    has_title_year = work["Title_norm"].notna() & work["Year_norm"].notna()
    work["Duplicate_Key"] = pd.Series(pd.NA, index=work.index, dtype="string")
    work.loc[has_doi, "Duplicate_Key"] = "doi:" + work.loc[has_doi, "DOI_norm"]
    title_year_rows = ~has_doi & has_title_year
    work.loc[title_year_rows, "Duplicate_Key"] = (
        "title-year:" + work.loc[title_year_rows, "Title_norm"] + "|" + work.loc[title_year_rows, "Year_norm"]
    )
    unmatched = ~has_doi & ~has_title_year
    work.loc[unmatched, "Duplicate_Key"] = (
        "unmatched-row:" + work.loc[unmatched, "__chronotome_original_row__"].astype(str)
    )
    # The public DOI field is canonical for every row.  This also converts
    # recognized missing tokens (for example ``NA`` or ``none``) to pd.NA
    # instead of leaking the raw placeholder into processed outputs.
    work["DOI"] = work["DOI_norm"]

    citation_priority = pd.to_numeric(work["Cited by"], errors="coerce").fillna(-np.inf)
    work["__chronotome_citation_priority__"] = citation_priority
    work = work.sort_values(
        ["__chronotome_citation_priority__", "__chronotome_original_row__"],
        ascending=[False, True], kind="stable",
    )

    group_sizes = work.groupby("Duplicate_Key", sort=False, dropna=False).size()
    duplicate_keys = set(group_sizes[group_sizes > 1].index)
    doi_duplicate_keys = {key for key in duplicate_keys if str(key).startswith("doi:")}
    title_duplicate_keys = {key for key in duplicate_keys if str(key).startswith("title-year:")}
    duplicates = work[work["Duplicate_Key"].isin(doi_duplicate_keys)].copy()

    enrichment: Counter = Counter()
    fused_rows = [
        _fuse_duplicate_group(group, enrichment)
        for _, group in work.groupby("Duplicate_Key", sort=False, dropna=False)
    ]
    final = pd.DataFrame(fused_rows).reset_index(drop=True)
    final = final.reindex(columns=FINAL_COLUMNS)
    final["Cited by"] = pd.to_numeric(final["Cited by"], errors="coerce").astype("Float64")
    final["Cited Reference Count"] = _valid_reference_counts(final["Cited Reference Count"])

    raw_comparable = raw_doi.map(
        lambda value: str(value) if not _is_missing_scalar(value) else pd.NA
    ).astype("string")
    normalized_original_order = (
        work.set_index("__chronotome_original_row__")["DOI_norm"]
        .sort_index().reset_index(drop=True)
    )
    raw_comparable = raw_comparable.reset_index(drop=True)
    doi_changed = int(
        (
            raw_comparable.notna()
            & (
                normalized_original_order.isna()
                | normalized_original_order.ne(raw_comparable).fillna(False)
            )
        ).sum()
    )

    no_doi = ~has_doi
    # Recompute masks in original row order so audit categories are unambiguous.
    original = work.sort_values("__chronotome_original_row__", kind="stable")
    original_no_doi = original["DOI_norm"].isna()
    original_title_missing = original["Title_norm"].isna()
    original_year_missing = original["Year_norm"].isna()
    missing_both = original_no_doi & original_title_missing & original_year_missing
    missing_title_only = original_no_doi & original_title_missing & ~original_year_missing
    missing_year_only = original_no_doi & ~original_title_missing & original_year_missing

    prisma.update({
        "records_with_doi": int(has_doi.sum()),
        "removed_by_doi": int(sum(group_sizes[key] - 1 for key in doi_duplicate_keys)),
        "records_for_title_check": int(no_doi.sum()),
        "removed_by_title_year": int(sum(group_sizes[key] - 1 for key in title_duplicate_keys)),
        "doi_based_fusion_groups": len(doi_duplicate_keys),
        "title_year_based_fusion_groups": len(title_duplicate_keys),
        "duplicate_groups_fused": len(duplicate_keys),
        "doi_values_changed_by_normalization": doi_changed,
        "no_doi_complete_title_year": int((original_no_doi & ~original_title_missing & ~original_year_missing).sum()),
        "retained_missing_title": int(missing_title_only.sum()),
        "retained_missing_year": int(missing_year_only.sum()),
        "retained_missing_title_and_year": int(missing_both.sum()),
        "final_total": len(final),
    })

    cross_database_groups = 0
    for key in duplicate_keys:
        group = work[work["Duplicate_Key"] == key]
        if len(aggregate_provenance(group["Databases"], database=True)) > 1:
            cross_database_groups += 1
    prisma["cross_database_duplicate_groups"] = cross_database_groups
    prisma["records_with_multiple_databases"] = int(final["Databases"].map(len).gt(1).sum())
    prisma["records_with_multiple_source_files"] = int(final["Source Files"].map(len).gt(1).sum())

    duplicate_cleanup = [
        "DOI_norm", "Title_norm", "Year_norm", "Duplicate_Key",
        "__chronotome_original_row__", "__chronotome_citation_priority__",
    ]
    duplicates = duplicates.drop(columns=duplicate_cleanup, errors="ignore").reindex(columns=FINAL_COLUMNS)
    enrichment_by_column = pd.DataFrame(
        sorted(enrichment.items(), key=lambda item: (-item[1], item[0])),
        columns=["Field", "Missing values filled"],
    )
    combinations = (
        final.assign(Provenance=final["Databases"].map(lambda values: "; ".join(values)))
        ["Provenance"].value_counts(sort=False).rename_axis("Databases").reset_index(name="Records")
        .sort_values(["Records", "Databases"], ascending=[False, True]).reset_index(drop=True)
    )
    if include_audit:
        audit = {
            "summary": pd.DataFrame([
                ("Records before deduplication", len(merged)),
                ("DOI-based fusion groups", len(doi_duplicate_keys)),
                ("Rows removed by DOI", prisma["removed_by_doi"]),
                ("Title-year-based fusion groups", len(title_duplicate_keys)),
                ("Rows removed by title/year", prisma["removed_by_title_year"]),
                ("Cross-database duplicate groups", cross_database_groups),
                ("DOI values changed by normalization", doi_changed),
                ("No-DOI records with complete title-year keys", prisma["no_doi_complete_title_year"]),
                ("No-DOI records retained: missing title", prisma["retained_missing_title"]),
                ("No-DOI records retained: missing year", prisma["retained_missing_year"]),
                ("No-DOI records retained: title and year missing", prisma["retained_missing_title_and_year"]),
                ("Records with multiple databases", prisma["records_with_multiple_databases"]),
                ("Records with multiple source files", prisma["records_with_multiple_source_files"]),
                ("Missing metadata cells filled during fusion", int(sum(enrichment.values()))),
                ("Unique records after deduplication", len(final)),
            ], columns=["Deduplication measure", "Records / cells"]),
            "enrichment_by_column": enrichment_by_column,
            "provenance_combinations": combinations,
            "author_name_sources": pd.DataFrame([author_source_counts(final)]),
            "rules": pd.DataFrame([
                ("DOI", "Unicode/case/prefix/whitespace/trailing-punctuation normalization", "Only equal usable DOI values are fused"),
                ("Title-year", "normalized non-empty title plus valid integer year", "Used only when DOI is missing and both fields are usable"),
                ("Unmatchable", "stable original row identifier", "Incomplete no-DOI records remain separate"),
                ("Priority", "Cited by descending; original row order tie-break", "Most-cited record remains the primary; missing metadata is filled"),
            ], columns=["Stage", "Normalization", "Rule"]),
        }
        return final, duplicates, audit
    return final, duplicates


def apply_time_filter(data: pd.DataFrame, enabled=True, collection_year=None, prisma=None) -> pd.DataFrame:
    """Exclude the collection year and later to correct indexing lag."""
    result = data.copy()
    removed = 0
    if enabled and result["Publication Year"].notna().any():
        cutoff = int(collection_year or datetime.now().year)
        before = len(result)
        result = result[result["Publication Year"] < cutoff].copy()
        removed = before - len(result)
    if prisma is not None:
        prisma["excluded_by_time_filter"] = removed
        prisma["final_total"] = len(result)
    return result
