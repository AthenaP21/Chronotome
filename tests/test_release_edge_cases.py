"""Focused regressions for release-critical missing-value edge cases."""

from __future__ import annotations

import unittest

import matplotlib.pyplot as plt
import pandas as pd

from chronotome_core.descriptive_bibliometrics import (
    add_internal_mncs,
    author_analysis,
    source_impact_analysis,
)
from chronotome_core.runner import run_corpus_bibliometrics
from chronotome_core.preprocessing import deduplicate, harmonize


class MissingValueEdgeCaseTests(unittest.TestCase):
    def test_processed_doi_replaces_recognized_missing_tokens(self):
        source = pd.DataFrame(
            [
                {"Title": "Missing token A", "Year": 2020, "Cited by": 0, "DOI": "NA"},
                {"Title": "Missing token B", "Year": 2020, "Cited by": 0, "DOI": "none"},
                {"Title": "Blank token", "Year": 2020, "Cited by": 0, "DOI": ""},
            ]
        )
        merged, audit, _, _ = harmonize({"Scopus": source}, include_audit=True)
        processed, _ = deduplicate(merged, audit)

        self.assertTrue(processed["DOI"].isna().all())
        self.assertEqual(len(processed), 3)

    def test_undefined_mncs_is_preserved_but_impact_figures_are_omitted(self):
        source = pd.DataFrame(
            {
                "Author Full Names": ["Alpha, A", "Beta, B"],
                "Authors": ["A A", "B B"],
                "Cited by": [0, 0],
                "Publication Year": [2020, 2020],
                "Source Title": ["Zero Citation Journal", "Zero Citation Journal"],
            }
        )
        enriched, _, _ = add_internal_mncs(source)
        self.assertTrue(enriched["MNCS"].isna().all())

        authors, productivity_figure, impact_figure, author_warnings, _ = author_analysis(
            enriched, top_n=10
        )
        self.assertTrue(authors["Avg_MNCS"].isna().all())
        self.assertIsNotNone(productivity_figure)
        self.assertIsNone(impact_figure)
        self.assertIn("defined MNCS", " ".join(author_warnings))

        _, tables, figures, source_warnings = source_impact_analysis(
            enriched, min_papers=1
        )
        self.assertTrue(tables["all_sources_ranked"]["Avg_MNCS"].isna().all())
        self.assertTrue(tables["top_sources_by_mncs"].empty)
        self.assertNotIn("top_10_journals_impact_analysis", figures)
        self.assertIn("defined MNCS", " ".join(source_warnings))

        for figure in [productivity_figure, *figures.values()]:
            plt.close(figure)

    def test_all_missing_citations_do_not_reach_matplotlib_as_pd_na(self):
        source = pd.DataFrame(
            {
                "Title": ["Missing citations A", "Missing citations B"],
                "Publication Year": pd.Series([2020, 2021], dtype="Int64"),
                "Cited by": pd.Series([pd.NA, pd.NA], dtype="Float64"),
                "Cited Reference Count": pd.Series([pd.NA, pd.NA], dtype="Int64"),
                "Source Title": ["Journal A", "Journal A"],
                "Author Full Names": ["Alpha, A", "Beta, B"],
                "Authors": ["A A", "B B"],
                "Document Type": ["Article", "Article"],
            }
        )

        result = run_corpus_bibliometrics(
            source, cutoff_year=2026, min_source_papers=1,
            include_archive=False,
        )

        self.assertTrue(result["data"]["MNCS"].isna().all())
        self.assertNotIn("citation_dynamics_dual_axis", result["figures"])
        self.assertIn(
            "Citation values are missing for every publication year",
            " ".join(result["warnings"]),
        )
        self.assertIn(
            "Results/bibliometric_dataset_with_mncs.xlsx", result["exports"]
        )


if __name__ == "__main__":
    unittest.main()
