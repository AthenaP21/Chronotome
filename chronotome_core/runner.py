"""Single high-level runner for the complete Chronotome workflow."""

from __future__ import annotations

import pandas as pd
import io
import zipfile
import networkx as nx
import gc
import os
import resource
import sys
from datetime import datetime

from .analysis import (
    add_mncs, annual_production, author_metrics, bradford_table, citation_dynamics,
    country_metrics, document_types, hot_papers, institution_networks, main_summary,
    ranked_articles, source_metrics, team_size_impact, thematic_analysis,
)
from .advanced_analyses import run_advanced_bibliometric_analysis
from .export import (
    create_exports, dataframe_csv, dataframe_excel, figure_pdf, figure_png,
    figure_svg, raster_export_policy, release_figures,
)
from .entity_resolution import resolve_entities
from .descriptive_bibliometrics import run_descriptive_bibliometrics
from .geographic_bibliometrics import (
    advanced_country_analysis, country_case_study_analysis,
    geographic_distribution_analysis,
)
from .io import combine_by_source, inspect_uploads, inspect_source_uploads, load_uploads
from .institutional_bibliometrics import (
    institutional_analysis, institutional_community_visualization,
    prepare_institutional_dataset,
)
from .preprocessing import apply_time_filter, deduplicate, enrich_affiliations, harmonize
from .thematic_bibliometrics import (
    DEFAULT_BLOCKLIST_PHRASES, DEFAULT_NOISE_LISTS,
    advanced_thematic_analysis, final_topic_models, prepare_thematic_dataset,
    thematic_preprocessing, topic_model_evaluation,
)
from .visualization import build_figures


def _attach_archive(files: dict[str, bytes], archive_name: str, enabled=True) -> None:
    """Attach a ZIP only for interactive single-stage downloads."""
    if not enabled:
        return
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    files[archive_name] = archive_buffer.getvalue()


def _rss_megabytes() -> float:
    """Return current RSS on Linux and a safe peak-RSS fallback elsewhere."""
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 ** 2)
    except (OSError, ValueError, IndexError):
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return rss / (1024 ** 2) if sys.platform == "darwin" else rss / 1024


def _release_result_figures(result: dict) -> None:
    figures = list(result.get("figures", {}).values())
    if result.get("figure") is not None:
        figures.append(result["figure"])
    release_figures(figures)


def prisma_table(report: dict) -> pd.DataFrame:
    total_loaded = report["scopus_initial"] + report["wos_initial"]
    total_removed = report["removed_by_doi"] + report["removed_by_title_year"] + report.get("excluded_by_time_filter", 0)
    rows = [
        ("Identification", "Records identified from Scopus", report["scopus_initial"]),
        ("Identification", "Records identified from WoS", report["wos_initial"]),
        ("Identification", "Total records loaded", total_loaded),
        ("Identification", "Records after merge", report["merged_total"]),
        ("Screening", "Records before deduplication", report["merged_total"]),
        ("Screening", "Duplicates removed by DOI", report["removed_by_doi"]),
        ("Screening", "Duplicates removed by title/year", report["removed_by_title_year"]),
        ("Screening", "Excluded by time filter", report["excluded_by_time_filter"]),
        ("Screening", "Total records removed", total_removed),
        ("Included", "Final records", report["final_total"]),
    ]
    return pd.DataFrame(rows, columns=["Stage", "Measure", "Records"])


def prisma_text_report(report: dict) -> str:
    """Format the notebook's textual PRISMA-style reporting block."""
    excluded = report.get("excluded_by_time_filter", 0)
    total_loaded = report["scopus_initial"] + report["wos_initial"]
    total_removed = report["removed_by_doi"] + report["removed_by_title_year"] + excluded
    expected = report["merged_total"] - total_removed
    sanity = "Passed." if expected == report["final_total"] else "FAILED — counts require review."
    return f"""================================================
     BIBLIOMETRIC REPORTING (PRISMA Style)
================================================
1. IDENTIFICATION
------------------------------------------------
Records identified from Scopus:     {report['scopus_initial']:,}
Records identified from WoS:        {report['wos_initial']:,}
Total records loaded:               {total_loaded:,}
Total records after merge:          {report['merged_total']:,}

2. SCREENING (DEDUPLICATION + TIME FILTER)
------------------------------------------------
Total records before deduplication: {report['merged_total']:,}
Duplicates removed by DOI:          {report['removed_by_doi']:,}
Duplicates removed by Title/Year:   {report['removed_by_title_year']:,}
Excluded by Time Filter:            {excluded:,}
------------------------------------------------
Total records removed:              {total_removed:,}

3. INCLUDED
------------------------------------------------
Final records in dataset:           {report['final_total']:,}
================================================
Sanity Check: {sanity}"""


def run_ingestion(scopus_files=None, wos_files=None, modes=None, config=None, include_archive=True):
    """Verify, append, harmonize, deduplicate, and export bibliographic files.

    This is the focused Phase 1 runner used by the ingestion page. It keeps
    Scopus and WoS upload streams separate, applies appendage rules within each
    stream, and stops after the PRISMA-ready merged dataset is produced.
    """
    modes = {"Scopus": "single", "WoS": "single", **(modes or {})}
    config = {"enable_time_filter": True, "collection_year": None, **(config or {})}
    verifications = {}
    sources = {}
    warnings = []
    if scopus_files:
        verification = inspect_source_uploads(scopus_files, "Scopus", modes["Scopus"])
        verifications["Scopus"] = verification
        sources["Scopus"] = verification["combined"]
        warnings.extend(verification["warnings"])
    if wos_files:
        verification = inspect_source_uploads(wos_files, "WoS", modes["WoS"])
        verifications["WoS"] = verification
        sources["WoS"] = verification["combined"]
        warnings.extend(verification["warnings"])
    if not sources:
        raise ValueError("Upload at least one Scopus or Web of Science export.")

    merged, report, harmonization_warnings, preprocessing_audit = harmonize(sources, include_audit=True)
    warnings.extend(harmonization_warnings)
    final, duplicate_doi_records, deduplication_audit = deduplicate(merged, report, include_audit=True)
    before_time_filter = final.copy()
    final = apply_time_filter(final, config["enable_time_filter"], config["collection_year"], report)
    if final.empty:
        raise ValueError("No records remain. Disable the collection-year filter or check publication years.")
    table = prisma_table(report)
    text_report = prisma_text_report(report)
    final_years = pd.to_numeric(final["Publication Year"], errors="coerce").dropna()
    cutoff = int(config["collection_year"] or datetime.now().year) if config["enable_time_filter"] else None
    temporal_audit = pd.DataFrame([
        ("Time filter", "Enabled" if config["enable_time_filter"] else "Disabled"),
        ("Cutoff source", "Manual input" if config["enable_time_filter"] and config["collection_year"] else
         ("Current system year" if config["enable_time_filter"] else "Not applicable")),
        ("Cutoff rule", f"Keep Publication Year < {cutoff}" if cutoff else "Keep all publication years"),
        ("Records before time filter", len(before_time_filter)),
        ("Records excluded", report["excluded_by_time_filter"]),
        ("Final year range", f"{int(final_years.min())}–{int(final_years.max())}" if not final_years.empty else "Not available"),
        ("Final records", len(final)),
    ], columns=["Temporal delimitation measure", "Value"])
    files = {
        "merged_bibliometric_dataset.csv": dataframe_csv(final),
        "merged_bibliometric_dataset.xlsx": dataframe_excel(final, "Merged deduplicated"),
        "prisma_reporting_counts.csv": dataframe_csv(table),
        "preprocessing_source_audit.csv": dataframe_csv(preprocessing_audit["source_summary"]),
        "schema_mapping_audit.csv": dataframe_csv(preprocessing_audit["schema_mapping"]),
        "deduplication_audit.csv": dataframe_csv(deduplication_audit["summary"]),
        "temporal_delimitation_audit.csv": dataframe_csv(temporal_audit),
        "prisma_text_report.txt": text_report.encode("utf-8"),
    }
    if not duplicate_doi_records.empty:
        files["duplicate_doi_records_review.csv"] = dataframe_csv(duplicate_doi_records)
    for source, verification in verifications.items():
        if modes[source] == "appendage":
            safe = source.lower().replace(" ", "_")
            files[f"stitched_{safe}_export.csv"] = dataframe_csv(verification["combined"])
            files[f"stitched_{safe}_export.xlsx"] = dataframe_excel(verification["combined"], f"Stitched {source}")
    _attach_archive(files, "chronotome_ingestion_outputs.zip", include_archive)
    return {
        "processed_data": final, "merged_before_deduplication": merged,
        "duplicate_doi_records": duplicate_doi_records, "prisma": report,
        "prisma_table": table, "prisma_text": text_report, "verifications": verifications,
        "preprocessing_audit": preprocessing_audit, "deduplication_audit": deduplication_audit,
        "temporal_audit": temporal_audit,
        "warnings": list(dict.fromkeys(warnings)), "exports": files, "config": config,
    }


def run_entity_resolution(data: pd.DataFrame, alias_json_file=None, include_archive=True):
    """Resolve institution and country entities and create portable exports."""
    resolved = resolve_entities(data, alias_json_file=alias_json_file)
    files = {
        "exploded_affiliations_list.csv": dataframe_csv(resolved["affiliations"]),
        "exploded_affiliations_list.xlsx": dataframe_excel(resolved["affiliations"], "Affiliations"),
        "final_article_summary_with_countries.csv": dataframe_csv(resolved["article_summary"]),
        "final_article_summary_with_countries.xlsx": dataframe_excel(resolved["article_summary"], "Article summary"),
        "entity_resolution_summary.csv": dataframe_csv(resolved["audit"]["summary"]),
        "institution_alias_map_summary.csv": dataframe_csv(pd.DataFrame(
            resolved["alias_info"]["summary"].items(), columns=["Alias-map measure", "Value"]
        )),
        "institution_alias_mappings.csv": dataframe_csv(resolved["audit"]["aliases"]),
        "abbreviation_expansions.csv": dataframe_csv(resolved["audit"]["abbreviations"]),
        "unresolved_country_fragments.csv": dataframe_csv(resolved["audit"]["unresolved_countries"]),
        "active_institutions.json": resolved["alias_info"]["content"],
    }
    for name, table in (
        ("institution_frequencies.csv", resolved["audit"]["institution_frequencies"]),
        ("country_frequencies.csv", resolved["audit"]["country_frequencies"]),
        ("alias_collisions.csv", resolved["alias_info"]["collisions"]),
        ("backup_canonicals_ignored.csv", resolved["alias_info"]["backup_ignored"]),
        ("complex_pattern_matches.csv", resolved["audit"]["complex_patterns"]),
    ):
        if not table.empty:
            files[name] = dataframe_csv(table)
    _attach_archive(files, "chronotome_entity_resolution_outputs.zip", include_archive)
    return {**resolved, "exports": files}


def run_corpus_bibliometrics(
    data: pd.DataFrame, cutoff_year=None, top_n=10, min_source_papers=5,
    max_source_title_length=30, include_archive=True,
):
    """Run notebook-faithful corpus, MNCS, typology, author, and trend analyses."""
    result = run_descriptive_bibliometrics(
        data, cutoff_year=cutoff_year, top_n=top_n,
        min_source_papers=min_source_papers,
        max_source_title_length=max_source_title_length,
    )
    files: dict[str, bytes] = {
        "Results/bibliometric_dataset_with_mncs.csv": dataframe_csv(result["data"]),
        "Results/bibliometric_dataset_with_mncs.xlsx": dataframe_excel(result["data"], "Dataset with MNCS"),
    }
    for name, table in result["tables"].items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            files[f"Results/{name}.csv"] = dataframe_csv(table)
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for name, table in result["tables"].items():
            if isinstance(table, pd.DataFrame) and not table.empty:
                table.to_excel(writer, index=False, sheet_name=name[:31])
    files["Results/descriptive_bibliometrics_tables.xlsx"] = workbook.getvalue()
    for name, figure in result["figures"].items():
        files[f"Plots/{name}.png"] = figure_png(figure, dpi=600)
        files[f"Plots/{name}.svg"] = figure_svg(figure)
        files[f"Plots/{name}.pdf"] = figure_pdf(figure)
    _attach_archive(files, "chronotome_corpus_bibliometrics_outputs.zip", include_archive)
    _release_result_figures(result)
    return {**result, "exports": files}


def run_geographic_bibliometrics(
    data: pd.DataFrame, collaboration_top_n=10, impact_top_n=15,
    min_papers=5, exclude_unknown=True, advanced_min_publications=5,
    citation_top_n=15, network_top_n=30, top_k_edges_per_node=5,
    network_layout_iterations=250, include_archive=True,
):
    """Run notebook Sections 17–18 and create publication-grade in-memory exports."""
    result = geographic_distribution_analysis(
        data,
        collaboration_top_n=collaboration_top_n,
        impact_top_n=impact_top_n,
        min_papers=min_papers,
        exclude_unknown=exclude_unknown,
    )
    advanced = advanced_country_analysis(
        result["data"], result["tables"]["country_collaboration_summary"],
        citation_top_n=citation_top_n,
        min_publications=advanced_min_publications,
        network_top_n=network_top_n,
        top_k_edges_per_node=top_k_edges_per_node,
        layout_iterations=network_layout_iterations,
    )
    result["tables"].update(advanced["tables"])
    result["figures"].update(advanced["figures"])
    result["warnings"] = list(dict.fromkeys(result["warnings"] + advanced["warnings"]))
    result["metadata"].update(advanced["metadata"])
    result["config"].update({
        "advanced_min_publications": int(advanced_min_publications),
        "citation_top_n": int(citation_top_n),
        "network_top_n": int(network_top_n),
        "top_k_edges_per_node": int(top_k_edges_per_node),
        "network_layout_iterations": int(network_layout_iterations),
    })
    result["network"] = advanced["network"]
    result["network_subgraph"] = advanced["network_subgraph"]
    files: dict[str, bytes] = {
        "Results/article_summary_with_country_classification.csv": dataframe_csv(result["data"]),
        "Results/article_summary_with_country_classification.xlsx": dataframe_excel(
            result["data"], "Country classification"
        ),
        "Results/exploded_country_appearances.csv": dataframe_csv(result["exploded_countries"]),
    }
    for name, table in result["tables"].items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            files[f"Results/{name}.csv"] = dataframe_csv(table)
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for name, table in result["tables"].items():
            if isinstance(table, pd.DataFrame) and not table.empty:
                table.to_excel(writer, index=False, sheet_name=name[:31])
    files["Results/geographic_distribution_tables.xlsx"] = workbook.getvalue()
    for name, figure in result["figures"].items():
        files[f"Plots/{name}.png"] = figure_png(figure, dpi=600)
        files[f"Plots/{name}.svg"] = figure_svg(figure)
        files[f"Plots/{name}.pdf"] = figure_pdf(figure)
    _attach_archive(files, "chronotome_geographic_distribution_outputs.zip", include_archive)
    _release_result_figures(result)
    return {**result, "exports": files}


def run_country_case_study(
    data: pd.DataFrame, exploded_countries: pd.DataFrame,
    country_stats: pd.DataFrame, country_name: str,
    affiliations: pd.DataFrame | None = None,
):
    """Run notebook Sections 20–21 for one selected country and export all artifacts."""
    result = country_case_study_analysis(
        data, exploded_countries, country_stats, country_name, affiliations=affiliations,
    )
    safe_name = result["safe_country_name"]
    files: dict[str, bytes] = {
        f"Plots/{safe_name}_Deep_Dive_Analysis.png": figure_png(result["figure"], dpi=300),
        f"Plots/{safe_name}_Deep_Dive_Analysis.svg": figure_svg(result["figure"]),
        f"Plots/{safe_name}_Deep_Dive_Analysis.pdf": figure_pdf(result["figure"]),
        f"Results/{safe_name}_Statistical_Report.txt": result["report_text"].encode("utf-8"),
    }
    for name, table in result["tables"].items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            files[f"Results/{safe_name}_{name}.csv"] = dataframe_csv(table)
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for name, table in result["tables"].items():
            if isinstance(table, pd.DataFrame) and not table.empty:
                table.to_excel(writer, index=False, sheet_name=name[:31])
    files[f"Results/{safe_name}_Country_Case_Study.xlsx"] = workbook.getvalue()
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    files[f"{safe_name}_Chronotome_Case_Study.zip"] = archive_buffer.getvalue()
    _release_result_figures(result)
    return {**result, "exports": files}


def run_advanced_analyses(data: pd.DataFrame, analyses=None, include_archive=True,
                          include_dataset=True):
    """Run selected paper-ready advanced analyses and export only their artifacts."""
    result = run_advanced_bibliometric_analysis(data, analyses=analyses)
    files: dict[str, bytes] = {}
    if include_dataset:
        files.update({
            "Results/advanced_analysis_dataset.csv": dataframe_csv(result["data"]),
            "Results/advanced_analysis_dataset.xlsx": dataframe_excel(result["data"], "Advanced dataset"),
        })
    for name, table in result["tables"].items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            files[f"Results/{name}.csv"] = dataframe_csv(table)
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for name, table in result["tables"].items():
            if isinstance(table, pd.DataFrame) and not table.empty:
                table.to_excel(writer, index=False, sheet_name=name[:31])
    files["Results/advanced_bibliometric_tables.xlsx"] = workbook.getvalue()
    for name, figure in result["figures"].items():
        files[f"Plots/{name}.png"] = figure_png(figure, dpi=600)
        files[f"Plots/{name}.svg"] = figure_svg(figure)
        files[f"Plots/{name}.pdf"] = figure_pdf(figure)
    _attach_archive(files, "chronotome_advanced_analyses_outputs.zip", include_archive)
    _release_result_figures(result)
    return {**result, "exports": files}


def _thematic_exports(result: dict, archive_name: str, workbook_name: str,
                      include_archive=True, include_dataset=True) -> dict:
    """Create consistent CSV/XLSX/SVG/PNG/PDF outputs for one thematic stage."""
    files: dict[str, bytes] = {}
    if include_dataset and isinstance(result.get("data"), pd.DataFrame):
        files["Results/thematic_analysis_dataset.csv"] = dataframe_csv(result["data"])
        files["Results/thematic_analysis_dataset.xlsx"] = dataframe_excel(result["data"], "Thematic dataset")
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        wrote = False
        for name, table in result.get("tables", {}).items():
            if isinstance(table, pd.DataFrame) and not table.empty:
                files[f"Results/{name}.csv"] = dataframe_csv(table)
                table.to_excel(writer, index=False, sheet_name=name[:31])
                wrote = True
        if not wrote:
            pd.DataFrame({"Status": ["No non-empty tables were generated"]}).to_excel(
                writer, index=False, sheet_name="Status"
            )
    files[f"Results/{workbook_name}"] = workbook.getvalue()
    for name, figure in result.get("figures", {}).items():
        files[f"Plots/{name}.png"] = figure_png(figure, dpi=600)
        files[f"Plots/{name}.svg"] = figure_svg(figure)
        files[f"Plots/{name}.pdf"] = figure_pdf(figure)
    _attach_archive(files, archive_name, include_archive)
    _release_result_figures(result)
    return {**result, "exports": files}


def run_thematic_preprocessing(data: pd.DataFrame, search_string: str, noise_lists: dict,
                               blocklist: set[str], min_df=None, max_df=0.90, include_archive=True,
                               include_dataset=True):
    result = thematic_preprocessing(
        data, search_string, noise_lists, blocklist, min_df=min_df, max_df=max_df,
    )
    return _thematic_exports(
        result, "chronotome_thematic_preprocessing_outputs.zip", "thematic_preprocessing_tables.xlsx",
        include_archive, include_dataset,
    )


def run_topic_model_evaluation(data: pd.DataFrame, k_values, min_df=2, max_df=0.95, max_iter=500,
                               include_archive=True, include_dataset=True):
    result = topic_model_evaluation(data, k_values, min_df=min_df, max_df=max_df, max_iter=max_iter)
    return _thematic_exports(
        result, "chronotome_topic_evaluation_outputs.zip", "topic_evaluation_tables.xlsx",
        include_archive, include_dataset,
    )


def run_final_topic_models(data: pd.DataFrame, lda_k: int, nmf_k: int, bin_duration=5,
                           top_words=15, min_df=2, max_df=0.95, include_archive=True):
    result = final_topic_models(
        data, lda_k, nmf_k, bin_duration=bin_duration, top_words=top_words,
        min_df=min_df, max_df=max_df,
    )
    return _thematic_exports(result, "chronotome_final_topic_models_outputs.zip", "final_topic_model_tables.xlsx", include_archive)


def run_advanced_thematic_analysis(data: pd.DataFrame, cooccurrence_threshold=0.1,
                                   min_country_documents=10, top_countries=20, include_archive=True,
                                   include_dataset=True):
    result = advanced_thematic_analysis(
        data, cooccurrence_threshold=cooccurrence_threshold,
        min_country_documents=min_country_documents, top_countries=top_countries,
    )
    return _thematic_exports(
        result, "chronotome_advanced_thematic_outputs.zip", "advanced_thematic_tables.xlsx",
        include_archive, include_dataset,
    )


def prepare_uploaded_thematic_dataset(data: pd.DataFrame):
    prepared, warnings = prepare_thematic_dataset(data)
    return {"data": prepared, "warnings": warnings}


def _graphml_bytes(graph) -> bytes:
    """Serialize a NetworkX graph without touching the filesystem."""
    return "\n".join(nx.generate_graphml(graph)).encode("utf-8")


def _institutional_exports(result: dict, archive_name: str, include_archive=True,
                           include_dataset=True) -> dict:
    """Create notebook filenames plus CSV/XLSX/GraphML and vector figure formats."""
    analysis_name = result["metadata"]["analysis_name"]
    top_n_plot = result["config"]["top_n_plot"]
    files: dict[str, bytes] = {
        f"Results/Top_Institutions_By_Publications_{analysis_name}.csv": dataframe_csv(
            result["tables"]["institution_ranking"]
        ),
        f"Results/Top_Institutions_By_Publications_{analysis_name}.xlsx": dataframe_excel(
            result["tables"]["institution_ranking"], "Institution ranking"
        ),
        f"Results/Institution_Collaboration_Counts_{analysis_name}.csv": dataframe_csv(
            result["tables"]["collaboration_counts"]
        ),
        f"Results/network_data_{analysis_name}.graphml": _graphml_bytes(result["full_graph"]),
        f"Results/network_data_{analysis_name}_nodes.csv": dataframe_csv(result["tables"]["network_nodes"]),
        f"Results/network_data_{analysis_name}_edges.csv": dataframe_csv(result["tables"]["network_edges"]),
        "Results/Analysis_Summary_Report.xlsx": dataframe_excel(
            result["tables"]["analysis_summary"], "Analysis summary"
        ),
    }
    if include_dataset:
        files.update({
            "Results/article_summary_with_country_classification.csv": dataframe_csv(result["prepared_data"]),
            "Results/article_summary_with_country_classification.xlsx": dataframe_excel(
                result["prepared_data"], "Geographic handoff"
            ),
        })
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for name, table in result["tables"].items():
            if isinstance(table, pd.DataFrame):
                table.to_excel(writer, index=False, sheet_name=name[:31])
    files[f"Results/Institutional_Analysis_{analysis_name}.xlsx"] = workbook.getvalue()
    for name, figure in result["figures"].items():
        if figure is None:
            continue
        files[f"Plots/{name}.png"] = figure_png(figure, dpi=600)
        files[f"Plots/{name}.svg"] = figure_svg(figure)
        files[f"Plots/{name}.pdf"] = figure_pdf(figure)
    _attach_archive(files, archive_name, include_archive)
    _release_result_figures(result)
    return {**result, "exports": files}


def run_institutional_analysis(
    data: pd.DataFrame, analysis_name="Global_All", top_n_list=1000,
    top_n_plot=30, max_institutions_per_paper=50, include_archive=True,
    include_dataset=True,
):
    result = institutional_analysis(
        data, analysis_name=analysis_name, top_n_list=top_n_list,
        top_n_plot=top_n_plot,
        max_institutions_per_paper=max_institutions_per_paper,
    )
    return _institutional_exports(
        result, f"chronotome_institutional_{analysis_name}_outputs.zip",
        include_archive, include_dataset,
    )


def run_topic_institutional_analysis(
    data: pd.DataFrame, topic, top_n_list=1000, top_n_plot=25,
    max_institutions_per_paper=50, include_archive=True, include_dataset=True,
):
    if "Dominant_Topic" not in data.columns:
        raise ValueError("Run the final LDA topic model before topic-level institutional analysis.")
    topic_frame = data[data["Dominant_Topic"].astype(str) == str(topic)].copy()
    if topic_frame.empty:
        raise ValueError(f"Topic {topic} has no articles.")
    safe_topic = str(topic).replace(".", "_")
    result = institutional_analysis(
        topic_frame, analysis_name="Global_All", output_name=f"Topic_{safe_topic}",
        top_n_list=top_n_list, top_n_plot=top_n_plot,
        max_institutions_per_paper=max_institutions_per_paper,
    )
    result["metadata"]["topic"] = topic
    return _institutional_exports(
        result, f"chronotome_institutional_Topic_{safe_topic}_outputs.zip",
        include_archive, include_dataset,
    )


def run_institutional_community_visualization(
    institutional_result: dict, top_n_to_plot: int | None = None, include_archive=True,
):
    """Generate and export the selected network's advanced community figure."""
    result = institutional_community_visualization(
        institutional_result, top_n_to_plot=top_n_to_plot,
    )
    basename = result["basename"]
    files: dict[str, bytes] = {
        f"Plots/{basename}.png": figure_png(result["figure"], dpi=600),
        f"Plots/{basename}.svg": figure_svg(result["figure"]),
        f"Plots/{basename}.pdf": figure_pdf(result["figure"]),
    }
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for name, table in result["tables"].items():
            files[f"Results/{name}_{result['metadata']['network_type']}.csv"] = dataframe_csv(table)
            table.to_excel(writer, index=False, sheet_name=name[:31])
    files[f"Results/Institutional_Communities_{result['metadata']['network_type']}.xlsx"] = workbook.getvalue()
    _attach_archive(
        files,
        f"chronotome_institutional_communities_{result['metadata']['network_type']}.zip",
        include_archive,
    )
    _release_result_figures(result)
    return {**result, "exports": files}


def run_all_workflow(
    scopus_files=None, wos_files=None, modes=None, config=None,
    ingestion_result: dict | None = None, progress_callback=None,
):
    """Run the complete workflow under a bounded-memory raster policy."""
    with raster_export_policy(max_dpi=300, max_side_px=4800):
        return _run_all_workflow_impl(
            scopus_files=scopus_files, wos_files=wos_files, modes=modes,
            config=config, ingestion_result=ingestion_result,
            progress_callback=progress_callback,
        )


def _run_all_workflow_impl(
    scopus_files=None, wos_files=None, modes=None, config=None,
    ingestion_result: dict | None = None, progress_callback=None,
):
    """Run every modern Chronotome stage through community visualization.

    Individual stage runners remain authoritative, so this convenience path
    cannot drift from the guided pages' analytical logic.
    """
    config = {
        "enable_time_filter": True, "collection_year": None,
        "top_n": 10, "min_source_papers": 5,
        "country_min_papers": 5, "institutional_top_n_plot": 30,
        "max_institutions_per_paper": 50,
        "topic_k_values": list(range(3, 11)), "thematic_min_df": None,
        "topic_model_min_df": 2, "topic_bin_duration": 5,
        "run_topic_institutional": True,
        "community_top_n_global": 50, "community_top_n_eu": 30,
        **(config or {}),
    }
    stage_summaries: dict[str, dict] = {}
    manifest_rows: list[dict] = []
    warnings: list[str] = []
    archive_buffer = io.BytesIO()
    archive = zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED)
    included_files = 0

    def notify(stage: str, state: str, detail: str = ""):
        if progress_callback is not None:
            progress_callback(stage, state, detail)

    def record(stage_key: str, label: str, result: dict | None, status="Complete", detail=""):
        nonlocal included_files
        stage_warnings = result.get("warnings", []) if result else []
        warnings.extend(stage_warnings)
        documents = ""
        if result:
            for data_key in ("data", "processed_data", "article_summary"):
                if isinstance(result.get(data_key), pd.DataFrame):
                    documents = len(result[data_key])
                    break
        if result is not None:
            for path, content in result.get("exports", {}).items():
                if path.lower().endswith(".zip"):
                    continue
                archive.writestr(f"{stage_key}/{path.lstrip('/')}", content)
                included_files += 1
            figures = list(result.get("figures", {}).values())
            if result.get("figure") is not None:
                figures.append(result["figure"])
            release_figures(figures)
            # The master archive now owns serialized artifacts. Keeping each
            # stage's bytes and plot objects would multiply session memory.
            result.pop("exports", None)
            result.pop("figures", None)
            result.pop("figure", None)
        rss = round(_rss_megabytes(), 1)
        stage_summaries[stage_key] = {
            "label": label, "status": status, "documents": documents,
            "warnings": len(stage_warnings), "rss_mb": rss,
        }
        manifest_rows.append({
            "Stage": label, "Status": status, "Documents": documents,
            "Warnings": len(stage_warnings), "RSS after stage (MB)": rss,
            "Detail": detail,
        })
        gc.collect()

    notify("Data ingestion", "running")
    if ingestion_result is None:
        ingestion = run_ingestion(
            scopus_files=scopus_files, wos_files=wos_files, modes=modes,
            config={
                "enable_time_filter": bool(config["enable_time_filter"]),
                "collection_year": config["collection_year"],
            },
            include_archive=False,
        )
    else:
        # Never mutate a guided-page result supplied from session state.
        ingestion = {**ingestion_result, "exports": dict(ingestion_result.get("exports", {}))}
    record("01_ingestion", "Data ingestion", ingestion)
    notify("Data ingestion", "complete", f"{len(ingestion['processed_data']):,} records")

    notify("Entity resolution", "running")
    entity = run_entity_resolution(ingestion["processed_data"], include_archive=False)
    record("02_entity_resolution", "Entity resolution", entity)
    notify("Entity resolution", "complete", f"{len(entity['article_summary']):,} articles")
    del ingestion
    gc.collect()

    notify("Corpus and production", "running")
    corpus = run_corpus_bibliometrics(
        entity["article_summary"], cutoff_year=config["collection_year"],
        top_n=int(config["top_n"]), min_source_papers=int(config["min_source_papers"]),
        include_archive=False,
    )
    record("03_corpus_and_production", "Corpus and production", corpus)
    notify("Corpus and production", "complete")
    del entity
    gc.collect()

    notify("Geographic analysis", "running")
    geographic = run_geographic_bibliometrics(
        corpus["data"], min_papers=int(config["country_min_papers"]),
        advanced_min_publications=int(config["country_min_papers"]),
        include_archive=False,
    )
    record("04_geographic_analysis", "Geographic analysis", geographic)
    notify("Geographic analysis", "complete")
    del corpus
    gc.collect()

    notify("Advanced evaluative analyses", "running")
    advanced = run_advanced_analyses(
        geographic["data"], include_archive=False, include_dataset=False
    )
    record("05_advanced_evaluative", "Advanced evaluative analyses", advanced)
    notify("Advanced evaluative analyses", "complete")
    del advanced
    gc.collect()

    thematic_final = None
    notify("Thematic preprocessing", "running")
    try:
        thematic_preprocessed = run_thematic_preprocessing(
            geographic["data"], "", DEFAULT_NOISE_LISTS, DEFAULT_BLOCKLIST_PHRASES,
            min_df=config["thematic_min_df"], include_archive=False,
            include_dataset=False,
        )
        record("06_thematic_preprocessing", "Thematic preprocessing", thematic_preprocessed)
        notify("Thematic preprocessing", "complete")

        notify("Automatic topic evaluation", "running")
        topic_evaluation = run_topic_model_evaluation(
            thematic_preprocessed["data"], config["topic_k_values"],
            min_df=int(config["topic_model_min_df"]), include_archive=False,
        )
        record("07_topic_evaluation", "Automatic topic evaluation", topic_evaluation)
        notify(
            "Automatic topic evaluation", "complete",
            f"LDA k={topic_evaluation['best_k']}; NMF k={topic_evaluation['best_nmf_k']}",
        )

        notify("Final topic models", "running")
        thematic_final = run_final_topic_models(
            thematic_preprocessed["data"], topic_evaluation["best_k"],
            topic_evaluation["best_nmf_k"],
            bin_duration=int(config["topic_bin_duration"]),
            min_df=int(config["topic_model_min_df"]),
            include_archive=False,
        )
        record("08_final_topic_models", "Final LDA/NMF topic models", thematic_final)
        notify("Final topic models", "complete")
        del thematic_preprocessed, topic_evaluation
        gc.collect()

        notify("Advanced thematic analyses", "running")
        thematic_advanced = run_advanced_thematic_analysis(
            thematic_final["data"], include_archive=False, include_dataset=False
        )
        record("09_advanced_thematic", "Advanced thematic analyses", thematic_advanced)
        notify("Advanced thematic analyses", "complete")
        del thematic_advanced
        gc.collect()
    except Exception as exc:
        detail = f"Thematic branch skipped after an analysis constraint: {exc}"
        warnings.append(detail)
        record("06_thematic_status", "Thematic analysis", None, status="Skipped", detail=detail)
        notify("Thematic analysis", "skipped", str(exc))

    if thematic_final is not None and bool(config["run_topic_institutional"]):
        topics = sorted(thematic_final["data"]["Dominant_Topic"].dropna().unique(), key=lambda value: str(value))
        for topic in topics:
            label = f"Topic {topic} institutional network"
            notify(label, "running")
            try:
                topic_result = run_topic_institutional_analysis(
                    thematic_final["data"], topic,
                    top_n_plot=min(25, int(config["institutional_top_n_plot"])),
                    max_institutions_per_paper=int(config["max_institutions_per_paper"]),
                    include_archive=False, include_dataset=False,
                )
                safe_topic = str(topic).replace(".", "_")
                record(f"10_topic_{safe_topic}_institutions", label, topic_result)
                notify(label, "complete")
                del topic_result
                gc.collect()
            except Exception as exc:
                detail = str(exc)
                record(f"10_topic_{topic}_status", label, None, status="Skipped", detail=detail)
                warnings.append(f"{label} skipped: {detail}")
                notify(label, "skipped", detail)

    analysis_names = ("Global_All", "Global_MCP", "Global_SCP", "EU_All", "EU_MCP", "EU_SCP")
    for index, analysis_name in enumerate(analysis_names, 1):
        label = f"Institutional analysis: {analysis_name}"
        notify(label, "running")
        try:
            institutional = run_institutional_analysis(
                geographic["data"], analysis_name=analysis_name,
                top_n_plot=int(config["institutional_top_n_plot"]),
                max_institutions_per_paper=int(config["max_institutions_per_paper"]),
                include_archive=False, include_dataset=False,
            )
            record(f"{20 + index:02d}_institutional_{analysis_name}", label, institutional)
            notify(label, "complete")
        except Exception as exc:
            detail = str(exc)
            record(f"{20 + index:02d}_institutional_{analysis_name}", label, None, status="Skipped", detail=detail)
            warnings.append(f"{label} skipped: {detail}")
            notify(label, "skipped", detail)
            continue

        community_label = f"Community visualization: {analysis_name}"
        notify(community_label, "running")
        try:
            top_n = (
                int(config["community_top_n_global"])
                if analysis_name.startswith("Global") else int(config["community_top_n_eu"])
            )
            community = run_institutional_community_visualization(
                institutional, top_n_to_plot=top_n, include_archive=False,
            )
            record(f"{30 + index:02d}_communities_{analysis_name}", community_label, community)
            notify(community_label, "complete")
            del community, institutional
            gc.collect()
        except Exception as exc:
            detail = str(exc)
            record(f"{30 + index:02d}_communities_{analysis_name}", community_label, None, status="Skipped", detail=detail)
            warnings.append(f"{community_label} skipped: {detail}")
            notify(community_label, "skipped", detail)

    if thematic_final is not None:
        del thematic_final
    del geographic
    gc.collect()

    manifest = pd.DataFrame(manifest_rows)
    manifest_excel = dataframe_excel(manifest, "Workflow manifest")
    archive.writestr("00_Workflow_Summary/full_workflow_manifest.xlsx", manifest_excel)
    archive.writestr("00_Workflow_Summary/full_workflow_manifest.csv", dataframe_csv(manifest))
    archive.writestr(
        "00_Workflow_Summary/README.txt",
        (
            "Chronotome complete background workflow\n"
            "Includes ingestion through institutional community visualization.\n"
            "Each stage folder contains its Excel/CSV tables, publication-grade plots, and network files.\n"
        ).encode("utf-8"),
    )
    archive.close()
    exports = {
        "chronotome_complete_background_workflow.zip": archive_buffer.getvalue(),
        "full_workflow_manifest.xlsx": manifest_excel,
    }
    notify("Complete workflow", "complete", f"{included_files:,} files packaged")
    return {
        "stages": stage_summaries, "manifest": manifest,
        "warnings": list(dict.fromkeys(warnings)), "exports": exports,
        "metadata": {
            "packaged_files": included_files,
            "documents": int(manifest.loc[manifest["Stage"] == "Geographic analysis", "Documents"].iloc[0]),
            "final_rss_mb": round(_rss_megabytes(), 1),
        },
        "config": config,
    }


def run_chronotome(uploaded_file, config=None):
    """Run ingestion, harmonization, analyses, plots, and in-memory exports.

    Parameters
    ----------
    uploaded_file:
        One Streamlit UploadedFile or a list of Scopus/WoS CSV, TXT, XLS, or
        XLSX exports. Multiple files from the same database are appended.
    config:
        Existing notebook parameters exposed by the app: time filter,
        collection year, ranking size, source/country minimum publications,
        network plot size, institution cap, and thematic topic settings.

    Returns
    -------
    dict
        Processed data, tables, figures, warnings, metadata, network objects,
        PRISMA counts, and downloadable byte files.
    """
    config = {
        "enable_time_filter": True, "collection_year": None, "top_n": 10,
        "min_papers": 5, "network_top_n": 30, "max_institutions_per_paper": 50,
        "run_thematic": True, "topic_count": 8, "min_document_frequency": None,
        **(config or {}),
    }
    metadata = inspect_uploads(uploaded_file)
    loaded = load_uploads(uploaded_file)
    sources = combine_by_source(loaded)
    merged, prisma, warnings = harmonize(sources)
    processed, duplicate_records = deduplicate(merged, prisma)
    processed = apply_time_filter(processed, config["enable_time_filter"], config["collection_year"], prisma)
    if processed.empty:
        raise ValueError("No records remain after preprocessing. Disable the year filter or check publication years.")
    processed, affiliations, affiliation_warnings = enrich_affiliations(processed)
    warnings.extend(affiliation_warnings)
    processed = add_mncs(processed)

    sources_table = source_metrics(processed)
    countries, country_timeline = country_metrics(processed)
    networks, network_summary = institution_networks(processed, config["max_institutions_per_paper"])
    tables = {
        "prisma_report": prisma_table(prisma),
        "main_information_summary": main_summary(processed),
        "document_types": document_types(processed),
        "annual_production": annual_production(processed),
        "citation_dynamics": citation_dynamics(processed),
        "author_metrics": author_metrics(processed),
        "source_metrics": sources_table,
        "country_metrics": countries,
        "country_publication_timeline": country_timeline,
        "affiliations_exploded": affiliations,
        "duplicate_doi_records": duplicate_records,
        "articles_ranked_by_citations": ranked_articles(processed),
        "hot_papers": hot_papers(processed),
        "bradford": bradford_table(sources_table),
        "team_size_impact": team_size_impact(processed),
        "institution_network_summary": network_summary,
    }
    for key, network in networks.items():
        tables[f"institutions_{key.lower()}"] = network["ranking"]
        tables[f"institution_edges_{key.lower()}"] = network["edges"]
        tables[f"institution_communities_{key.lower()}"] = pd.DataFrame(
            [(index, len(nodes), "; ".join(nodes)) for index, nodes in enumerate(network["communities"], 1)],
            columns=["Community", "Size", "Institutions"],
        )
    if config["run_thematic"]:
        thematic_tables, thematic_warnings = thematic_analysis(
            processed, config["topic_count"], config["min_document_frequency"]
        )
        tables.update(thematic_tables)
        warnings.extend(thematic_warnings)
    figures = build_figures(tables, networks, config)
    exports = create_exports(processed, tables, figures)
    release_figures(figures.values())
    return {
        "processed_data": processed,
        "tables": tables,
        "figures": figures,
        "warnings": list(dict.fromkeys(warnings)),
        "metadata": metadata,
        "prisma": prisma,
        "networks": networks,
        "exports": exports,
        "config": config,
    }
