"""Notebook-faithful descriptive and evaluative bibliometric analyses."""

from __future__ import annotations

from datetime import datetime
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from scipy import stats
from cycler import cycler


DOC_TYPE_MAP = {
    "article": "Article", "journal article": "Article",
    "review": "Review", "review article": "Review", "survey": "Review",
    "conference paper": "Conference", "proceeding paper": "Conference",
    "conference proceeding": "Conference", "book chapter": "Book Chapter", "book": "Book",
    "editorial": "Other", "editorial material": "Other", "letter": "Other", "note": "Other",
    "short survey": "Other", "erratum": "Other", "correction": "Other", "retraction": "Other",
    "data paper": "Other", "missing/incomplete data": "Other",
}

PROTECTED_ACRONYMS = {"ieee", "acm", "spie", "nasa", "mnras", "pasp", "aaas", "plos"}
LOWERCASE_WORDS = {"a", "an", "the", "and", "or", "but", "for", "nor", "on", "at", "to", "from", "by", "of", "in"}


def configure_publication_style():
    """Apply the notebook's publication-ready Cividis defaults."""
    plt.style.use("seaborn-v0_8-whitegrid")
    cividis_colors = plt.cm.cividis(np.linspace(0, 0.9, 5))
    plt.rcParams.update({
        "figure.figsize": (10, 6), "figure.dpi": 150, "savefig.dpi": 300,
        "font.family": "sans-serif", "font.size": 11, "axes.titlesize": 14,
        "axes.titleweight": "bold", "grid.alpha": 0.3, "axes.grid": True,
        "axes.prop_cycle": cycler("color", cividis_colors),
    })


def dataframe_memory_audit(data: pd.DataFrame) -> pd.DataFrame:
    """Report the active analysis DataFrame's shape and deep memory usage."""
    return pd.DataFrame([{
        "DataFrame": "df_article_summary", "Rows": len(data), "Columns": len(data.columns),
        "Memory (KB)": data.memory_usage(deep=True).sum() / 1024,
    }])


def corpus_characteristics(data: pd.DataFrame) -> tuple[dict, pd.DataFrame, list[str]]:
    """Compute notebook metrics for temporal coverage, growth, age, and impact."""
    warnings = []
    metrics: dict[str, object] = {"Total Documents": len(data)}
    if "Publication Year" in data:
        years = pd.to_numeric(data["Publication Year"], errors="coerce").dropna().astype(int)
        if not years.empty:
            metrics["Timespan"] = f"{years.min()} - {years.max()}"
            documents_per_year = years.value_counts().sort_index()
            first_year, last_year = documents_per_year.index.min(), documents_per_year.index.max()
            if last_year > first_year and documents_per_year.iloc[0] > 0:
                n_years = last_year - first_year
                metrics["Annual Growth Rate (CAGR %)"] = (
                    (documents_per_year.iloc[-1] / documents_per_year.iloc[0]) ** (1 / n_years) - 1
                ) * 100
            else:
                metrics["Annual Growth Rate (CAGR %)"] = np.nan
            full_timeline = pd.Series(0, index=range(first_year, last_year + 1))
            full_timeline = full_timeline.add(documents_per_year, fill_value=0)
            if len(full_timeline) > 1:
                metrics["Linear Growth Reliability (R²)"] = stats.linregress(
                    full_timeline.index, full_timeline.values
                ).rvalue ** 2
            else:
                metrics["Linear Growth Reliability (R²)"] = np.nan
                warnings.append("Linear growth R² requires at least two publication years.")
            metrics["Average Document Age"] = (datetime.now().year - years).mean()
        else:
            warnings.append("Publication Year contains no valid numeric data.")
    else:
        warnings.append("Publication Year is unavailable; temporal metrics were skipped.")
    if "Source Title" in data:
        metrics["Unique Sources"] = data["Source Title"].nunique()
    if "Cited by" in data:
        metrics["Avg. Citations per Doc"] = pd.to_numeric(data["Cited by"], errors="coerce").fillna(0).mean()
    if "Cited Reference Count" in data:
        metrics["Total References (Intellectual Base)"] = pd.to_numeric(
            data["Cited Reference Count"], errors="coerce"
        ).fillna(0).sum()

    def format_value(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:,.2f}"
        if isinstance(value, (int, np.integer)):
            return f"{value:,}"
        return str(value)

    table = pd.DataFrame(metrics.items(), columns=["Metric", "Value"])
    table["Value"] = table["Value"].apply(format_value)
    return metrics, table, warnings


def add_internal_mncs(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Add internal year-normalized citations exactly as defined in the notebook."""
    result = data.copy()
    warnings = []
    if "Publication Year" in result and "Cited by" in result:
        result["Publication Year"] = pd.to_numeric(result["Publication Year"], errors="coerce")
        result["Cited by"] = pd.to_numeric(result["Cited by"], errors="coerce").fillna(0)
        year_averages = result.groupby("Publication Year")["Cited by"].mean().to_dict()

        def calculate_mncs(row):
            baseline = year_averages.get(row["Publication Year"], 1)
            if pd.isna(baseline) or baseline == 0:
                baseline = 1
            return row["Cited by"] / baseline

        result["MNCS"] = result.apply(calculate_mncs, axis=1)
        baselines = pd.DataFrame(sorted(year_averages.items()), columns=["Publication Year", "Average Citations (Baseline)"])
    else:
        result["MNCS"] = 1.0
        baselines = pd.DataFrame(columns=["Publication Year", "Average Citations (Baseline)"])
        warnings.append("Publication Year or Cited by is missing; MNCS was set to the notebook fallback of 1.0.")
    preview_columns = [column for column in ["Title", "Publication Year", "Cited by", "MNCS"] if column in result]
    return result, baselines, warnings


def normalize_doc_type(doc_type_str) -> str:
    """Normalize one raw document type through the notebook taxonomy."""
    if pd.isna(doc_type_str):
        return "Other"
    return DOC_TYPE_MAP.get(str(doc_type_str).lower().strip(), "Other")


def document_type_analysis(data: pd.DataFrame):
    """Create the standardized type table and original monochrome figure."""
    if "Document Type" not in data:
        return pd.DataFrame(), None, ["Document Type is unavailable; structural morphology was skipped."]
    clean = data.copy()
    clean["Document Type"] = clean["Document Type"].fillna("Missing/Incomplete data")
    clean["Document Types List"] = clean["Document Type"].astype(str).str.split("; ")
    exploded = clean.explode("Document Types List")
    exploded["Standardized_Type"] = exploded["Document Types List"].apply(normalize_doc_type)
    counts = exploded["Standardized_Type"].value_counts()
    summary = pd.DataFrame({
        "Document Type": counts.index, "Count": counts.values,
        "Percentage": counts.values / max(1, len(data)) * 100,
    }).sort_values("Count", ascending=False).reset_index(drop=True)
    if summary.empty:
        return summary, None, ["No document types could be counted."]
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(summary["Document Type"], summary["Count"], color="#333333")
    ax.set_xlabel("Percentage of Total Collection (%)")
    ax.set_title(
        f"Structural Morphology: Distribution of Document Types ($N={len(data)}$)",
        pad=20, fontweight="bold",
    )
    ax.invert_yaxis()
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    max_value = summary["Count"].max()
    ax.set_xlim(0, max_value * 1.2)
    for bar, count, percentage in zip(bars, summary["Count"], summary["Percentage"]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f" {count} ({percentage:.1f}%)", ha="left", va="center", fontsize=10, color="black")
    fig.tight_layout()
    return summary, fig, []


def author_analysis(data: pd.DataFrame, top_n=10):
    """Compute full/fractional author metrics and reproduce both author figures."""
    warnings = []
    author_column = None
    if "Author Full Names" in data and not data["Author Full Names"].dropna().empty:
        author_column = "Author Full Names"
    elif "Authors" in data and not data["Authors"].dropna().empty:
        author_column = "Authors"
        warnings.append("Author Full Names is unavailable; Authors was used for author analysis.")
    if not author_column:
        return pd.DataFrame(), None, None, ["No suitable author column was found; author analysis was skipped."], None
    work = data.copy()
    if "MNCS" not in work:
        work["MNCS"] = np.nan
        warnings.append("MNCS was missing; the author impact panel may be empty.")
    authors = work[[author_column, "Cited by", "MNCS"]].dropna(subset=[author_column]).copy()
    authors["num_authors"] = authors[author_column].apply(lambda value: len(str(value).split(";")))
    authors["fractional_credit"] = 1 / authors["num_authors"]
    authors["Authors_Split"] = authors[author_column].astype(str).str.split(";")
    exploded = authors.explode("Authors_Split")
    exploded["Authors_Split"] = exploded["Authors_Split"].str.strip()
    exploded = exploded[exploded["Authors_Split"] != ""]
    author_stats = exploded.groupby("Authors_Split").agg(
        Total_Papers=("Authors_Split", "size"), Total_Citations=("Cited by", "sum"),
        Fractional_Credit=("fractional_credit", "sum"), Avg_MNCS=("MNCS", "mean"),
    ).reset_index().rename(columns={"Authors_Split": "Author"})
    total_authors = len(author_stats)
    if author_stats.empty:
        return author_stats, None, None, warnings + ["No non-empty author names were found."], author_column

    top_traditional = author_stats.sort_values(
        by=["Total_Papers", "Total_Citations"], ascending=False
    ).head(top_n).copy()
    fig_productivity, ax = plt.subplots(figsize=(10, 6))
    plot_traditional = top_traditional.sort_values("Total_Papers", ascending=True)
    bars = ax.barh(plot_traditional["Author"], plot_traditional["Total_Papers"], color="#333333")
    ax.set_xlabel("Total Publications ($N_{papers}$)")
    ax.set_title(
        f"Top {top_n} Authors by Total Publication Volume\n"
        f"(Full Counting, Dataset Total: $N={total_authors}$ Authors)", fontweight="bold"
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    for bar in bars:
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{int(bar.get_width())}", va="center", fontsize=10)
    fig_productivity.tight_layout()

    top_scientific = author_stats.sort_values(
        by=["Fractional_Credit", "Avg_MNCS"], ascending=False
    ).head(top_n).copy()
    top_scientific["Fractional_Credit"] = top_scientific["Fractional_Credit"].round(2)
    top_scientific["Avg_MNCS"] = top_scientific["Avg_MNCS"].round(2)
    fig_impact, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    plot_scientific = top_scientific.sort_values("Fractional_Credit", ascending=True)
    cividis_blue = plt.cm.cividis(0.0)
    ax1.barh(plot_scientific["Author"], plot_scientific["Fractional_Credit"], color="#333333")
    ax1.set_xlabel("Fractionalized Credit ($N_{frac}$)")
    ax1.set_title("Author Contribution\n(Adjusted for Team Size)", fontweight="bold", fontsize=11)
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    ax1.spines[["top", "right"]].set_visible(False)
    for index, value in enumerate(plot_scientific["Fractional_Credit"]):
        ax1.text(value + 0.05, index, f"{value:.2f}", color="black", va="center",
                 fontweight="bold", fontsize=9)
    ax2.hlines(y=plot_scientific["Author"], xmin=0, xmax=plot_scientific["Avg_MNCS"],
               color="gray", alpha=0.5, linewidth=1)
    ax2.plot(plot_scientific["Avg_MNCS"], plot_scientific["Author"], "o",
             markersize=9, color=cividis_blue)
    ax2.axvline(x=1.0, color="black", linestyle="--", linewidth=1.2)
    ax2.text(1.05, 0.02, "Global Avg (1.0)", transform=ax2.get_xaxis_transform(),
             color="black", fontsize=9)
    ax2.set_xlabel("Mean Normalized Citation Score ($MNCS$)")
    ax2.set_title("Citation Impact\n(Field-Normalized)", fontweight="bold", fontsize=11)
    ax2.grid(axis="x", linestyle="--", alpha=0.5)
    ax2.spines[["top", "right", "left"]].set_visible(False)
    ax2.tick_params(left=False)
    for index, value in enumerate(plot_scientific["Avg_MNCS"]):
        ax2.text(value + 0.1, index, f"{value:.2f}", color=cividis_blue, va="center",
                 fontweight="bold", fontsize=9)
    fig_impact.suptitle(
        f"Author Performance: Fractionalized Contribution vs. Normalized Impact\n"
        f"(Top {top_n} of $N={total_authors}$ Authors)", fontsize=14, y=1.05, fontweight="bold"
    )
    fig_impact.tight_layout()
    return author_stats, fig_productivity, fig_impact, warnings, author_column


def annual_production_analysis(data: pd.DataFrame):
    """Gap-fill annual output and reproduce the notebook growth figure."""
    if data.empty or "Publication Year" not in data:
        return pd.DataFrame(), None, {}, ["Publication Year is unavailable; annual production was skipped."]
    plot_data = data.dropna(subset=["Publication Year"]).copy()
    plot_data["Publication Year"] = pd.to_numeric(plot_data["Publication Year"], errors="coerce")
    plot_data = plot_data.dropna(subset=["Publication Year"])
    plot_data["Publication Year"] = plot_data["Publication Year"].astype(int)
    annual = plot_data.groupby("Publication Year").size().reset_index(name="Count")
    if annual.empty:
        return annual, None, {}, ["No valid publication years were available."]
    min_year, max_year = annual["Publication Year"].min(), annual["Publication Year"].max()
    annual = pd.DataFrame({"Publication Year": range(min_year, max_year + 1)}).merge(
        annual, on="Publication Year", how="left"
    ).fillna(0)
    annual["Count"] = annual["Count"].astype(int)
    total_n = annual["Count"].sum()
    nonzero = annual[annual["Count"] > 0]
    cagr = np.nan
    cagr_string = "N/A"
    if not nonzero.empty:
        start_row = nonzero.iloc[0]
        years_difference = max_year - start_row["Publication Year"]
        if start_row["Count"] > 0 and years_difference >= 1:
            cagr = (annual.iloc[-1]["Count"] / start_row["Count"]) ** (1 / years_difference) - 1
            cagr_string = f"{cagr:.1%}"
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(annual["Publication Year"], annual["Count"], color="#555555", marker="o",
            linewidth=1.5, alpha=0.7, label="Annual Volume (Raw)")
    regression = {"Slope": np.nan, "Intercept": np.nan, "R²": np.nan,
                  "p-value": np.nan, "Standard error": np.nan, "CAGR": cagr}
    if len(annual) > 1:
        fit = stats.linregress(annual["Publication Year"], annual["Count"])
        line = fit.slope * annual["Publication Year"] + fit.intercept
        ax.plot(annual["Publication Year"], line, linestyle="--", linewidth=2.5,
                color=plt.cm.cividis(0.0), label=f"Linear Trend ($R^2={fit.rvalue**2:.2f}$)")
        regression.update({"Slope": fit.slope, "Intercept": fit.intercept, "R²": fit.rvalue ** 2,
                           "p-value": fit.pvalue, "Standard error": fit.stderr})
    ax.set_title(
        f"Annual Scientific Production: Growth Trends ({min_year}–{max_year})\n"
        f"Total $N={total_n}$ Articles | CAGR: {cagr_string}", fontsize=14, fontweight="bold", pad=15
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Articles")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlim(min_year - 0.5, max_year + 1.0)
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.95)
    fig.tight_layout()
    regression_table = pd.DataFrame(regression.items(), columns=["Growth statistic", "Value"])
    return annual, fig, regression_table, []


def citation_dynamics_analysis(data: pd.DataFrame, cutoff_year=None):
    """Reproduce accumulated citation versus annualized velocity analysis."""
    if "Publication Year" not in data or "Cited by" not in data:
        return pd.DataFrame(), None, ["Publication Year or Cited by is missing; citation dynamics was skipped."]
    cutoff = int(cutoff_year or datetime.now().year)
    work = data.copy()
    work["Publication Year"] = pd.to_numeric(work["Publication Year"], errors="coerce")
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce")
    work = work.dropna(subset=["Publication Year"])
    citations = work.groupby("Publication Year").agg(
        MeanTotalCitations=("Cited by", "mean"), N=("Publication Year", "size")
    ).reset_index()
    if citations.empty:
        return citations, None, ["No valid publication years were available for citation dynamics."]
    min_year, max_year = int(citations["Publication Year"].min()), int(citations["Publication Year"].max())
    citations = pd.DataFrame({"Publication Year": range(min_year, max_year + 1)}).merge(
        citations, on="Publication Year", how="left"
    )
    citations["N"] = citations["N"].fillna(0)
    citations["Age"] = (cutoff - citations["Publication Year"]) + 0.5
    citations["MeanAnnualized"] = citations["MeanTotalCitations"] / citations["Age"]
    warnings = []
    if (citations["Age"] <= 0).any():
        warnings.append("The annualization cutoff is not later than every publication year; some citation velocities may be negative or undefined.")
    fig, ax1 = plt.subplots(figsize=(12, 7))
    total_documents = int(citations["N"].sum())
    ax1.set_title(
        f"Citation Lifecycle: Accumulated Prestige vs. Impact Velocity ($N={total_documents}$ Articles)",
        fontsize=14, fontweight="bold", pad=20,
    )
    color_bars = plt.cm.cividis(0.95)
    color_line = plt.cm.cividis(0.0)
    ax1.bar(citations["Publication Year"], citations["MeanTotalCitations"], color=color_bars,
            alpha=0.7, edgecolor="grey", linewidth=0.5, label="Mean Total Citations (Accumulated)")
    ax1.set_xlabel("Publication Year", fontsize=12)
    ax1.set_ylabel("Mean Total Citations", color="#8c7b00", fontsize=12, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor="#8c7b00")
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=20))
    ax1.tick_params(axis="x", rotation=45)
    ax2 = ax1.twinx()
    ax2.plot(citations["Publication Year"], citations["MeanAnnualized"], color=color_line,
             marker="o", linewidth=2.5, markersize=6, label="Mean Annualized Citations (Velocity)")
    ax2.set_ylabel("Mean Annualized Citations (Cites/Year)", color=color_line,
                   fontsize=12, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=color_line)
    ax2.set_ylim(bottom=0)
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc="upper left", facecolor="white", framealpha=0.9)
    ax1.grid(True, axis="x", linestyle="--", alpha=0.3)
    ax2.spines["top"].set_visible(False)
    fig.tight_layout()
    return citations, fig, warnings


def calculate_local_h_index(citations) -> int:
    """Calculate the notebook's local source h-index."""
    sorted_citations = sorted(pd.to_numeric(pd.Series(citations), errors="coerce").fillna(0), reverse=True)
    h = 0
    for index, citation in enumerate(sorted_citations, 1):
        if citation >= index:
            h = index
        else:
            break
    return h


def calculate_local_g_index(citations) -> int:
    """Calculate the notebook's local source g-index."""
    sorted_citations = sorted(pd.to_numeric(pd.Series(citations), errors="coerce").fillna(0), reverse=True)
    g, cumulative = 0, 0
    for index, citation in enumerate(sorted_citations, 1):
        cumulative += citation
        if cumulative >= index ** 2:
            g = index
        else:
            break
    return g


def format_journal_title(title_str) -> str:
    """Apply notebook capitalization while protecting common journal acronyms."""
    if pd.isna(title_str):
        return "Unknown Source"
    formatted = []
    for index, word in enumerate(str(title_str).split()):
        clean = re.sub(r"[^\w\s]", "", word).lower()
        if clean in PROTECTED_ACRONYMS:
            formatted.append(clean.upper())
        elif clean in LOWERCASE_WORDS and index > 0:
            formatted.append(word.lower())
        else:
            formatted.append(word.title())
    return " ".join(formatted)


def _create_top_source_panel(ax, data, column, title, xlabel, is_float=False):
    plot_data = data.sort_values(by=column, ascending=True)
    bars = ax.barh(plot_data["Source_Display"], plot_data[column], color="#333333")
    ax.set_title(title, fontweight="bold", fontsize=11)
    ax.set_xlabel(xlabel, fontsize=10)
    max_value = plot_data[column].max()
    ax.set_xlim(0, max_value * 1.2 if max_value > 0 else 1)
    for bar in bars:
        width = bar.get_width()
        label = f" {width:.2f}" if is_float else f" {int(width)}"
        ax.annotate(label, xy=(width, bar.get_y() + bar.get_height() / 2), xytext=(3, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=9)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    if not is_float:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))


def source_impact_analysis(data: pd.DataFrame, min_papers=5, max_length=30):
    """Compute local source metrics and reproduce both journal figures."""
    warnings = []
    if "Source Title" not in data:
        return data.copy(), {}, {}, ["Source Title is unavailable; source impact analysis was skipped."]
    work = data.copy()
    work["Source_Key"] = (work["Source Title"].astype(str).str.lower()
        .str.replace(" & ", " and ", regex=False).str.replace("&", "and", regex=False)
        .str.replace("-", " ", regex=False).str.replace(r"[^\w\s]", "", regex=True).str.strip())
    if "MNCS" not in work:
        work["MNCS"] = np.nan
        warnings.append("MNCS was missing; source efficiency metrics may be empty.")
    required = ["Source_Key", "Publication Year", "Cited by", "Source Title"]
    if not all(column in work for column in required):
        return work, {}, {}, warnings + ["Required source-analysis columns are missing."]
    clean = work.dropna(subset=["Source Title", "Publication Year"]).copy()
    clean["Publication Year"] = pd.to_numeric(clean["Publication Year"], errors="coerce")
    clean["Cited by"] = pd.to_numeric(clean["Cited by"], errors="coerce").fillna(0)
    clean = clean.dropna(subset=["Publication Year"])
    if clean.empty:
        return work, {}, {}, warnings + ["No source records with valid publication years were available."]
    current_year = datetime.now().year
    source_stats = clean.groupby("Source_Key").agg(
        OriginalTitle=("Source Title", lambda values: values.mode().iloc[0]),
        h_index=("Cited by", calculate_local_h_index),
        g_index=("Cited by", calculate_local_g_index),
        Total_Citations=("Cited by", "sum"),
        Number_of_Publications=("Source_Key", "size"),
        Avg_MNCS=("MNCS", "mean"),
        First_Publication_Year=("Publication Year", "min"),
    ).reset_index()
    source_stats["OriginalTitle"] = source_stats["OriginalTitle"].apply(format_journal_title)
    source_stats["Years_Active"] = source_stats["First_Publication_Year"].apply(
        lambda year: max(1, current_year - int(year) + 1)
    )
    source_stats["m_index"] = source_stats["h_index"] / source_stats["Years_Active"]
    source_stats["Source_Display"] = source_stats["OriginalTitle"].apply(
        lambda title: title if len(title) <= max_length else title[:max_length] + "..."
    )
    title_map = source_stats.set_index("Source_Key")["OriginalTitle"]
    work["OriginalTitle"] = work["Source_Key"].map(title_map)
    rankings = {
        "top_sources_by_volume": source_stats.sort_values("Number_of_Publications", ascending=False).head(10).copy(),
        "top_sources_by_h_index": source_stats.sort_values("h_index", ascending=False).head(10).copy(),
        "top_sources_by_g_index": source_stats.sort_values("g_index", ascending=False).head(10).copy(),
        "top_sources_by_m_index": source_stats.sort_values("m_index", ascending=False).head(10).copy(),
    }

    figure_descriptive, axes = plt.subplots(2, 2, figsize=(20, 12))
    figure_descriptive.suptitle(
        f"Descriptive Bibliometric Indicators: Top Sources (Total $N={len(source_stats)}$)",
        fontsize=18, fontweight="bold", y=0.98,
    )
    _create_top_source_panel(axes[0, 0], rankings["top_sources_by_volume"], "Number_of_Publications",
                             "Most Productive Sources", "Total Publications")
    _create_top_source_panel(axes[0, 1], rankings["top_sources_by_h_index"], "h_index",
                             "Highest Local Impact", "Local H-Index")
    _create_top_source_panel(axes[1, 0], rankings["top_sources_by_g_index"], "g_index",
                             "Highest Cumulative Impact", "Local G-Index")
    _create_top_source_panel(axes[1, 1], rankings["top_sources_by_m_index"], "m_index",
                             "Highest Sustained Impact", "Local M-Index", is_float=True)
    figure_descriptive.tight_layout(rect=[0, 0.03, 1, 0.95])

    significant = source_stats[source_stats["Number_of_Publications"] >= min_papers].copy()
    top_impact = significant.sort_values(["Avg_MNCS", "h_index"], ascending=False).head(10).copy()
    top_impact["Avg_MNCS"] = top_impact["Avg_MNCS"].round(2)
    rankings["top_sources_by_mncs"] = top_impact
    figure_impact = None
    if not top_impact.empty:
        figure_impact, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
        plot_impact = top_impact.sort_values("Avg_MNCS", ascending=True)
        ax1.barh(plot_impact["Source_Display"], plot_impact["h_index"], color="#333333")
        ax1.set_xlabel("Local H-Index (Corpus Specific)")
        ax1.set_title("Accumulated Prestige (Local H-Index)", fontweight="bold")
        ax1.grid(axis="x", linestyle="--", alpha=0.5)
        ax1.spines[["top", "right"]].set_visible(False)
        for index, value in enumerate(plot_impact["h_index"]):
            ax1.text(value + 0.1, index, str(value), color="black", va="center", fontweight="bold", fontsize=9)
        cividis_blue = plt.cm.cividis(0.0)
        ax2.hlines(y=plot_impact["Source_Display"], xmin=0, xmax=plot_impact["Avg_MNCS"],
                   color="gray", alpha=0.5, linewidth=1)
        ax2.plot(plot_impact["Avg_MNCS"], plot_impact["Source_Display"], "o",
                 markersize=9, color=cividis_blue)
        ax2.axvline(x=1.0, color="black", linestyle="--", linewidth=1.2)
        ax2.text(1.05, 0.02, "Global Avg (1.0)", transform=ax2.get_xaxis_transform(),
                 color="black", fontsize=9, verticalalignment="bottom")
        ax2.set_xlabel("Mean Normalized Citation Score (MNCS)")
        ax2.set_title("Normalized Impact Efficiency (MNCS)", fontweight="bold")
        ax2.grid(axis="x", linestyle="--", alpha=0.5)
        ax2.spines[["top", "right", "left"]].set_visible(False)
        ax2.tick_params(left=False)
        for index, value in enumerate(plot_impact["Avg_MNCS"]):
            ax2.text(value + 0.1, index, f"{value:.2f}", color=cividis_blue,
                     va="center", fontweight="bold", fontsize=9)
        figure_impact.suptitle(
            "Journal Impact Analysis: Accumulated Prestige vs. Normalized Efficiency\n"
            f"(Subset: $N={len(significant)}$ Sources with $\\geq${min_papers} Articles)",
            fontsize=16, y=1.05,
        )
        figure_impact.tight_layout()
    else:
        warnings.append(f"No sources met the minimum of {min_papers} papers for the MNCS impact panel.")
    figures = {"composite_top_sources_descriptive": figure_descriptive}
    if figure_impact is not None:
        figures["top_10_journals_impact_analysis"] = figure_impact
    tables = {"all_sources_ranked": source_stats, **rankings}
    return work, tables, figures, warnings


def run_descriptive_bibliometrics(
    data: pd.DataFrame, cutoff_year=None, top_n=10, min_source_papers=5,
    max_source_title_length=30,
) -> dict:
    """Run notebook sections 9 and 11–15 and return tables, figures, and warnings."""
    configure_publication_style()
    if data is None or data.empty:
        raise ValueError("The analysis dataset is empty.")
    metrics, main_information, warnings = corpus_characteristics(data)
    enriched, mncs_baselines, mncs_warnings = add_internal_mncs(data)
    warnings.extend(mncs_warnings)
    document_types, document_figure, document_warnings = document_type_analysis(enriched)
    warnings.extend(document_warnings)
    authors, author_productivity_figure, author_impact_figure, author_warnings, author_column = author_analysis(
        enriched, top_n=top_n
    )
    warnings.extend(author_warnings)
    annual, annual_figure, regression, annual_warnings = annual_production_analysis(enriched)
    warnings.extend(annual_warnings)
    citation_dynamics, citation_figure, citation_warnings = citation_dynamics_analysis(enriched, cutoff_year)
    warnings.extend(citation_warnings)
    enriched, source_tables, source_figures, source_warnings = source_impact_analysis(
        enriched, min_papers=min_source_papers, max_length=max_source_title_length
    )
    warnings.extend(source_warnings)
    figures = {
        name: figure for name, figure in {
            "document_types": document_figure,
            "author_productivity_ranking": author_productivity_figure,
            "author_impact_panel_chart": author_impact_figure,
            "annual_scientific_production": annual_figure,
            "citation_dynamics_dual_axis": citation_figure,
        }.items() if figure is not None
    }
    figures.update(source_figures)
    return {
        "data": enriched,
        "metrics": metrics,
        "tables": {
            "main_information_summary": main_information,
            "mncs_yearly_baselines": mncs_baselines,
            "document_type_summary": document_types,
            "author_metrics_complete": authors,
            "annual_scientific_production": annual,
            "growth_regression_statistics": regression,
            "citation_dynamics": citation_dynamics,
            "dataframe_memory_audit": dataframe_memory_audit(enriched),
            **source_tables,
        },
        "figures": figures, "warnings": list(dict.fromkeys(warnings)),
        "author_column": author_column,
        "config": {"cutoff_year": cutoff_year, "top_n": top_n,
                   "min_source_papers": min_source_papers,
                   "max_source_title_length": max_source_title_length},
    }
