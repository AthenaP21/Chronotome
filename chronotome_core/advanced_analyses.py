"""Final paper-ready summary and advanced evaluative bibliometrics."""

from __future__ import annotations

from datetime import datetime
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import seaborn as sns
except ImportError:
    sns = None

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

from .descriptive_bibliometrics import (
    calculate_local_h_index, configure_publication_style, normalize_doc_type,
    source_impact_analysis,
)
from .preprocessing import author_source_counts, select_author_text


def safe_author_split(value) -> list[str]:
    """Split the notebook's standardized semicolon-delimited author field."""
    if pd.isna(value):
        return []
    return [author.strip() for author in str(value).split(";") if author.strip()]


def _unique_terms(series: pd.Series) -> int:
    terms = series.dropna().astype(str).str.split(";").explode().str.strip()
    return int(terms[(terms != "") & (terms.str.lower() != "nan")].nunique())


def _author_impact(data: pd.DataFrame) -> tuple[pd.DataFrame, dict, list[str]]:
    warnings = []
    selected = select_author_text(data)
    source_counts = author_source_counts(data)
    if selected.dropna().empty:
        return pd.DataFrame(columns=["Author", "h_index", "Total_Citations", "Total_Papers"]), source_counts, [
            "No author field was available for author impact analysis."
        ]
    work = pd.DataFrame({"Selected Author Names": selected, "Cited by": data["Cited by"]})
    work = work.dropna(subset=["Selected Author Names"]).copy()
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce").fillna(0)
    work["Author"] = work["Selected Author Names"].apply(safe_author_split)
    exploded = work.explode("Author")
    exploded = exploded[exploded["Author"].astype(str).str.strip() != ""]
    stats = exploded.groupby("Author").agg(
        Total_Papers=("Author", "size"),
        Total_Citations=("Cited by", "sum"),
        h_index=("Cited by", calculate_local_h_index),
    ).reset_index()
    stats = stats.sort_values(
        ["h_index", "Total_Citations", "Total_Papers"], ascending=False
    ).reset_index(drop=True)
    stats.insert(0, "Rank", np.arange(1, len(stats) + 1))
    return stats, source_counts, warnings


def _final_summary(
    data: pd.DataFrame, source_stats: pd.DataFrame,
    author_stats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary: dict[str, object] = {"Total Documents": len(data)}
    current_year = datetime.now().year
    if "Publication Year" in data:
        years = pd.to_numeric(data["Publication Year"], errors="coerce").dropna().astype(int)
        if not years.empty:
            minimum, maximum = years.min(), years.max()
            summary["Timespan"] = f"{minimum} - {maximum}"
            summary["Average Document Age"] = (current_year - years).mean()
            span = maximum - minimum
            first_count, last_count = int((years == minimum).sum()), int((years == maximum).sum())
            summary["Annual Growth Rate %"] = (
                ((last_count / first_count) ** (1 / span) - 1) * 100
                if span > 0 and first_count > 0 else np.nan
            )
    if not source_stats.empty:
        summary["Journals/Sources"] = len(source_stats)
    elif "Source Title" in data:
        summary["Journals/Sources"] = data["Source Title"].nunique()
    if "Keywords Plus" in data:
        summary["Keywords Plus (ID)"] = _unique_terms(data["Keywords Plus"])
    if "Author Keywords" in data:
        summary["Author Keywords (DE)"] = _unique_terms(data["Author Keywords"])
    if "Cited Reference Count" in data:
        summary["Total References"] = pd.to_numeric(
            data["Cited Reference Count"], errors="coerce"
        ).fillna(0).sum()
    if "Cited by" in data:
        citations = pd.to_numeric(data["Cited by"], errors="coerce").fillna(0)
        summary["Average Citations per Doc"] = citations.mean()
        summary["Total Citations"] = citations.sum()
    if not author_stats.empty:
        summary["Authors"] = len(author_stats)
    selected_authors = select_author_text(data)
    if selected_authors.notna().any():
        author_counts = selected_authors.apply(safe_author_split).apply(len)
        author_counts = author_counts[author_counts > 0]
        summary["Co-Authors per Doc"] = author_counts.mean()
        summary["Single-authored Docs"] = int((author_counts == 1).sum())
    if "Country_Classification" in data:
        summary["International Collab %"] = (
            (data["Country_Classification"] == "MCP").sum() / max(1, len(data)) * 100
        )
    elif "Countries_Extracted" in data:
        def is_international(value):
            if isinstance(value, list):
                return len({country for country in value if country}) > 1
            try:
                cleaned = str(value).replace("[", "").replace("]", "").replace("'", "")
                return len({country.strip() for country in cleaned.split(",") if country.strip()}) > 1
            except Exception:
                return False
        summary["International Collab %"] = data["Countries_Extracted"].apply(is_international).mean() * 100

    def nice_format(value):
        if isinstance(value, (int, np.integer)):
            return f"{value:,}"
        if isinstance(value, (float, np.floating)):
            return "N/A" if np.isnan(value) else f"{value:,.2f}"
        return str(value)

    summary_table = pd.DataFrame(summary.items(), columns=["Description", "Value"])
    summary_table["Value"] = summary_table["Value"].apply(nice_format)
    if "Document Type" in data:
        raw_types = data["Document Type"].astype(str).str.lower().str.split(";").explode().str.strip()
        document_snapshot = raw_types.value_counts().head(5).rename_axis("Document Type").reset_index(name="Count")
        document_snapshot["Normalized Type"] = document_snapshot["Document Type"].apply(normalize_doc_type)
    else:
        document_snapshot = pd.DataFrame(columns=["Document Type", "Count", "Normalized Type"])
    return summary_table, document_snapshot


def _article_rankings(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "Title" not in data or "Cited by" not in data:
        return pd.DataFrame(), pd.DataFrame()
    work = data.copy()
    work["Selected Author Names"] = select_author_text(work)
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce").fillna(0)
    columns = [column for column in [
        "Title", "Authors", "Author Full Names", "Selected Author Names",
        "Publication Year", "Cited by", "DOI",
    ] if column in work]
    full = work[columns].sort_values("Cited by", ascending=False).reset_index(drop=True)
    full.insert(0, "Rank", np.arange(1, len(full) + 1))
    top = full.head(10).copy()
    top["First_Author"] = top["Selected Author Names"].apply(
        lambda value: safe_author_split(value)[0] if safe_author_split(value) else "N/A"
    )
    top["Short_Title"] = top["Title"].apply(
        lambda value: str(value)[:70] + "..." if len(str(value)) > 70 else str(value)
    )
    display_columns = [column for column in ["Rank", "Short_Title", "First_Author", "Publication Year", "Cited by"] if column in top]
    return full, top[display_columns]


def _bradford_analysis(source_stats: pd.DataFrame):
    if source_stats.empty:
        return pd.DataFrame(), pd.DataFrame(), None, ["Insufficient source data for Bradford's Law."]
    bradford = source_stats[["OriginalTitle", "Number_of_Publications"]].copy()
    bradford = bradford.rename(columns={"Number_of_Publications": "Count"})
    bradford = bradford.sort_values("Count", ascending=False).reset_index(drop=True)
    bradford["Rank"] = bradford.index + 1
    bradford["Cumulative_Articles"] = bradford["Count"].cumsum()
    bradford["Log_Rank"] = np.log(bradford["Rank"])
    total_articles = int(bradford["Cumulative_Articles"].max())
    first_threshold, second_threshold = total_articles / 3, total_articles * 2 / 3
    bradford["Bradford Zone"] = np.select(
        [
            bradford["Cumulative_Articles"] <= first_threshold,
            bradford["Cumulative_Articles"] <= second_threshold,
        ], ["Zone 1 (Core)", "Zone 2"], default="Zone 3 (Periphery)",
    )
    zone_order = ["Zone 1 (Core)", "Zone 2", "Zone 3 (Periphery)"]
    zone_summary = bradford.groupby("Bradford Zone").agg(
        Sources=("OriginalTitle", "size"), Articles=("Count", "sum")
    ).reindex(zone_order, fill_value=0).reset_index()
    n1, n2, n3 = zone_summary["Sources"].tolist()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(bradford["Rank"], bradford["Cumulative_Articles"], color="#333333", linewidth=2,
            label="Source Distribution")
    ax.set_xscale("log")
    ax.axhline(first_threshold, color="#666666", linestyle="--", linewidth=1, alpha=0.8)
    ax.axhline(second_threshold, color="#666666", linestyle="--", linewidth=1, alpha=0.8)
    if n1 > 0:
        ax.axvline(n1, color="#666666", linestyle="--", linewidth=1, alpha=0.8)
    if n1 + n2 > 0:
        ax.axvline(n1 + n2, color="#666666", linestyle="--", linewidth=1, alpha=0.8)
    ax.text(1.1, first_threshold / 2, f"Zone 1 (Core)\n{n1} Sources", color="black",
            fontsize=10, fontweight="bold", va="center")
    middle_rank = n1 + n2 / 2 if n2 > 0 else max(1, n1)
    ax.text(max(1, middle_rank), (first_threshold + second_threshold) / 2,
            f"Zone 2\n{n2} Sources", color="black", fontsize=10, fontweight="bold",
            ha="center", va="center")
    peripheral_rank = max(1, (n1 + n2) * 1.5)
    ax.text(peripheral_rank, (second_threshold + total_articles) / 2,
            f"Zone 3 (Periphery)\n{n3} Sources", color="black", fontsize=10,
            fontweight="bold", va="center")
    ax.set_title(
        "Bradford's Law of Scattering: Source Concentration\n"
        f"(Total $N={len(bradford)}$ Sources, $N={total_articles}$ Articles)",
        fontsize=14, fontweight="bold", pad=15,
    )
    ax.set_xlabel("Source Rank (Log Scale)", fontsize=12)
    ax.set_ylabel("Cumulative Number of Articles", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle=":", alpha=0.4, which="both")
    fig.tight_layout()
    return bradford, zone_summary, fig, []


def _hot_papers(data: pd.DataFrame):
    recent_year = datetime.now().year - 3
    if not {"Publication Year", "Cited by", "Title"}.issubset(data.columns):
        return pd.DataFrame(), pd.DataFrame(), recent_year, ["Required hot-paper columns were unavailable."]
    work = data.copy()
    work["Selected Author Names"] = select_author_text(work)
    work["Publication Year"] = pd.to_numeric(work["Publication Year"], errors="coerce")
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce").fillna(0)
    recent = work[work["Publication Year"] >= recent_year].sort_values("Cited by", ascending=False).copy()
    if recent.empty:
        return recent, recent, recent_year, [f"No articles were published since {recent_year}."]
    recent["First Author"] = recent["Selected Author Names"].apply(
        lambda value: safe_author_split(value)[0] if safe_author_split(value) else "N/A"
    )
    recent["Title (Short)"] = recent["Title"].apply(
        lambda value: str(value)[:70] + "..." if len(str(value)) > 70 else str(value)
    )
    recent["Rank"] = np.arange(1, len(recent) + 1)
    source_column = "OriginalTitle" if "OriginalTitle" in recent else "Source Title"
    display = ["Rank", "Title (Short)", "First Author"]
    if source_column in recent:
        display.append(source_column)
    display.extend(["Publication Year", "Cited by"])
    return recent, recent[display].head(10), recent_year, []


def _team_science(data: pd.DataFrame):
    if "Cited by" not in data:
        return pd.DataFrame(), None, ["Cited by was unavailable for team-size analysis."]
    work = data.copy()
    work["Selected Author Names"] = select_author_text(work)
    if work["Selected Author Names"].dropna().empty:
        return pd.DataFrame(), None, ["No author names were available for team-size analysis."]
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce").fillna(0)
    work["Author_Count"] = work["Selected Author Names"].apply(safe_author_split).apply(len)
    work = work[work["Author_Count"] > 0].copy()
    work["Team_Size_Category"] = work["Author_Count"].apply(lambda count: str(count) if count < 6 else "6+")
    category_order = ["1", "2", "3", "4", "5", "6+"]
    summary = work.groupby("Team_Size_Category")["Cited by"].agg(
        Average_Citations="mean", Number_of_Articles="count"
    ).reindex(category_order).reset_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    if sns is not None:
        sns.barplot(
            data=summary, x="Team_Size_Category", y="Average_Citations",
            hue="Team_Size_Category", palette="cividis", legend=False,
            edgecolor="black", linewidth=0.5, ax=ax,
        )
    else:
        colors = plt.cm.cividis(np.linspace(0, 1, len(summary)))
        ax.bar(summary["Team_Size_Category"], summary["Average_Citations"],
               color=colors, edgecolor="black", linewidth=0.5)
    ax.set_title(
        f"Impact of Team Size on Citation Performance\n(Analysis of $N={len(work)}$ Articles)",
        fontsize=14, fontweight="bold", pad=15,
    )
    ax.set_xlabel("Number of Authors per Article", fontsize=11)
    ax.set_ylabel("Average Citations per Article", fontsize=11)
    for patch in ax.patches:
        height = patch.get_height()
        if pd.notna(height):
            ax.annotate(
                f"{height:.1f}", (patch.get_x() + patch.get_width() / 2, height),
                ha="center", va="bottom", fontsize=10, fontweight="bold", color="#333333",
                xytext=(0, 3), textcoords="offset points",
            )
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return summary, fig, []


def _journal_landscape(source_stats: pd.DataFrame):
    if source_stats.empty:
        return pd.DataFrame(), None, ["Source metrics were unavailable for the journal landscape."]
    plot_data = source_stats[source_stats["Number_of_Publications"] > 0].copy()
    plot_data["Avg_Citations"] = (
        plot_data["Total_Citations"] / plot_data["Number_of_Publications"]
    )
    if plot_data.empty or not (plot_data["Avg_Citations"] > 0).any():
        return plot_data, None, ["Positive source citation averages are required for the log-scale landscape."]
    fig, ax = plt.subplots(figsize=(12, 8))
    scatter = ax.scatter(
        plot_data["Number_of_Publications"], plot_data["Avg_Citations"],
        s=plot_data["h_index"] * 10, c=plot_data["h_index"], cmap="cividis",
        alpha=0.7, edgecolors="white", linewidth=0.5,
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title(
        "Bibliometric Landscape: Source Productivity vs. Impact Efficiency\n"
        f"($N={len(plot_data)}$ Sources)", fontsize=14, fontweight="bold", pad=20,
    )
    ax.set_xlabel("Productivity (Total Publications) [Log Scale]", fontsize=11)
    ax.set_ylabel("Impact (Avg Citations per Paper) [Log Scale]", fontsize=11)
    texts = []
    for row in plot_data.nlargest(10, "h_index").itertuples():
        texts.append(ax.text(
            row.Number_of_Publications, row.Avg_Citations,
            textwrap.fill(row.OriginalTitle, 20), fontsize=8, fontweight="medium",
        ))
    if adjust_text is not None and texts:
        try:
            adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))
        except Exception:
            pass
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("Local H-Index (Accumulated Prestige)", rotation=270, labelpad=15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.3, which="both")
    fig.tight_layout()
    return plot_data, fig, []


def run_advanced_bibliometric_analysis(data: pd.DataFrame, analyses=None) -> dict:
    """Run only the requested final-summary or advanced-analysis components."""
    if data is None or data.empty:
        raise ValueError("The advanced-analysis dataset is empty.")
    available = {"summary", "articles", "authors", "bradford", "hot", "team", "landscape"}
    selected = set(analyses or available)
    unknown = selected - available
    if unknown:
        raise ValueError("Unknown advanced analyses: " + ", ".join(sorted(unknown)))
    configure_publication_style()
    enriched = data.copy()
    if "Cited by" not in enriched:
        enriched["Cited by"] = 0
    enriched["Cited by"] = pd.to_numeric(enriched["Cited by"], errors="coerce").fillna(0)
    tables: dict[str, pd.DataFrame] = {}
    figures: dict = {}
    warnings: list[str] = []
    author_sources: dict = {}
    recent_year = datetime.now().year - 3

    source_stats = pd.DataFrame()
    if selected & {"summary", "bradford", "hot", "landscape"}:
        enriched, source_tables, source_figures, source_warnings = source_impact_analysis(enriched)
        for figure in source_figures.values():
            plt.close(figure)
        source_stats = source_tables.get("all_sources_ranked", pd.DataFrame())
        warnings.extend(source_warnings)

    author_stats = pd.DataFrame()
    if selected & {"summary", "authors"}:
        author_stats, author_sources, author_warnings = _author_impact(enriched)
        warnings.extend(author_warnings)
        tables["author_name_source_audit"] = pd.DataFrame(
            author_sources.items(), columns=["Author-name source", "Papers"]
        )

    if "summary" in selected:
        final_summary, document_snapshot = _final_summary(
            enriched, source_stats, author_stats
        )
        tables.update({
            "final_main_summary": final_summary,
            "document_type_snapshot": document_snapshot,
        })
    if "articles" in selected:
        all_articles, top_articles = _article_rankings(enriched)
        tables.update({
            "all_articles_ranked_by_citations": all_articles,
            "top_10_most_cited_articles": top_articles,
        })
    if "authors" in selected:
        tables.update({
            "all_authors_ranked_by_impact": author_stats,
            "top_10_authors_by_impact": author_stats.head(10),
        })
    if "bradford" in selected:
        bradford, zones, figure, component_warnings = _bradford_analysis(source_stats)
        tables.update({"bradford_law_data": bradford, "bradford_zone_summary": zones})
        if figure is not None:
            figures["bradford_law_scattering"] = figure
        warnings.extend(component_warnings)
    if "hot" in selected:
        hot_full, hot_top, recent_year, component_warnings = _hot_papers(enriched)
        tables.update({
            "emerging_research_fronts_hot_papers": hot_full,
            "top_10_hot_papers": hot_top,
        })
        warnings.extend(component_warnings)
    if "team" in selected:
        team_table, figure, component_warnings = _team_science(enriched)
        tables["collaboration_impact_team_size"] = team_table
        if figure is not None:
            figures["collaboration_impact_team_size"] = figure
        warnings.extend(component_warnings)
    if "landscape" in selected:
        landscape_table, figure, component_warnings = _journal_landscape(source_stats)
        tables.update({
            "journal_landscape_data": landscape_table,
            "source_metrics_for_advanced_analysis": source_stats,
        })
        if figure is not None:
            figures["journal_landscape_cividis"] = figure
        warnings.extend(component_warnings)
    return {
        "data": enriched, "tables": tables, "figures": figures,
        "warnings": list(dict.fromkeys(warnings)), "author_source_counts": author_sources,
        "recent_year": recent_year, "analyses": sorted(selected),
    }
