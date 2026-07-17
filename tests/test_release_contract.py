"""Release-contract regressions for Chronotome 0.2."""

from __future__ import annotations

import ast
import io
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import chronotome
import chronotome_core
from chronotome.cli import _DARK_THEME_ARGS
from chronotome_core.descriptive_bibliometrics import add_internal_mncs, author_analysis
from chronotome_core.entity_resolution import canonicalize_country_name, resolve_entities
from chronotome_core.export import dataframe_csv
from chronotome_core.geographic_bibliometrics import geographic_distribution_analysis
from chronotome_core.institutional_bibliometrics import (
    EU27_COUNTRIES,
    is_exclusively_eu,
    prepare_institutional_dataset,
)
from chronotome_core.io import (
    INTERNAL_SOURCE_FILE_COLUMN,
    InputError,
    inspect_source_uploads,
    parse_wos_plaintext,
    read_uploaded_file_detailed,
)
from chronotome_core.preprocessing import (
    FINAL_COLUMNS,
    aggregate_provenance,
    author_source_counts,
    count_cited_references,
    deduplicate,
    harmonize,
    normalize_doi,
    normalize_title_key,
    select_author_text,
)
from chronotome_core.thematic_bibliometrics import (
    DEFAULT_BLOCKLIST_PHRASES,
    DEFAULT_NOISE_LISTS,
    prepare_thematic_dataset,
)
from chronotome_ui.branding import BRAND, LIGHT, apply_brand_theme
from chronotome_ui.dataframe_display import arrow_safe_frame


ROOT = Path(__file__).resolve().parents[1]


class Upload(io.BytesIO):
    def __init__(self, frame: pd.DataFrame, name: str):
        super().__init__(frame.to_csv(index=False).encode("utf-8"))
        self.name = name


class BytesUpload(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


def _harmonize(scopus: pd.DataFrame | None = None, wos: pd.DataFrame | None = None):
    sources = {}
    if scopus is not None:
        sources["Scopus"] = scopus
    if wos is not None:
        sources["WoS"] = wos
    return harmonize(sources, include_audit=True)


class WorkflowContractTests(unittest.TestCase):
    def test_one_public_full_workflow_and_strict_config(self):
        self.assertEqual(chronotome.__version__, "0.2.0")
        self.assertIs(chronotome.run_chronotome, chronotome_core.run_chronotome)
        signature = inspect.signature(chronotome.run_chronotome)
        self.assertEqual(signature.parameters["scopus_files"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertFalse(hasattr(chronotome_core, "run_all_workflow"))
        with self.assertRaisesRegex(ValueError, "Unknown Chronotome configuration key"):
            chronotome_core.resolve_config({"min_papers": 5})
        resolved = chronotome_core.resolve_config({"top_n": 7})
        self.assertEqual(resolved["top_n"], 7)
        self.assertEqual(tuple(resolved["topic_k_values"]), tuple(range(3, 11)))

        runner_source = (ROOT / "chronotome_core" / "runner.py").read_text(encoding="utf-8")
        runner_tree = ast.parse(runner_source)
        full_definitions = [
            node for node in runner_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run_chronotome"
        ]
        self.assertEqual(len(full_definitions), 1)
        self.assertNotIn("run_all_workflow", runner_source)
        self.assertFalse((ROOT / "chronotome_core" / "analysis.py").exists())
        self.assertFalse((ROOT / "chronotome_core" / "visualization.py").exists())

    def test_streamlit_full_and_guided_pages_share_stage_functions(self):
        full_source = (ROOT / "chronotome_ui" / "full_workflow.py").read_text(encoding="utf-8")
        self.assertIn("run_chronotome", full_source)
        self.assertNotIn("run_all_workflow", full_source)
        expected = {
            "ingestion.py": "run_ingestion",
            "entity_resolution.py": "run_entity_resolution",
            "corpus_bibliometrics.py": "run_corpus_bibliometrics",
            "geographic_analysis.py": "run_geographic_bibliometrics",
            "advanced_analyses.py": "run_advanced_analyses",
            "thematic_analysis.py": "run_thematic_preprocessing",
            "institutional_analysis.py": "run_institutional_analysis",
        }
        for filename, stage_name in expected.items():
            source = (ROOT / "chronotome_ui" / filename).read_text(encoding="utf-8")
            self.assertIn(stage_name, source, filename)

    def test_latest_release_keeps_explicit_analysis_buttons(self):
        corpus_source = (
            ROOT / "chronotome_ui" / "corpus_bibliometrics.py"
        ).read_text(encoding="utf-8")
        geographic_source = (
            ROOT / "chronotome_ui" / "geographic_analysis.py"
        ).read_text(encoding="utf-8")
        institutional_source = (
            ROOT / "chronotome_ui" / "institutional_analysis.py"
        ).read_text(encoding="utf-8")
        app_source = (ROOT / "chronotome" / "app.py").read_text(encoding="utf-8")

        self.assertIn("Generate corpus analysis", corpus_source)
        self.assertIn("if generate_analysis and data is not None", corpus_source)
        self.assertIn("Generate geographic analysis", geographic_source)
        self.assertIn("if generate_analysis and data is not None", geographic_source)
        self.assertIn("Generate institutional network", institutional_source)
        self.assertIn("Compare two institutional networks", institutional_source)
        self.assertIn("Local installation", app_source)
        self.assertLess(
            app_source.index('"Local installation"'),
            app_source.index('"Data ingestion"'),
        )

    def test_public_installation_documentation_uses_pypi(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        installation = (
            ROOT / "chronotome_ui" / "local_installation.py"
        ).read_text(encoding="utf-8")
        for text in (readme, installation):
            self.assertIn("https://pypi.org/project/chronotome/", text)
            self.assertIn("python -m pip install chronotome", text)
            self.assertIn("python -m pip uninstall chronotome", text)
        for removed_heading in (
            "Methodological assumptions retained",
            "Not yet supported",
            "Deploy on Streamlit Community Cloud",
        ):
            self.assertNotIn(removed_heading, readme)

    def test_orchestrator_matches_direct_canonical_stages(self):
        # This contract compares deterministic tables and metadata, not plot
        # pixels.  Avoid spending the regression budget rasterizing the same
        # figures in both the direct and orchestrated runs.
        for exporter, payload in (
            ("figure_png", b"test-png"),
            ("figure_svg", b"test-svg"),
            ("figure_pdf", b"test-pdf"),
        ):
            patcher = patch(
                f"chronotome_core.runner.{exporter}", return_value=payload
            )
            patcher.start()
            self.addCleanup(patcher.stop)

        source = pd.DataFrame([
            {
                "Authors": "Doe J.; Smith A.",
                "Title": "Canonical workflow paper A",
                "Year": 2020,
                "Cited by": 4,
                "DOI": "doi:10.1000/A.",
                "Source title": "Journal of Canonical Tests",
                "Document Type": "Article",
                "Affiliations": "Department, Charles University, Prague, Czech Republic",
                "References": "Reference 1; Reference 2",
                "Abstract": "Canonical workflow concepts and reproducible evidence",
            },
            {
                "Authors": "Roe B.",
                "Title": "Canonical workflow paper B",
                "Year": 2021,
                "Cited by": 0,
                "DOI": "10.1000/b",
                "Source title": "Journal of Canonical Tests",
                "Document Type": "Article",
                "Affiliations": "Laboratory, University of Bucharest, Bucharest, Romania",
                "References": "",
                "Abstract": "Reproducible workflow concepts and transparent evidence",
            },
        ])
        direct_ingestion = chronotome_core.run_ingestion(
            scopus_files=[Upload(source, "/private/client/canonical_scopus.csv")],
            modes={"Scopus": "single", "WoS": "single"},
            config={"enable_time_filter": False},
        )
        direct_entity = chronotome_core.run_entity_resolution(
            direct_ingestion["processed_data"]
        )
        direct_corpus = chronotome_core.run_corpus_bibliometrics(
            direct_entity["article_summary"],
            cutoff_year=None,
            top_n=10,
            min_source_papers=5,
            max_source_title_length=30,
        )
        direct_geographic = chronotome_core.run_geographic_bibliometrics(
            direct_corpus["data"], min_papers=5,
            advanced_min_publications=5, include_archive=False,
        )
        direct_advanced = chronotome_core.run_advanced_analyses(
            direct_geographic["data"], include_archive=False, include_dataset=False,
        )
        direct_thematic = chronotome_core.run_thematic_preprocessing(
            direct_geographic["data"], "", DEFAULT_NOISE_LISTS,
            DEFAULT_BLOCKLIST_PHRASES, min_df=1,
            include_archive=False, include_dataset=False,
        )
        direct_institutional = chronotome_core.run_institutional_analysis(
            direct_geographic["data"], analysis_name="Global_All",
            top_n_plot=30, max_institutions_per_paper=50,
            include_archive=False, include_dataset=False,
        )

        def institutional_stage(data, *, analysis_name, **kwargs):
            if analysis_name != "Global_All":
                raise ValueError("fixture validates the Global_All institutional stage")
            return chronotome_core.run_institutional_analysis(
                data, analysis_name=analysis_name, **kwargs
            )

        with (
            patch(
                "chronotome_core.runner.run_topic_model_evaluation",
                side_effect=ValueError("fixture validates thematic preprocessing only"),
            ),
            patch(
                "chronotome_core.runner.run_institutional_analysis",
                side_effect=institutional_stage,
            ),
            patch(
                "chronotome_core.runner.run_institutional_community_visualization",
                side_effect=ValueError("fixture does not validate plot pixels"),
            ),
        ):
            orchestrated = chronotome.run_chronotome(
                scopus_files=[Upload(source, "/private/client/canonical_scopus.csv")],
                modes={"Scopus": "single", "WoS": "single"},
                config={
                    "enable_time_filter": False,
                    "thematic_min_df": 1,
                    "run_topic_institutional": False,
                },
            )

        pd.testing.assert_frame_equal(
            orchestrated["processed_data"], direct_geographic["data"]
        )
        archive = zipfile.ZipFile(io.BytesIO(
            orchestrated["exports"]["chronotome_complete_background_workflow.zip"]
        ))
        self.assertEqual(
            archive.read("01_ingestion/merged_bibliometric_dataset.csv"),
            direct_ingestion["exports"]["merged_bibliometric_dataset.csv"],
        )
        self.assertEqual(
            archive.read("02_entity_resolution/final_article_summary_with_countries.csv"),
            direct_entity["exports"]["final_article_summary_with_countries.csv"],
        )
        for table_name in (
            "main_information_summary",
            "mncs_yearly_baselines",
            "author_metrics_complete",
        ):
            self.assertEqual(
                archive.read(f"03_corpus_and_production/Results/{table_name}.csv"),
                direct_corpus["exports"][f"Results/{table_name}.csv"],
            )
        stage_exports = (
            (
                "04_geographic_analysis/Results/country_master_stats.csv",
                direct_geographic["exports"]["Results/country_master_stats.csv"],
            ),
            (
                "05_advanced_evaluative/Results/final_main_summary.csv",
                direct_advanced["exports"]["Results/final_main_summary.csv"],
            ),
            (
                "06_thematic_preprocessing/Results/combined_ngram_frequency.csv",
                direct_thematic["exports"]["Results/combined_ngram_frequency.csv"],
            ),
            (
                "21_institutional_Global_All/Results/Top_Institutions_By_Publications_Global_All.csv",
                direct_institutional["exports"]["Results/Top_Institutions_By_Publications_Global_All.csv"],
            ),
        )
        for archive_path, direct_bytes in stage_exports:
            self.assertEqual(archive.read(archive_path), direct_bytes)
        self.assertEqual(
            orchestrated["metadata"]["ingestion"], direct_ingestion["metadata"]
        )
        self.assertEqual(
            direct_ingestion["metadata"]["input_records_by_source_file"],
            {"Scopus": {"canonical_scopus.csv": 2}},
        )
        self.assertEqual(
            direct_ingestion["verifications"]["Scopus"]["files"].iloc[0]["Columns"],
            len(source.columns),
        )
        self.assertIn("preprocessing_source_file_audit.csv", direct_ingestion["exports"])

    def test_no_expensive_validation_or_obsolete_imports_are_active(self):
        active_roots = [ROOT / "chronotome", ROOT / "chronotome_core", ROOT / "chronotome_ui"]
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for root in active_roots
            for path in root.rglob("*.py")
        )
        for forbidden in (
            "consensus_cross_validation", "generate_null_distribution",
            "normalized_mutual_info_score", "from .analysis", "from .visualization",
        ):
            self.assertNotIn(forbidden, text)


class ProvenanceAndDeduplicationTests(unittest.TestCase):
    def test_cross_database_fusion_preserves_primary_and_all_provenance(self):
        scopus = pd.DataFrame([{
            "Title": "A shared paper", "Year": 2020, "Cited by": 12,
            "DOI": "doi:10.1000/Example.", "References": "Ref A; Ref B",
            INTERNAL_SOURCE_FILE_COLUMN: "/private/path/scopus_part_1.csv",
        }])
        wos = pd.DataFrame([{
            "Article Title": "A shared paper", "Publication Year": 2020,
            "Times Cited, WoS Core": 4,
            "DOI": "https://doi.org/10.1000/example",
            "CR": "Ref C; Ref D; Ref E",
            INTERNAL_SOURCE_FILE_COLUMN: "/another/path/wos_part_2.txt",
        }])
        merged, prisma, _, audit = _harmonize(scopus, wos)
        result, _, dedup_audit = deduplicate(merged, prisma, include_audit=True)
        self.assertEqual(len(result), 1)
        record = result.iloc[0]
        self.assertEqual(record["DOI"], "10.1000/example")
        self.assertEqual(record["Primary Database"], "Scopus")
        self.assertEqual(record["Databases"], ["Scopus", "Web of Science"])
        self.assertEqual(record["Source Files"], ["scopus_part_1.csv", "wos_part_2.txt"])
        self.assertEqual(record["Cited References Raw"], "Ref A; Ref B")
        self.assertEqual(record["Cited Reference Count"], 2)
        self.assertNotIn("Database", result.columns)
        self.assertEqual(prisma["cross_database_duplicate_groups"], 1)
        self.assertEqual(prisma["records_with_multiple_source_files"], 1)
        self.assertEqual(prisma["doi_values_changed_by_normalization"], 2)
        self.assertEqual(audit["source_files"]["Input records"].sum(), 2)
        self.assertEqual(
            dedup_audit["provenance_combinations"].iloc[0]["Databases"],
            "Scopus; Web of Science",
        )

        display = arrow_safe_frame(result[["Databases", "Source Files"]])
        self.assertEqual(display.iloc[0]["Databases"], "Scopus; Web of Science")

    def test_doi_normalization_equivalent_forms_and_missing_tokens(self):
        forms = [
            "10.1000/Example", "doi:10.1000/example",
            "https://doi.org/10.1000/example",
            "http://dx.doi.org/10.1000/example", " 10.1000/example.",
            "10.1000 / example",
        ]
        self.assertEqual({normalize_doi(value) for value in forms}, {"10.1000/example"})
        for missing in (None, "", "NA", "n/a", "nan", "None", "NULL", "<NA>", pd.NA):
            self.assertTrue(pd.isna(normalize_doi(missing)))
        self.assertEqual(normalize_doi("10.1000/a(b):c_d;"), "10.1000/a(b):c_d")

    def test_incomplete_no_doi_records_remain_separate(self):
        scopus = pd.DataFrame([
            {"Title": "Complete title", "Year": 2020, "Cited by": 2, "DOI": None},
            {"Title": "complete-title", "Year": 2020, "Cited by": 1, "DOI": ""},
            {"Title": None, "Year": 2020, "Cited by": 1, "DOI": None},
            {"Title": "", "Year": 2020, "Cited by": 1, "DOI": None},
            {"Title": "Missing year", "Year": None, "Cited by": 1, "DOI": None},
            {"Title": "Missing year", "Year": None, "Cited by": 0, "DOI": None},
            {"Title": None, "Year": None, "Cited by": 1, "DOI": None},
            {"Title": None, "Year": None, "Cited by": 0, "DOI": None},
            {"Title": "DOI and no DOI stay apart", "Year": 2021, "Cited by": 9, "DOI": "10.1/x"},
            {"Title": "DOI and no DOI stay apart", "Year": 2021, "Cited by": 8, "DOI": None},
        ])
        merged, prisma, _, _ = _harmonize(scopus=scopus)
        result, _, audit = deduplicate(merged, prisma, include_audit=True)
        self.assertEqual(len(result), 9)
        self.assertEqual(prisma["title_year_based_fusion_groups"], 1)
        self.assertEqual(prisma["retained_missing_title"], 2)
        self.assertEqual(prisma["retained_missing_year"], 2)
        self.assertEqual(prisma["retained_missing_title_and_year"], 2)
        self.assertEqual(
            int((result["Title"] == "DOI and no DOI stay apart").sum()), 2
        )
        self.assertTrue(pd.isna(normalize_title_key(None)))
        self.assertTrue(pd.isna(normalize_title_key("---")))
        self.assertEqual(audit["summary"].iloc[-1]["Records / cells"], 9)

    def test_raw_reference_text_and_nullable_count_are_distinct(self):
        scopus = pd.DataFrame([
            {"Title": "Empty", "Year": 2020, "Cited by": 0, "References": ""},
            {"Title": "Missing", "Year": 2020, "Cited by": 0, "References": None},
            {
                "Title": "Exported count", "Year": 2020, "Cited by": 0,
                "References": "A; B", "Cited Reference Count": 9,
            },
        ])
        wos = pd.DataFrame([{
            "Article Title": "WoS refs", "Publication Year": 2020,
            "Times Cited, WoS Core": 0, "CR": "W1; W2; W3", "NR": 7,
        }])
        merged, _, _, _ = _harmonize(scopus, wos)
        counts = merged.set_index("Title")["Cited Reference Count"]
        self.assertEqual(counts["Empty"], 0)
        self.assertTrue(pd.isna(counts["Missing"]))
        self.assertEqual(counts["Exported count"], 9)
        self.assertEqual(counts["WoS refs"], 7)
        self.assertEqual(merged.set_index("Title").loc["WoS refs", "Cited References Raw"], "W1; W2; W3")
        self.assertEqual(count_cited_references(""), 0)
        self.assertTrue(pd.isna(count_cited_references(None)))

        tagged = parse_wos_plaintext(
            b"PT J\nAU Smith, J\n   Doe, A\nTI Tagged paper\nPY 2020\n"
            b"CR Reference A\n   Reference B\nCR Reference C\nER\nEF\n"
        )
        self.assertEqual(tagged.loc[0, "AU"], "Smith, J; Doe, A")
        self.assertEqual(tagged.loc[0, "CR"], "Reference A; Reference B; Reference C")
        tagged_merged, _, _, _ = _harmonize(wos=tagged)
        self.assertEqual(tagged_merged.loc[0, "Cited Reference Count"], 3)

    def test_uploaded_blank_reference_cells_remain_empty(self):
        csv_upload = BytesUpload(
            b"Title,Year,Cited by,References,Abstract\n"
            b"CSV blank,2020,0,,\n"
            b"CSV missing,2020,0,NA,\n",
            "references.csv",
        )
        csv_frame, _ = read_uploaded_file_detailed(csv_upload)
        self.assertEqual(csv_frame.loc[0, "References"], "")
        self.assertTrue(pd.isna(csv_frame.loc[1, "References"]))
        self.assertTrue(pd.isna(csv_frame.loc[0, "Abstract"]))

        workbook = io.BytesIO()
        pd.DataFrame(
            {
                "Title": ["XLSX blank", "XLSX missing"],
                "Year": [2020, 2020],
                "Cited by": [0, 0],
                "References": ["", "NA"],
                "Abstract": ["", ""],
            }
        ).to_excel(workbook, index=False)
        xlsx_frame, _ = read_uploaded_file_detailed(
            BytesUpload(workbook.getvalue(), "references.xlsx")
        )
        self.assertEqual(xlsx_frame.loc[0, "References"], "")
        self.assertTrue(pd.isna(xlsx_frame.loc[1, "References"]))
        self.assertTrue(pd.isna(xlsx_frame.loc[0, "Abstract"]))

        csv_merged, _, _, _ = _harmonize(scopus=csv_frame)
        xlsx_merged, _, _, _ = _harmonize(scopus=xlsx_frame)
        self.assertEqual(
            csv_merged.set_index("Title").loc["CSV blank", "Cited Reference Count"],
            0,
        )
        self.assertTrue(pd.isna(
            csv_merged.set_index("Title").loc["CSV missing", "Cited Reference Count"]
        ))
        self.assertEqual(
            xlsx_merged.set_index("Title").loc["XLSX blank", "Cited Reference Count"],
            0,
        )
        self.assertTrue(pd.isna(
            xlsx_merged.set_index("Title").loc["XLSX missing", "Cited Reference Count"]
        ))

    def test_source_filename_collision_is_rejected(self):
        frame = pd.DataFrame({
            "Title": ["Paper"], "Year": [2020],
            INTERNAL_SOURCE_FILE_COLUMN: ["attacker.csv"],
        })
        with self.assertRaises(InputError):
            inspect_source_uploads([Upload(frame, "query.csv")], "Scopus", "single")

    def test_provenance_export_is_deterministic_and_non_mutating(self):
        frame = pd.DataFrame({
            "Databases": [["Scopus", "Web of Science"]],
            "Source Files": [["first.csv", "second.txt"]],
            "Set value": [{"b", "a"}],
            INTERNAL_SOURCE_FILE_COLUMN: ["private-marker.csv"],
        })
        databases = frame.at[0, "Databases"]
        first = dataframe_csv(frame)
        second = dataframe_csv(frame)
        self.assertEqual(first, second)
        self.assertIs(frame.at[0, "Databases"], databases)
        exported = pd.read_csv(io.BytesIO(first))
        self.assertNotIn(INTERNAL_SOURCE_FILE_COLUMN, exported.columns)
        self.assertEqual(json.loads(exported.at[0, "Databases"]), ["Scopus", "Web of Science"])
        self.assertEqual(
            aggregate_provenance([{"second.txt", "First.csv", "first.csv"}]),
            ["First.csv", "second.txt"],
        )


class MetricAndEntityTests(unittest.TestCase):
    def test_mncs_definition_and_zero_mean_behavior(self):
        frame = pd.DataFrame({
            "Title": ["A", "B", "C", "D", "E", "F"],
            "Publication Year": [2020, 2020, 2021, 2021, 2022, np.nan],
            "Cited by": [2, 6, 0, 0, np.nan, 3],
        })
        result, baselines, warnings = add_internal_mncs(frame)
        np.testing.assert_allclose(result.loc[:1, "MNCS"], [0.5, 1.5])
        self.assertEqual(result.loc[:1, "MNCS_Baseline_Citations"].tolist(), [4.0, 4.0])
        self.assertEqual(result.loc[:1, "MNCS_Reference_Set_Size"].tolist(), [2, 2])
        self.assertTrue(result.loc[:1, "MNCS_Defined"].all())
        self.assertTrue(result.loc[2:3, "MNCS"].isna().all())
        self.assertFalse(result.loc[2:3, "MNCS_Defined"].any())
        self.assertTrue(result.loc[4:5, "MNCS"].isna().all())
        self.assertEqual(
            baselines.set_index("Publication Year").loc[2021, "Average Citations (Baseline)"], 0
        )
        self.assertIn("undefined", " ".join(warnings).lower())
        self.assertNotIn("Internal_MNCS", result)

    def test_author_names_fall_back_row_by_row(self):
        frame = pd.DataFrame({
            "Author Full Names": ["Full, Person", pd.NA, "   "],
            "Authors": ["FP", "Fallback B", "Fallback C"],
            "Cited by": [2, 4, 6],
            "Publication Year": [2020, 2020, 2020],
        })
        selected = select_author_text(frame)
        self.assertEqual(selected.tolist(), ["Full, Person", "Fallback B", "Fallback C"])
        self.assertEqual(author_source_counts(frame), {
            "usable_full_names": 1,
            "used_abbreviated_names": 2,
            "unusable_rows": 0,
        })
        enriched, _, _ = add_internal_mncs(frame)
        author_stats, _, _, _, sources = author_analysis(enriched, top_n=10)
        self.assertEqual(set(author_stats["Author"]), {"Full, Person", "Fallback B", "Fallback C"})
        self.assertEqual(sources["used_abbreviated_names"], 2)

    def test_country_aliases_and_eu_filter_use_czechia(self):
        for spelling in ("Czech Republic", "Czech Rep.", "Czechia"):
            self.assertEqual(canonicalize_country_name(spelling), "Czechia")
        self.assertIn("Czechia", EU27_COUNTRIES)
        self.assertNotIn("Czech Republic", EU27_COUNTRIES)
        self.assertTrue(is_exclusively_eu(["Czech Republic", "Germany"]))

        resolved = resolve_entities(pd.DataFrame([{
            "Title": "Czech paper",
            "Affiliations": "Department of Physics, Charles University, Prague, Czech Republic",
        }]))
        article = resolved["article_summary"].iloc[0]
        self.assertEqual(article["Countries_Extracted"], ["Czechia"])
        prepared, _ = prepare_institutional_dataset(resolved["article_summary"])
        self.assertEqual(prepared.iloc[0]["Countries_Extracted"], ["Czechia"])
        self.assertTrue(is_exclusively_eu(prepared.iloc[0]["Countries_Extracted"]))

        handoff = pd.DataFrame({
            "Title": ["Canonical country handoff"],
            "Publication Year": [2020],
            "Cited by": [1],
            "Countries_Extracted": [["Czech Republic"]],
        })
        geographic = geographic_distribution_analysis(
            handoff, collaboration_top_n=1, impact_top_n=1, min_papers=1
        )
        self.assertEqual(
            geographic["data"].iloc[0]["Countries_Extracted_List"], ["Czechia"]
        )
        self.assertEqual(
            geographic["tables"]["country_collaboration_summary"].iloc[0]["Country"],
            "Czechia",
        )
        thematic, _ = prepare_thematic_dataset(handoff)
        self.assertEqual(thematic.iloc[0]["Countries_Extracted"], ["Czechia"])
        for figure in geographic["figures"].values():
            plt.close(figure)

    def test_dark_and_light_themes_use_distinct_readable_palettes(self):
        with patch("chronotome_ui.branding.st.markdown") as markdown:
            apply_brand_theme()
        css = markdown.call_args.args[0]
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("color-scheme: dark", css)
        self.assertIn("color-scheme: light", css)
        for color in ("#102720", "#23443C", "#17352F", "#F7F3E8", "#C6A04A"):
            self.assertIn(color, css)
        self.assertEqual(BRAND["green_dark"], "#102720")
        self.assertEqual(LIGHT["background"], "#F7F3E8")
        self.assertEqual(LIGHT["text"], "#263238")
        self.assertNotEqual(LIGHT["text"], BRAND["paper"])
        self.assertIn("--theme.base=dark", _DARK_THEME_ARGS)
        self.assertIn("--theme.backgroundColor=#102720", _DARK_THEME_ARGS)
        self.assertIn('[data-testid="stLinkButton"]', css)
        self.assertIn('[data-testid="stSelectbox"]', css)
        self.assertIn("-webkit-text-fill-color: var(--chronotome-text) !important", css)
        self.assertIn('[data-theme="light"] div[role="option"]', css)

        with (
            patch(
                "chronotome_ui.branding.st.context",
                SimpleNamespace(theme={"type": "light"}),
            ),
            patch("chronotome_ui.branding.st.markdown") as light_markdown,
        ):
            apply_brand_theme()
        light_css = light_markdown.call_args.args[0]
        root_block = light_css.split('[data-theme="dark"]', 1)[0]
        self.assertIn("color-scheme: light", root_block)
        self.assertIn("--chronotome-background: #F7F3E8", root_block)
        self.assertIn("--chronotome-text: #263238", root_block)


if __name__ == "__main__":
    unittest.main()
