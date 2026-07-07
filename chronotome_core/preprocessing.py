"""Schema harmonization, deduplication, and entity extraction for Chronotome."""

from __future__ import annotations

import re
from datetime import datetime

import numpy as np
import pandas as pd

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
    "Affiliations": "Affiliations", "Cited Reference Count": "Cited Reference Count",
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
    "Addresses": "Affiliations", "Cited Reference Count": "Cited Reference Count", "CR": "References_Raw_WoS",
    # Two-character fields emitted by the notebook's tagged WoS plaintext parser.
    "AU": "Authors", "AF": "Author Full Names", "TI": "Title", "SO": "Source Title",
    "PY": "Publication Year", "TC": "Cited by", "DI": "DOI", "AB": "Abstract",
    "DE": "Author Keywords", "ID": "Keywords Plus", "LA": "Language", "DT": "Document Type",
    "C1": "Affiliations", "PU": "Publisher", "SN": "ISSN",
}

FINAL_COLUMNS = [
    "Authors", "Author Full Names", "Title", "Source Title", "Publication Year", "Volume", "Issue",
    "Article Number", "Start Page", "End Page", "Number of Pages", "Cited by", "DOI", "Abstract",
    "Author Keywords", "Keywords Plus", "Language", "Document Type", "Conference Title", "Conference Date",
    "Conference Location", "Funding Orgs", "Funding Text", "Publisher", "ISSN", "ISBN",
    "Journal Abbreviation", "WoS Categories", "Web of Science Index", "Research Areas", "Affiliations",
    "Cited Reference Count", "Database",
]

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
    if pd.isna(ref_str):
        return 0
    return len([reference for reference in str(ref_str).split(";") if reference.strip()])


def wos_cited_reference_count(ref_str) -> int:
    """Count semicolon-delimited references in a WoS CR field."""
    if pd.isna(ref_str):
        return 0
    return len([reference for reference in str(ref_str).split(";") if reference.strip()])


def harmonize(sources: dict[str, pd.DataFrame], include_audit=False):
    """Map raw Scopus/WoS frames to the notebook's common schema."""
    frames, warnings = [], []
    source_audit_rows: list[dict] = []
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
        reference_rows = 0
        total_references = 0
        if source == "Scopus":
            if "References" in raw:
                raw["Cited Reference Count"] = raw["References"].apply(scopus_cited_reference_count)
                reference_rows = int(raw["References"].notna().sum())
                total_references = int(raw["Cited Reference Count"].sum())
            else:
                raw["Cited Reference Count"] = np.nan
        else:
            if "Author Full Names" not in raw and "AF" not in raw:
                raw["Author Full Names"] = np.nan
            if "CR" in raw:
                raw["Cited Reference Count"] = raw["CR"].apply(wos_cited_reference_count)
                reference_rows = int(raw["CR"].notna().sum())
                total_references = int(raw["Cited Reference Count"].sum())
            else:
                raw["Cited Reference Count"] = np.nan
            if "Times Cited, WoS Core" not in raw and "Times Cited, All Databases" in raw:
                mapping = dict(mapping)
                mapping["Times Cited, All Databases"] = "Cited by"
        existing = [column for column in mapping if column in raw]
        frame = raw[existing].rename(columns=mapping)
        frame["Database"] = source
        frames.append(frame)
        for original, unified in mapping.items():
            mapping_audit_rows.append({
                "Database": source, "Source field": original, "Unified field": unified,
                "Present in upload": "Yes" if original in raw_columns else "No",
                "Non-null values": int(raw[original].notna().sum()) if original in raw_columns else 0,
                "Retained in final schema": "Yes" if unified in FINAL_COLUMNS else "No",
            })
        source_audit_rows.append({
            "Database": source, "Input records": len(raw), "Input columns": len(raw_columns),
            "Fields mapped": len(existing), "Fields not selected": len(raw_columns - set(mapping)),
            "Author rows processed": author_rows, "Author strings changed": author_rows_changed,
            "Scopus author IDs removed": author_ids_removed, "Rows with references parsed": reference_rows,
            "Total cited references counted": total_references,
        })
    if not frames:
        raise ValueError("No Scopus or Web of Science records were loaded.")
    merged = pd.concat(frames, ignore_index=True, sort=False).reindex(columns=FINAL_COLUMNS)
    merged["Cited by"] = pd.to_numeric(merged["Cited by"], errors="coerce").fillna(0).astype(int)
    merged["Publication Year"] = pd.to_numeric(merged["Publication Year"], errors="coerce")
    prisma["merged_total"] = len(merged)
    for column in ("Publication Year", "Affiliations", "Abstract", "Document Type"):
        if merged[column].isna().all():
            warnings.append(f"'{column}' is unavailable; analyses that depend on it will be skipped.")
    if include_audit:
        audit = {
            "source_summary": pd.DataFrame(source_audit_rows),
            "schema_mapping": pd.DataFrame(mapping_audit_rows),
            "final_schema": pd.DataFrame({"Order": range(1, len(FINAL_COLUMNS) + 1), "Unified field": FINAL_COLUMNS}),
        }
        return merged, prisma, warnings, audit
    return merged, prisma, warnings


def deduplicate(merged: pd.DataFrame, prisma: dict, include_audit=False):
    """Fuse DOI duplicates and remove title/year duplicates exactly as in the notebook."""
    work = merged.copy()
    doi_text = work["DOI"].astype("string").str.lower().str.strip()
    work["DOI_norm"] = doi_text.mask(doi_text.isin(["", "nan", "none"]))
    work["Title_norm"] = work["Title"].fillna("").astype(str).str.lower().str.strip().str.replace(r"[^a-z0-9]", "", regex=True)
    work = work.sort_values("Cited by", ascending=False)
    with_doi, no_doi = work[work["DOI_norm"].notna()], work[work["DOI_norm"].isna()]
    duplicates = with_doi[with_doi.duplicated("DOI_norm", keep=False)].copy()
    with_doi = with_doi.sort_values(["DOI_norm", "Cited by"], ascending=[True, False])
    before_fusion = with_doi.groupby("DOI_norm").nth(0)
    fused = with_doi.groupby("DOI_norm", as_index=False, dropna=False).first()
    after_fusion = fused.set_index("DOI_norm")
    duplicate_dois = duplicates["DOI_norm"].dropna().unique()
    enrichment_by_column = pd.DataFrame(columns=["Field", "Missing values filled"])
    if len(duplicate_dois):
        before = before_fusion.loc[before_fusion.index.intersection(duplicate_dois)]
        after = after_fusion.loc[after_fusion.index.intersection(duplicate_dois)]
        filled = before.isna() & after.notna()
        counts = filled.sum()
        counts = counts[counts > 0].sort_values(ascending=False)
        enrichment_by_column = counts.rename("Missing values filled").rename_axis("Field").reset_index()
    prisma["records_with_doi"] = len(fused)
    prisma["removed_by_doi"] = len(with_doi) - len(fused)
    prisma["records_for_title_check"] = len(no_doi)
    no_doi = no_doi.sort_values("Cited by", ascending=False).drop_duplicates(["Title_norm", "Publication Year"], keep="first")
    prisma["removed_by_title_year"] = prisma["records_for_title_check"] - len(no_doi)
    final = pd.concat([fused, no_doi], ignore_index=True).drop(columns=["DOI_norm", "Title_norm"], errors="ignore")
    prisma["final_total"] = len(final)
    if include_audit:
        audit = {
            "summary": pd.DataFrame([
                ("Records before deduplication", len(merged)),
                ("Records containing a DOI after fusion", len(fused)),
                ("Duplicate DOI groups", len(duplicate_dois)),
                ("Rows removed by DOI", prisma["removed_by_doi"]),
                ("Records without DOI checked by title/year", prisma["records_for_title_check"]),
                ("Rows removed by title/year", prisma["removed_by_title_year"]),
                ("Missing metadata cells filled by DOI fusion", int(enrichment_by_column["Missing values filled"].sum()) if not enrichment_by_column.empty else 0),
                ("Unique records after deduplication", len(final)),
            ], columns=["Deduplication measure", "Records / cells"]),
            "enrichment_by_column": enrichment_by_column,
            "rules": pd.DataFrame([
                ("DOI", "lowercase + strip whitespace", "Highest-precision match; first non-null field after citation sorting"),
                ("Title", "lowercase + strip + remove non-alphanumeric characters", "Used only when DOI is missing"),
                ("Priority", "Cited by descending", "Most-cited record becomes the primary fusion record"),
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


def enrich_affiliations(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Compatibility wrapper around the full notebook entity-resolution stage."""
    if "Affiliations" not in data or data["Affiliations"].isna().all():
        result = data.copy()
        result["Countries_Extracted"] = [[] for _ in range(len(result))]
        result["Institutions_Extracted"] = [[] for _ in range(len(result))]
        result["Country_Count"] = 0
        result["Collaboration_Type"] = "Undefined"
        result["Country_Classification"] = "Unknown"
        return result, pd.DataFrame(), ["No affiliations were available; country and institution analyses were skipped."]
    from .entity_resolution import resolve_entities
    resolved = resolve_entities(data)
    return resolved["article_summary"], resolved["affiliations"], resolved["warnings"]
