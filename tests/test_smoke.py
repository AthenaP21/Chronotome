"""Small end-to-end regression tests for the converted notebook workflow."""

import io
import json
import unittest

import pandas as pd
from matplotlib.colors import to_hex
import matplotlib.pyplot as plt

from chronotome_core import (
    run_advanced_analyses, run_advanced_thematic_analysis, run_chronotome, run_corpus_bibliometrics,
    run_country_case_study, run_entity_resolution,
    run_final_topic_models, run_geographic_bibliometrics, run_ingestion,
    run_thematic_preprocessing, run_topic_model_evaluation,
)
from chronotome_core.entity_resolution import validate_institution_alias_json
from chronotome_core.io import InputError, inspect_source_uploads
from chronotome_core.preprocessing import (
    clean_scopus_authors, clean_wos_authors, remove_id_codes_from_full_names,
    scopus_cited_reference_count, wos_cited_reference_count,
)


class Upload(io.BytesIO):
    def __init__(self, frame, name):
        super().__init__(frame.to_csv(index=False).encode())
        self.name = name


class JsonUpload(io.BytesIO):
    def __init__(self, data, name="institutions.json"):
        super().__init__(json.dumps(data).encode())
        self.name = name


class ChronotomeSmokeTest(unittest.TestCase):
    def test_empty_search_string_preserves_ai_and_ml_bigrams(self):
        data = pd.DataFrame({
            "Title": ["Artificial intelligence and machine learning"] * 3,
            "Abstract": [""] * 3,
        })
        result = run_thematic_preprocessing(
            data, "", {"Custom": set()}, set(), min_df=1, max_df=1.0,
        )
        bigrams = set(result["tables"]["bigram_frequency"]["ngram"])
        self.assertIn("artificial intelligence", bigrams)
        self.assertIn("machine learning", bigrams)

    def test_staged_thematic_analysis_and_vector_exports(self):
        themes = [
            ("atmosphere spectrum telescope", "transit stellar orbit"),
            ("neural classification algorithm", "learning signal feature"),
            ("formation disk migration", "dynamics simulation mass"),
        ]
        rows = []
        for index in range(18):
            title, abstract = themes[index % len(themes)]
            rows.append({
                "Title": title, "Abstract": abstract, "Author Keywords": title,
                "Keywords Plus": abstract, "Publication Year": 2015 + index % 6,
                "Cited by": index + 1, "Authors": f"Author {index}; Collaborator",
                "Countries_Extracted": ["Germany"] if index % 2 else ["Germany", "France"],
            })
        preprocessing = run_thematic_preprocessing(
            pd.DataFrame(rows), "planet AND climate", {"Custom": {"study"}}, set(), min_df=2,
        )
        self.assertIn("Processed_Text", preprocessing["data"])
        self.assertFalse(preprocessing["tables"]["unigram_frequency"].empty)
        evaluation = run_topic_model_evaluation(preprocessing["data"], [2, 3], min_df=2)
        self.assertIn(evaluation["best_k"], (2, 3))
        self.assertIn("Plots/LDA_Evaluation_Metrics.svg", evaluation["exports"])
        final = run_final_topic_models(
            preprocessing["data"], evaluation["best_k"], evaluation["best_nmf_k"], bin_duration=2,
        )
        self.assertIn("Dominant_Topic", final["data"])
        self.assertIn("Plots/Topic_Evolution_Proportion.svg", final["exports"])
        self.assertIn("chronotome_final_topic_models_outputs.zip", final["exports"])
        advanced = run_advanced_thematic_analysis(
            final["data"], cooccurrence_threshold=0.1, min_country_documents=2,
        )
        self.assertIn("topic_citation_impact_mncs", advanced["tables"])
        self.assertIn("most_cited_article_per_topic", advanced["tables"])
        self.assertIn("Plots/topic_cooccurrence_heatmap.svg", advanced["exports"])

    def test_final_summary_and_advanced_analysis_exports(self):
        country_sets = [["Germany"], ["France"], ["Germany", "France"]]
        rows = []
        for index in range(30):
            countries = country_sets[index % len(country_sets)]
            rows.append({
                "Title": f"Advanced paper {index}",
                "Authors": f"Doe J.; Author {index % 7}",
                "Author Full Names": f"Doe, Jane; Author, {index % 7}",
                "Publication Year": 2018 + index % 6,
                "Cited by": index + 1,
                "Source Title": f"Journal {index % 4}",
                "DOI": f"10.1/advanced-{index}",
                "Document Type": "Review" if index % 4 == 0 else "Article",
                "Author Keywords": "bibliometrics; collaboration",
                "Keywords Plus": "science; impact",
                "Cited Reference Count": 10 + index,
                "Countries_Extracted": countries,
                "Country_Classification": "MCP" if len(countries) > 1 else "SCP",
                "MNCS": 1 + index / 100,
            })
        result = run_advanced_analyses(pd.DataFrame(rows))
        summary = result["tables"]["final_main_summary"].set_index("Description")["Value"]
        self.assertEqual(summary.loc["Total Documents"], "30")
        self.assertEqual(summary.loc["Journals/Sources"], "4")
        self.assertEqual(summary.loc["Authors"], "8")
        self.assertIn("all_articles_ranked_by_citations", result["tables"])
        self.assertIn("all_authors_ranked_by_impact", result["tables"])
        self.assertEqual(
            tuple(result["figures"]["bradford_law_scattering"].get_size_inches()), (10.0, 6.0)
        )
        self.assertEqual(
            result["figures"]["bradford_law_scattering"].axes[0].lines[0].get_color(), "#333333"
        )
        self.assertEqual(
            tuple(result["figures"]["collaboration_impact_team_size"].get_size_inches()), (10.0, 6.0)
        )
        self.assertEqual(
            tuple(result["figures"]["journal_landscape_cividis"].get_size_inches()), (12.0, 8.0)
        )
        self.assertIn("Results/final_main_summary.csv", result["exports"])
        self.assertIn("Results/advanced_bibliometric_tables.xlsx", result["exports"])
        self.assertIn("Plots/bradford_law_scattering.png", result["exports"])
        self.assertIn("Plots/bradford_law_scattering.svg", result["exports"])
        self.assertIn("Plots/journal_landscape_cividis.pdf", result["exports"])
        self.assertIn("chronotome_advanced_analyses_outputs.zip", result["exports"])

        team_only = run_advanced_analyses(pd.DataFrame(rows), analyses=["team"])
        self.assertEqual(team_only["analyses"], ["team"])
        self.assertEqual(set(team_only["tables"]), {"collaboration_impact_team_size"})
        self.assertEqual(set(team_only["figures"]), {"collaboration_impact_team_size"})
        self.assertNotIn("Results/final_main_summary.csv", team_only["exports"])

    def test_notebook_faithful_geographic_distribution(self):
        rows = []
        country_sets = [
            ["Germany"], ["France"], ["Germany", "France"],
            ["United States", "Germany"], ["Romania"], ["Romania", "France"],
        ]
        for index in range(24):
            rows.append({
                "Title": f"Country paper {index}",
                "Publication Year": 2019 + index % 4,
                "Cited by": index + 1,
                "Countries_Extracted": country_sets[index % len(country_sets)],
            })
        rows.append({
            "Title": "Unknown geography", "Publication Year": 2022,
            "Cited by": 0, "Countries_Extracted": [],
        })
        result = run_geographic_bibliometrics(
            pd.DataFrame(rows), collaboration_top_n=10, impact_top_n=15,
            min_papers=2, exclude_unknown=True,
        )
        self.assertEqual(result["metadata"]["unknown_articles"], 1)
        self.assertEqual(result["metadata"]["scp_articles"], 12)
        self.assertEqual(result["metadata"]["mcp_articles"], 12)
        germany = result["tables"]["country_collaboration_summary"].set_index("Country").loc["Germany"]
        self.assertEqual(int(germany["Articles"]), 12)
        self.assertEqual(int(germany["SCP"]), 4)
        self.assertEqual(int(germany["MCP"]), 8)

        collaboration_figure = result["figures"]["top_10_countries_collaboration"]
        self.assertEqual(tuple(collaboration_figure.get_size_inches()), (12.0, 8.0))
        self.assertEqual(
            to_hex(collaboration_figure.axes[0].patches[0].get_facecolor()),
            to_hex(plt.cm.cividis(0.95)),
        )
        impact_figure = result["figures"]["country_impact_comparison"]
        self.assertEqual(tuple(impact_figure.get_size_inches()), (16.0, 8.0))
        self.assertEqual(to_hex(impact_figure.axes[0].patches[0].get_facecolor()), "#555555")
        citation_figure = result["figures"]["Country_Citation_Impact_Distribution"]
        self.assertEqual(tuple(citation_figure.get_size_inches()), (10.5, 6.5))
        matrix_figure = result["figures"]["Scientometric_Performance_Matrix_Productivity_vs_Impact"]
        self.assertEqual(tuple(matrix_figure.get_size_inches()), (12.0, 9.0))
        network_figure = result["figures"]["International_Collaboration_Network_Topology"]
        self.assertEqual(tuple(network_figure.get_size_inches()), (18.0, 11.0))
        self.assertGreater(result["network"].number_of_edges(), 0)
        self.assertIn("international_collaboration_nodes", result["tables"])
        self.assertIn("international_collaboration_edges", result["tables"])
        self.assertIn("Results/country_collaboration_summary.csv", result["exports"])
        self.assertIn("Results/country_master_stats.csv", result["exports"])
        self.assertIn("Plots/top_10_countries_collaboration.png", result["exports"])
        self.assertIn("Plots/country_impact_comparison.pdf", result["exports"])
        self.assertIn("Plots/Country_Citation_Impact_Distribution.png", result["exports"])
        self.assertIn("Plots/Country_Citation_Impact_Distribution.svg", result["exports"])
        self.assertIn("Plots/Scientometric_Performance_Matrix_Productivity_vs_Impact.pdf", result["exports"])
        self.assertIn("Plots/International_Collaboration_Network_Topology.png", result["exports"])
        self.assertIn("chronotome_geographic_distribution_outputs.zip", result["exports"])

        affiliations = pd.DataFrame([
            {"Country_Standardized": "Germany", "Institution_Extracted": "Institute A"},
            {"Country_Standardized": "Germany", "Institution_Extracted": "Institute A"},
            {"Country_Standardized": "Germany", "Institution_Extracted": "Institute B"},
        ])
        case = run_country_case_study(
            result["data"], result["exploded_countries"],
            result["tables"]["country_master_stats"], "Germany", affiliations,
        )
        self.assertEqual(case["country"], "Germany")
        self.assertEqual(tuple(case["figure"].get_size_inches()), (20.0, 16.0))
        self.assertEqual(case["tables"]["top_institutions"].iloc[0]["Institution"], "Institute A")
        self.assertIn("country_rank_evolution", case["tables"])
        self.assertIn("Plots/Germany_Deep_Dive_Analysis.png", case["exports"])
        self.assertIn("Plots/Germany_Deep_Dive_Analysis.svg", case["exports"])
        self.assertIn("Plots/Germany_Deep_Dive_Analysis.pdf", case["exports"])
        self.assertIn("Results/Germany_Country_Case_Study.xlsx", case["exports"])
        self.assertIn("Germany_Chronotome_Case_Study.zip", case["exports"])

    def test_notebook_faithful_corpus_figures_and_exports(self):
        rows = []
        for index in range(18):
            rows.append({
                "Title": f"Paper {index}", "Publication Year": 2018 + index % 6,
                "Cited by": index + 1, "Cited Reference Count": 10 + index,
                "Source Title": f"Journal {index % 3}",
                "Document Type": "Article; Proceedings Paper" if index % 4 == 0 else "Article",
                "Authors": f"Doe J.; Smith A.; Author {index}",
                "Author Full Names": f"Doe, Jane; Smith, Alex; Author, {index}",
            })
        result = run_corpus_bibliometrics(pd.DataFrame(rows), cutoff_year=2026, top_n=10)
        self.assertIn("MNCS", result["data"])
        yearly_mncs = result["data"].groupby("Publication Year")["MNCS"].mean()
        self.assertTrue(((yearly_mncs - 1).abs() < 1e-10).all())

        document_figure = result["figures"]["document_types"]
        self.assertEqual(tuple(document_figure.get_size_inches()), (10.0, 6.0))
        self.assertEqual(to_hex(document_figure.axes[0].patches[0].get_facecolor()), "#333333")
        annual_figure = result["figures"]["annual_scientific_production"]
        self.assertEqual(tuple(annual_figure.get_size_inches()), (12.0, 6.0))
        self.assertEqual(annual_figure.axes[0].lines[0].get_color(), "#555555")
        citation_figure = result["figures"]["citation_dynamics_dual_axis"]
        self.assertEqual(tuple(citation_figure.get_size_inches()), (12.0, 7.0))
        source_figure = result["figures"]["composite_top_sources_descriptive"]
        self.assertEqual(tuple(source_figure.get_size_inches()), (20.0, 12.0))
        self.assertEqual(to_hex(source_figure.axes[0].patches[0].get_facecolor()), "#333333")
        source_impact_figure = result["figures"]["top_10_journals_impact_analysis"]
        self.assertEqual(tuple(source_impact_figure.get_size_inches()), (16.0, 6.0))
        self.assertIn("all_sources_ranked", result["tables"])

        self.assertIn("Plots/annual_scientific_production.png", result["exports"])
        self.assertIn("Plots/annual_scientific_production.svg", result["exports"])
        self.assertIn("Plots/annual_scientific_production.pdf", result["exports"])
        self.assertIn("Plots/composite_top_sources_descriptive.png", result["exports"])
        self.assertIn("Plots/top_10_journals_impact_analysis.pdf", result["exports"])
        self.assertIn("Results/all_sources_ranked.csv", result["exports"])
        self.assertIn("Results/descriptive_bibliometrics_tables.xlsx", result["exports"])
        self.assertIn("chronotome_corpus_bibliometrics_outputs.zip", result["exports"])

    def test_custom_institution_alias_map_and_entity_outputs(self):
        data = pd.DataFrame([
            {
                "Title": "Paper A", "Publication Year": 2022, "DOI": "10.1/a",
                "Affiliations": (
                    "California Inst. of Tech. (Caltech), Pasadena, United States of America; "
                    "Max Planck Inst for Solar System Research, Göttingen, Germany"
                ),
            },
            {
                "Title": "Paper B", "Publication Year": 2023, "DOI": "10.1/b",
                "Affiliations": "CNRS; Univ Paris Saclay, Orsay, FRANCE",
            },
        ])
        custom = JsonUpload({
            "Caltech Updated": ["california institute technology", "caltech"],
            "Max Planck Institute": ["max planck institute"],
            "CNRS": ["cnrs"],
            "University Paris Saclay": ["university paris saclay"],
        })
        result = run_entity_resolution(data, custom)
        institutions = {item for values in result["article_summary"]["Institutions_Extracted"] for item in values}
        self.assertIn("Caltech Updated", institutions)
        self.assertIn("Max Planck Institute", institutions)
        self.assertEqual(result["article_summary"].iloc[0]["Collaboration_Type"], "International")
        self.assertIn("exploded_affiliations_list.xlsx", result["exports"])
        self.assertIn("final_article_summary_with_countries.csv", result["exports"])
        self.assertIn("active_institutions.json", result["exports"])

    def test_alias_collision_is_reported(self):
        alias_info = validate_institution_alias_json(JsonUpload({
            "Institution A": ["shared alias"], "Institution B": ["shared alias"],
        }))
        self.assertEqual(len(alias_info["collisions"]), 1)

    def test_notebook_preprocessing_rules(self):
        self.assertEqual(clean_scopus_authors("Doe J.;  Smith A. ;"), "Doe J.; Smith A.")
        self.assertEqual(clean_wos_authors("DOE J, SMITH A"), "DOE J; SMITH A")
        self.assertEqual(remove_id_codes_from_full_names("Smith, John(57211158827)"), "Smith, John")
        self.assertEqual(scopus_cited_reference_count("One; Two; Three"), 3)
        self.assertEqual(wos_cited_reference_count("One; Two"), 2)

    @staticmethod
    def small_scopus(start=0, count=3):
        return pd.DataFrame([{
            "Authors": "Doe J.; Smith A.", "Title": f"Study {index}", "Source title": "Journal",
            "Year": 2022, "Cited by": index, "DOI": f"10.1/{index}",
            "Affiliations": "Department, Example University, Berlin, Germany",
        } for index in range(start, start + count)])

    def test_appendage_verification_and_ingestion(self):
        part_two = Upload(self.small_scopus(3), "scopus_query_2.csv")
        part_one = Upload(self.small_scopus(0), "scopus_query_1.csv")
        verification = inspect_source_uploads([part_two, part_one], "Scopus", "appendage")
        self.assertEqual([item.part_number for item in verification["loaded"]], [1, 2])
        result = run_ingestion(
            scopus_files=[part_two, part_one], modes={"Scopus": "appendage"},
            config={"enable_time_filter": False},
        )
        self.assertEqual(len(result["processed_data"]), 6)
        self.assertIn("merged_bibliometric_dataset.xlsx", result["exports"])
        self.assertIn("stitched_scopus_export.csv", result["exports"])
        self.assertIn("preprocessing_source_audit.csv", result["exports"])
        self.assertIn("prisma_text_report.txt", result["exports"])
        self.assertNotIn("prisma_flow.png", result["exports"])
        self.assertFalse(result["preprocessing_audit"]["schema_mapping"].empty)

    def test_appendage_rejects_mixed_series(self):
        with self.assertRaises(InputError):
            inspect_source_uploads(
                [Upload(self.small_scopus(), "query_a_1.csv"), Upload(self.small_scopus(), "query_b_2.csv")],
                "Scopus", "appendage",
            )

    def test_merged_scopus_wos_workflow(self):
        countries = ["Germany", "France", "United States", "Romania"]
        rows = []
        for index in range(18):
            first, second = countries[index % 4], countries[(index + 1) % 4]
            rows.append({
                "Authors": f"Doe J.; Smith A.; Author {index}",
                "Author full names": f"Doe, Jane(123); Smith, Alex(456); Author, {index}",
                "Title": f"Planetary motion climate dynamics study {index % 6}",
                "Source title": f"Journal {index % 3}", "Year": 2018 + index % 6,
                "Cited by": index * 2, "DOI": "10.1/shared" if index in (0, 1) else f"10.1/{index}",
                "Abstract": f"planetary science orbit climate temporal analysis method result {index % 4}",
                "Author Keywords": "planetary science; orbital dynamics; climate",
                "Index Keywords": "bibliometrics; network analysis", "Document Type": "Article",
                "Affiliations": f"Department, University of Example {index % 5}, City, {first}; Institute of Space Science, City, {second}",
                "References": "Ref A; Ref B; Ref C",
            })
        scopus = pd.DataFrame(rows)
        wos = pd.DataFrame([{
            "Authors": "DOE J; OTHER B", "Article Title": "Planetary motion climate dynamics study extra",
            "Source Title": "Journal 2", "Publication Year": 2020, "Times Cited, WoS Core": 12,
            "DOI": "10.1/wos", "Abstract": "planetary science orbit climate temporal analysis method",
            "Author Keywords": "planetary science; climate", "Keywords Plus": "network analysis",
            "Document Type": "Article",
            "Addresses": "Lab, University of Example 2, Berlin, Germany; Center, CNRS, Paris, France",
            "CR": "Ref A; Ref B",
        }])
        result = run_chronotome(
            [Upload(scopus, "scopus.csv"), Upload(wos, "wos.csv")],
            {"enable_time_filter": False, "run_thematic": True, "topic_count": 4},
        )
        self.assertEqual(len(result["processed_data"]), 18)
        self.assertGreater(len(result["tables"]), 30)
        self.assertGreater(len(result["figures"]), 5)
        self.assertIn("topics", result["tables"])
        self.assertTrue(result["exports"]["chronotome_outputs.zip"])


if __name__ == "__main__":
    unittest.main()
