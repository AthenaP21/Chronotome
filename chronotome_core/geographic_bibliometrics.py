"""Notebook-faithful geographic distribution and collaboration analysis."""

from __future__ import annotations

import ast
import itertools
import re
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import networkx as nx
import numpy as np
import pandas as pd

try:
    import seaborn as sns
except ImportError:
    sns = None

from .descriptive_bibliometrics import (
    add_internal_mncs, configure_publication_style, normalize_doc_type,
)

try:
    from adjustText import adjust_text
    ADJUST_TEXT_AVAILABLE = True
except ImportError:
    adjust_text = None
    ADJUST_TEXT_AVAILABLE = False


def ensure_country_list(value) -> list:
    """Return a safe list from list-valued or serialized country metadata."""
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return []


def classify_country_collaboration(country_list) -> str:
    """Classify one article as SCP, MCP, or Unknown."""
    if isinstance(country_list, list):
        clean = {str(country).strip() for country in country_list if country and str(country).strip()}
        if len(clean) == 1:
            return "SCP"
        if len(clean) > 1:
            return "MCP"
    return "Unknown"


def configure_advanced_country_style():
    """Apply the notebook's Section 18 publication-ready plotting defaults."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "figure.dpi": 200, "savefig.dpi": 600,
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 14, "axes.labelsize": 12,
        "xtick.labelsize": 10, "ytick.labelsize": 10,
        "axes.linewidth": 0.8, "grid.alpha": 0.25,
        "grid.linestyle": ":", "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": True,
        "legend.framealpha": 0.95,
    })


def _fallback_adjust_text(texts, ax, iterations=80):
    """Nudge overlapping labels apart when the optional adjustText package is absent."""
    if not texts:
        return
    figure = ax.figure
    for _ in range(iterations):
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        boxes = [text.get_window_extent(renderer=renderer).expanded(1.03, 1.08) for text in texts]
        moved = False
        for first in range(len(texts)):
            for second in range(first + 1, len(texts)):
                if not boxes[first].overlaps(boxes[second]):
                    continue
                x_display, y_display = ax.transData.transform(texts[second].get_position())
                direction = 1 if boxes[second].y0 >= boxes[first].y0 else -1
                new_position = ax.transData.inverted().transform((x_display + 2, y_display + direction * 4))
                texts[second].set_position(new_position)
                moved = True
        if not moved:
            break


def advanced_country_analysis(
    data: pd.DataFrame,
    collaboration: pd.DataFrame,
    citation_top_n: int = 15,
    min_publications: int = 5,
    network_top_n: int = 30,
    top_k_edges_per_node: int = 5,
    layout_iterations: int = 250,
) -> dict:
    """Run notebook Section 18 impact, strategic-matrix, and network analyses."""
    configure_advanced_country_style()
    warnings: list[str] = []
    frame = data.copy()
    frame["Cited by"] = pd.to_numeric(frame.get("Cited by", 0), errors="coerce").fillna(0)

    if "Publication Year" in frame.columns:
        frame["Publication Year"] = pd.to_numeric(frame["Publication Year"], errors="coerce")
        yearly = (
            frame.groupby("Publication Year")["Cited by"].mean()
            .reset_index(name="Global_Avg_Citations")
        )
        normalized = frame.merge(yearly, on="Publication Year", how="left")
        normalized["Global_Avg_Citations"] = normalized["Global_Avg_Citations"].fillna(1).replace(0, 1)
        normalized["Normalized_Citations"] = (
            normalized["Cited by"] / normalized["Global_Avg_Citations"]
        )
    else:
        yearly = pd.DataFrame(columns=["Publication Year", "Global_Avg_Citations"])
        normalized = frame.copy()
        normalized["Normalized_Citations"] = pd.to_numeric(
            normalized.get("MNCS", 1.0), errors="coerce"
        ).fillna(0)
        warnings.append(
            "Publication Year is unavailable; the advanced analysis reused existing MNCS values."
        )

    normalized["Countries_List"] = normalized["Countries_Extracted"].apply(ensure_country_list)
    normalized_exploded = normalized.explode("Countries_List").rename(columns={"Countries_List": "Country"})
    normalized_exploded = normalized_exploded.dropna(subset=["Country"])
    normalized_exploded["Country"] = normalized_exploded["Country"].astype(str).str.strip()
    normalized_exploded = normalized_exploded[normalized_exploded["Country"] != ""]

    impact = (
        normalized_exploded.groupby("Country")
        .agg(MNCS=("Normalized_Citations", "mean"), Total_Citations=("Cited by", "sum"))
        .reset_index()
    )
    country_stats = collaboration.merge(impact, on="Country", how="left", suffixes=("", "_Advanced"))
    for column in ("MNCS", "Total_Citations"):
        advanced_column = f"{column}_Advanced"
        if advanced_column in country_stats.columns:
            country_stats[column] = country_stats[advanced_column]
            country_stats = country_stats.drop(columns=[advanced_column])
    country_stats["MNCS"] = country_stats.get("MNCS", 0).fillna(0)
    country_stats["Total_Citations"] = country_stats.get("Total_Citations", 0).fillna(0).astype(int)
    country_stats["Total_Articles"] = country_stats["Articles"]
    total_countries = len(country_stats)

    figures: dict = {}
    tables: dict[str, pd.DataFrame] = {
        "advanced_mncs_yearly_baselines": yearly,
        "country_master_stats": country_stats,
    }

    # Plot A: citation distribution, retaining exact notebook dimensions and Cividis range.
    top_cited = country_stats.sort_values("Total_Citations", ascending=False).head(
        max(1, int(citation_top_n))
    )
    top_cited_plot = top_cited.sort_values("Total_Citations", ascending=True)
    tables["top_countries_by_total_citations"] = top_cited
    if not top_cited_plot.empty:
        fig_a, ax = plt.subplots(figsize=(10.5, 6.5))
        colors = plt.cm.cividis(np.linspace(0.20, 0.95, len(top_cited_plot)))
        ax.barh(top_cited_plot["Country"], top_cited_plot["Total_Citations"], color=colors, edgecolor="none")
        ax.set_xlabel("Total Accumulated Citations ($TC$)")
        ax.set_ylabel("")
        ax.set_title(
            f"Global Citation Distribution (Top {len(top_cited)} of $N={total_countries}$ Countries)",
            fontweight="bold", pad=12,
        )
        comma_format = mtick.FuncFormatter(lambda value, position: f"{int(value):,}" if value >= 1 else f"{value:g}")
        ax.xaxis.set_major_formatter(comma_format)
        maximum = top_cited_plot["Total_Citations"].max()
        limit = maximum if maximum > 0 else 1
        ax.set_xlim(0, limit * 1.12)
        for i, value in enumerate(top_cited_plot["Total_Citations"].values):
            ax.text(value + limit * 0.01, i, f"{int(value):,}", va="center", ha="left", fontsize=9)
        fig_a.tight_layout()
        figures["Country_Citation_Impact_Distribution"] = fig_a

    # Plot B: productivity-impact strategic matrix.
    matrix_data = country_stats[country_stats["Total_Articles"] >= max(1, int(min_publications))].copy()
    tables["country_performance_matrix_data"] = matrix_data
    if matrix_data.empty:
        warnings.append(
            f"No country met the minimum of {int(min_publications)} articles; the performance matrix was skipped."
        )
    else:
        fig_b, ax = plt.subplots(figsize=(12, 9))
        citations = matrix_data["Total_Citations"].fillna(0).clip(lower=0).astype(float)
        citation_sqrt = np.sqrt(citations + 1)
        maximum_sqrt = citation_sqrt.max()
        sizes = 40 + (citation_sqrt / maximum_sqrt) * (1400 - 40) if maximum_sqrt else np.full(len(citations), 40)
        mncs = matrix_data["MNCS"].fillna(0).astype(float)
        vmin, vmax = np.nanpercentile(mncs, 2), np.nanpercentile(mncs, 98)
        if vmin == vmax:
            vmin, vmax = mncs.min(), mncs.max() + 1e-9
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        scatter = ax.scatter(
            matrix_data["Total_Articles"], matrix_data["MNCS"],
            s=sizes, c=mncs, cmap=plt.cm.cividis, norm=norm,
            alpha=0.82, linewidth=0.6, edgecolors="white",
        )
        ax.set_xscale("log")
        ax.axhline(1.0, color="black", linestyle="--", linewidth=1.2, alpha=0.85)
        median_productivity = matrix_data["Total_Articles"].median()
        ax.axvline(median_productivity, color="black", linestyle=":", linewidth=1.0, alpha=0.6)
        ax.set_xlabel("Total Publications (log scale)")
        ax.set_ylabel("Mean Normalized Citation Score (MNCS)")
        ax.set_title(
            "Scientometric Performance Matrix: Productivity vs. Impact\n"
            f"(Subset: $N={len(matrix_data)}$ Countries with $\\geq$ {int(min_publications)} Articles)",
            fontweight="bold", pad=14,
        )
        ax.grid(True, which="both", linestyle=":", alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        ax.text(0.02, 0.99, "Low Productivity / High Impact (Niche)",
                transform=ax.transAxes, ha="left", va="top", fontsize=8, fontweight="bold")
        ax.text(0.98, 0.99, "High Productivity / High Impact",
                transform=ax.transAxes, ha="right", va="top", fontsize=8, fontweight="bold")
        ax.text(0.02, 0.01, "Low Productivity / Low Impact",
                transform=ax.transAxes, ha="left", va="bottom", fontsize=8, fontweight="bold", alpha=0.85)
        ax.text(0.98, 0.01, "High Productivity / Low Impact",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=8, fontweight="bold", alpha=0.85)
        colorbar = fig_b.colorbar(scatter, ax=ax, pad=0.02)
        colorbar.set_label("MNCS (Cividis)", rotation=90)
        labels = pd.concat([
            matrix_data.nlargest(15, "Total_Articles"),
            matrix_data.nlargest(10, "MNCS"),
            matrix_data.nlargest(10, "Total_Citations"),
        ]).drop_duplicates(subset=["Country"])
        texts = []
        for row in labels.itertuples():
            texts.append(ax.text(
                row.Total_Articles, row.MNCS, textwrap.fill(row.Country, 18),
                fontsize=9, ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1.5),
            ))
        if ADJUST_TEXT_AVAILABLE and texts:
            try:
                adjust_text(
                    texts, ax=ax,
                    arrowprops=dict(arrowstyle="-", color="gray", lw=0.6, alpha=0.7),
                    expand_points=(1.2, 1.2), expand_text=(1.1, 1.2),
                )
            except Exception:
                _fallback_adjust_text(texts, ax)
        elif texts:
            _fallback_adjust_text(texts, ax)
        fig_b.tight_layout()
        figures["Scientometric_Performance_Matrix_Productivity_vs_Impact"] = fig_b

    # Plot C: weighted international collaboration network.
    graph = nx.Graph()
    for country_list in frame["Countries_Extracted"].apply(ensure_country_list):
        clean = sorted({str(country).strip() for country in country_list if country and str(country).strip()})
        if len(clean) > 1:
            for country_a, country_b in itertools.combinations(clean, 2):
                if graph.has_edge(country_a, country_b):
                    graph[country_a][country_b]["weight"] += 1
                else:
                    graph.add_edge(country_a, country_b, weight=1)

    full_edges = pd.DataFrame(
        [(a, b, values["weight"]) for a, b, values in graph.edges(data=True)],
        columns=["Country A", "Country B", "Weight"],
    )
    if graph.number_of_edges() == 0:
        warnings.append("Not enough multi-country connections were available for the collaboration network.")
        tables["international_collaboration_edges"] = full_edges
        tables["international_collaboration_nodes"] = pd.DataFrame(
            columns=["Country", "Weighted Degree", "MNCS", "Displayed"]
        )
        subgraph = nx.Graph()
    else:
        weighted_degree = dict(graph.degree(weight="weight"))
        top_nodes = sorted(weighted_degree, key=weighted_degree.get, reverse=True)[:max(1, int(network_top_n))]
        subgraph = graph.subgraph(top_nodes).copy()
        keep: set[tuple[str, str]] = set()
        for node in subgraph.nodes():
            strongest = sorted(
                subgraph.edges(node, data=True), key=lambda edge: edge[2].get("weight", 1), reverse=True
            )[:max(1, int(top_k_edges_per_node))]
            for country_a, country_b, _ in strongest:
                keep.add(tuple(sorted((country_a, country_b))))
        displayed_edges = [(a, b) for a, b in keep if subgraph.has_edge(a, b)]
        displayed_set = set(displayed_edges)
        full_edges["Displayed"] = full_edges.apply(
            lambda row: tuple(sorted((row["Country A"], row["Country B"]))) in displayed_set, axis=1
        )
        tables["international_collaboration_edges"] = full_edges.sort_values("Weight", ascending=False)
        mncs_map = country_stats.set_index("Country")["MNCS"].to_dict()
        node_table = pd.DataFrame({
            "Country": list(graph.nodes()),
            "Weighted Degree": [weighted_degree[node] for node in graph.nodes()],
            "MNCS": [mncs_map.get(node, np.nan) for node in graph.nodes()],
            "Displayed": [node in subgraph for node in graph.nodes()],
        }).sort_values("Weighted Degree", ascending=False)
        tables["international_collaboration_nodes"] = node_table

        sub_degree = dict(subgraph.degree(weight="weight"))
        degree_values = np.array([sub_degree[node] for node in subgraph.nodes()], dtype=float)
        node_sizes = 300 + (np.sqrt(degree_values) / np.sqrt(degree_values.max())) * (2600 - 300)
        mncs_values = np.array([mncs_map.get(node, np.nan) for node in subgraph.nodes()], dtype=float)
        if np.all(np.isnan(mncs_values)):
            mncs_values = np.zeros(len(subgraph.nodes()))
        vmin, vmax = np.nanpercentile(mncs_values, 2), np.nanpercentile(mncs_values, 98)
        if vmin == vmax:
            vmin, vmax = np.nanmin(mncs_values), np.nanmax(mncs_values) + 1e-9
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        node_colors = plt.cm.cividis(norm(np.nan_to_num(mncs_values, nan=vmin)))
        positions = nx.spring_layout(
            subgraph, weight="weight", k=1.2, iterations=max(1, int(layout_iterations)), seed=42
        )
        fig_c, ax = plt.subplots(figsize=(18, 11))
        ax.set_axis_off()
        weights = np.array([subgraph[a][b]["weight"] for a, b in displayed_edges], dtype=float)
        widths = 0.4 + 3.0 * (np.log1p(weights) / np.log1p(weights.max())) if len(weights) else []
        nx.draw_networkx_edges(
            subgraph, positions, edgelist=displayed_edges, width=widths,
            edge_color="black", alpha=0.12, ax=ax,
        )
        nx.draw_networkx_nodes(
            subgraph, positions, node_size=node_sizes, node_color=node_colors,
            edgecolors="black", linewidths=0.8, alpha=0.95, ax=ax,
        )
        label_top = sorted(sub_degree, key=sub_degree.get, reverse=True)[:40]
        texts = []
        for node in label_top:
            x, y = positions[node]
            texts.append(ax.text(
                x, y, node, fontsize=11, fontweight="bold", ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=1.2),
            ))
        if ADJUST_TEXT_AVAILABLE and texts:
            try:
                adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", color="gray", lw=0.6, alpha=0.6))
            except Exception:
                _fallback_adjust_text(texts, ax)
        elif texts:
            _fallback_adjust_text(texts, ax)
        color_scalar = plt.cm.ScalarMappable(cmap=plt.cm.cividis, norm=norm)
        color_scalar.set_array([])
        colorbar = fig_c.colorbar(color_scalar, ax=ax, shrink=0.75, pad=0.02)
        colorbar.set_label("MNCS (Cividis)")
        reference_degrees = np.unique(np.round(np.nanpercentile(degree_values, [50, 75, 95])).astype(int))
        handles = []
        for reference in reference_degrees:
            reference_size = 300 + (np.sqrt(reference) / np.sqrt(degree_values.max())) * (2600 - 300)
            handles.append(ax.scatter([], [], s=reference_size, facecolors="none", edgecolors="black", linewidth=0.8))
        ax.legend(
            handles, [f"Weighted degree ≈ {value:,}" for value in reference_degrees],
            title="Node size", loc="lower left", frameon=True, fontsize=8,
            title_fontsize=9, markerscale=0.55, labelspacing=0.25,
            handletextpad=0.5, borderpad=0.35, handlelength=1.0,
        )
        ax.set_title(
            "International Collaboration Network (Co-authorship)\n"
            f"Top {len(subgraph.nodes())} Nodes by Collaboration Strength | "
            f"Full Network: $N={len(graph.nodes())}$ Countries, $E={len(graph.edges())}$ Links\n"
            f"Edges shown: strongest ties (top-{int(top_k_edges_per_node)} per node)",
            fontsize=15, fontweight="bold", pad=16,
        )
        fig_c.tight_layout()
        figures["International_Collaboration_Network_Topology"] = fig_c

    return {
        "tables": tables,
        "figures": figures,
        "warnings": list(dict.fromkeys(warnings)),
        "network": graph,
        "network_subgraph": subgraph,
        "metadata": {
            "matrix_countries": len(matrix_data),
            "network_countries": graph.number_of_nodes(),
            "network_links": graph.number_of_edges(),
            "displayed_network_countries": subgraph.number_of_nodes(),
        },
    }


def geographic_distribution_analysis(
    data: pd.DataFrame,
    collaboration_top_n: int = 10,
    impact_top_n: int = 15,
    min_papers: int = 5,
    exclude_unknown: bool = True,
) -> dict:
    """Run notebook Section 17 country collaboration and impact analysis.

    Returns an article-level enriched dataset, country tables, the two original
    Matplotlib figures, warnings, and summary metadata. Country appearances use
    full counting: an MCP article contributes once to every detected country.
    """
    if data is None or data.empty:
        raise ValueError("The geographic analysis dataset is empty.")
    if "Countries_Extracted" not in data.columns:
        raise ValueError(
            "Countries_Extracted is required. Run Institutional and Geographic Entity Resolution first."
        )

    configure_publication_style()
    warnings: list[str] = []
    enriched = data.copy()
    if "MNCS" not in enriched.columns:
        enriched, baselines, mncs_warnings = add_internal_mncs(enriched)
        warnings.extend(mncs_warnings)
        warnings.append("MNCS was calculated from the uploaded corpus's publication-year citation averages.")
    else:
        enriched["MNCS"] = pd.to_numeric(enriched["MNCS"], errors="coerce")
        baselines = pd.DataFrame(columns=["Publication Year", "Average Citations (Baseline)"])

    if "Cited by" not in enriched.columns:
        enriched["Cited by"] = 0
        warnings.append("Cited by is unavailable; total country citations were set to zero.")
    enriched["Cited by"] = pd.to_numeric(enriched["Cited by"], errors="coerce").fillna(0)
    enriched["Countries_Extracted_List"] = enriched["Countries_Extracted"].apply(ensure_country_list)
    enriched["Country_Classification"] = enriched["Countries_Extracted_List"].apply(
        classify_country_collaboration
    )

    classification_order = ["SCP", "MCP", "Unknown"]
    counts = enriched["Country_Classification"].value_counts().reindex(classification_order, fill_value=0)
    classification_summary = pd.DataFrame({
        "Country Classification": counts.index,
        "Articles": counts.values.astype(int),
        "Percentage": counts.values / max(1, len(enriched)) * 100,
    })

    unknown_count = int((enriched["Country_Classification"] == "Unknown").sum())
    if exclude_unknown:
        collaboration_data = enriched[enriched["Country_Classification"] != "Unknown"].copy()
    else:
        collaboration_data = enriched.copy()
        unknown_mask = collaboration_data["Country_Classification"] == "Unknown"
        collaboration_data.loc[unknown_mask, "Countries_Extracted_List"] = pd.Series(
            [["Unknown"] for _ in range(int(unknown_mask.sum()))], index=collaboration_data.index[unknown_mask]
        )
    if unknown_count:
        action = "excluded from country rankings" if exclude_unknown else "retained as an Unknown country"
        warnings.append(f"{unknown_count:,} articles without valid country data were {action}.")
    if collaboration_data.empty:
        raise ValueError("No articles with valid country data remain for geographic analysis.")

    exploded = collaboration_data.explode("Countries_Extracted_List").copy()
    exploded = exploded.rename(columns={"Countries_Extracted_List": "Country_Exploded"})
    exploded = exploded.dropna(subset=["Country_Exploded"])
    exploded["Country_Exploded"] = exploded["Country_Exploded"].astype(str).str.strip()
    exploded = exploded[exploded["Country_Exploded"] != ""]
    if exploded.empty:
        raise ValueError("Country lists were present but did not contain usable country names.")

    collaboration = (
        exploded.groupby("Country_Exploded")["Country_Classification"]
        .agg(
            Articles="size",
            SCP=lambda values: (values == "SCP").sum(),
            MCP=lambda values: (values == "MCP").sum(),
        )
        .reset_index()
        .rename(columns={"Country_Exploded": "Country"})
    )
    collaboration[["Articles", "SCP", "MCP"]] = collaboration[["Articles", "SCP", "MCP"]].astype(int)
    denominator = collaboration["Articles"].replace(0, np.nan)
    collaboration["SCP %"] = (collaboration["SCP"] / denominator * 100).round(1).fillna(0)
    collaboration["MCP %"] = (collaboration["MCP"] / denominator * 100).round(1).fillna(0)
    collaboration["MCP_Ratio"] = (collaboration["MCP"] / denominator).fillna(0)
    collaboration = collaboration.sort_values("Articles", ascending=False).reset_index(drop=True)

    impact = (
        exploded.groupby("Country_Exploded")
        .agg(MNCS=("MNCS", "mean"), Total_Citations=("Cited by", "sum"))
        .reset_index()
        .rename(columns={"Country_Exploded": "Country"})
    )
    country_stats = collaboration.merge(impact, on="Country", how="left")
    country_stats["MNCS"] = country_stats["MNCS"].fillna(0)
    country_stats["Total_Citations"] = country_stats["Total_Citations"].fillna(0)

    total_countries = len(collaboration)
    total_documents = len(collaboration_data)
    top_volume = collaboration.head(max(1, int(collaboration_top_n))).copy()
    significant = country_stats[country_stats["Articles"] >= max(1, int(min_papers))].copy()
    top_impact = significant.sort_values("MNCS", ascending=False).head(max(1, int(impact_top_n))).copy()
    if significant.empty:
        warnings.append(
            f"No country met the minimum of {int(min_papers)} articles; the country impact figure was skipped."
        )

    # Plot A: exact notebook collaboration pattern styling.
    plot_a = top_volume.sort_values("Articles", ascending=True)
    fig_a, ax = plt.subplots(figsize=(12, 8))
    cividis_gold = plt.cm.cividis(0.95)
    cividis_blue = plt.cm.cividis(0.0)
    ax.barh(plot_a["Country"], plot_a["SCP"], label="Single-Country (SCP)", color=cividis_gold)
    ax.barh(
        plot_a["Country"], plot_a["MCP"], left=plot_a["SCP"],
        label="Multi-Country (MCP)", color=cividis_blue,
    )
    for i, row in enumerate(plot_a.itertuples()):
        ax.annotate(
            f" {row.Articles}", xy=(row.Articles, i), ha="left", va="center",
            fontsize=10, fontweight="bold", color="#333333",
        )
        if row.MCP > row.Articles * 0.10:
            ax.annotate(
                f"{row.MCP / row.Articles * 100:.0f}%", xy=(row.SCP + row.MCP / 2, i),
                ha="center", va="center", color="white", fontsize=9, fontweight="bold",
            )
    ax.set_title(
        f"Country Production: Domestic (SCP) vs. International (MCP)\n"
        f"(Top {len(top_volume)} of $N={total_countries}$ Active Countries)",
        fontweight="bold", pad=20,
    )
    ax.set_xlabel("Number of Article Appearances")
    ax.legend(loc="lower right", frameon=True, facecolor="white", framealpha=1)
    ax.spines[["top", "right"]].set_visible(False)
    fig_a.tight_layout()

    figures = {"top_10_countries_collaboration": fig_a}

    # Plot B: exact notebook quantity-versus-MNCS panel styling.
    if not top_impact.empty:
        plot_b = top_impact.sort_values("MNCS", ascending=True)
        fig_b, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), sharey=True)
        ax1.barh(plot_b["Country"], plot_b["Articles"], color="#555555")
        ax1.set_xlabel("Total Publications")
        ax1.set_title("Quantity (Volume)", fontweight="bold")
        ax1.grid(axis="x", linestyle="--", alpha=0.5)
        ax1.invert_xaxis()
        ax1.spines[["top", "left"]].set_visible(False)
        max_volume = plot_b["Articles"].max()
        ax1.set_xlim(max_volume * 1.2, 0)
        for i, value in enumerate(plot_b["Articles"]):
            ax1.text(value, i, f" {value}", color="black", va="center", ha="right", fontsize=9, fontweight="bold")

        minimum_mncs, maximum_mncs = plot_b["MNCS"].min(), plot_b["MNCS"].max()
        if minimum_mncs == maximum_mncs:
            norm = plt.Normalize(vmin=minimum_mncs, vmax=maximum_mncs + 1e-9)
        else:
            norm = plt.Normalize(vmin=minimum_mncs, vmax=maximum_mncs)
        colors = [plt.cm.cividis(norm(value)) for value in plot_b["MNCS"]]
        ax2.barh(plot_b["Country"], plot_b["MNCS"], color=colors)
        ax2.axvline(x=1.0, color="black", linestyle="--", linewidth=1.5)
        ax2.text(1.05, -1, "Global Avg (1.0)", color="black", fontsize=10, fontweight="bold")
        ax2.set_xlabel("Mean Normalized Citation Score (MNCS)")
        ax2.set_title("Quality (Field-Normalized Impact)", fontweight="bold")
        ax2.grid(axis="x", linestyle="--", alpha=0.5)
        ax2.spines[["top", "right", "left"]].set_visible(False)
        ax2.tick_params(left=False)
        for i, value in enumerate(plot_b["MNCS"]):
            ax2.text(value + 0.05, i, f"{value:.2f}", color="black", va="center", fontsize=9, fontweight="bold")
        fig_b.suptitle(
            f"Country Performance: High-Impact Leaders\n"
            f"(Top {len(top_impact)} by MNCS, Min. {int(min_papers)} Articles, "
            f"Analysis of $N={total_documents}$ Documents)",
            fontsize=16, y=1.02, fontweight="bold",
        )
        fig_b.tight_layout()
        figures["country_impact_comparison"] = fig_b

    tables = {
        "country_classification_summary": classification_summary,
        "country_collaboration_summary": collaboration,
        "country_master_stats": country_stats,
        "top_countries_by_volume": top_volume,
        "top_countries_by_mncs": top_impact,
        "mncs_yearly_baselines": baselines,
    }
    return {
        "data": enriched,
        "exploded_countries": exploded,
        "tables": tables,
        "figures": figures,
        "warnings": list(dict.fromkeys(warnings)),
        "metadata": {
            "articles_total": len(enriched),
            "articles_analyzed": total_documents,
            "unknown_articles": unknown_count,
            "active_countries": total_countries,
            "scp_articles": int(counts["SCP"]),
            "mcp_articles": int(counts["MCP"]),
        },
        "config": {
            "collaboration_top_n": int(collaboration_top_n),
            "impact_top_n": int(impact_top_n),
            "min_papers": int(min_papers),
            "exclude_unknown": bool(exclude_unknown),
        },
    }


def _frequency_table(series: pd.Series, item_column: str, top_n: int) -> pd.DataFrame:
    """Convert cleaned values into a ranked frequency table."""
    clean = series.dropna().astype(str).str.strip()
    clean = clean[(clean != "") & (clean.str.lower() != "nan")]
    counts = clean.value_counts().head(top_n)
    return counts.rename_axis(item_column).reset_index(name="Count")


def _country_palette(number_of_colors: int):
    """Use the notebook HUSL palette, with its documented Cividis fallback."""
    if sns is not None:
        return sns.color_palette("husl", n_colors=number_of_colors)
    return plt.cm.cividis(np.linspace(0, 0.9, number_of_colors))


def country_case_study_analysis(
    data: pd.DataFrame,
    exploded_countries: pd.DataFrame,
    country_stats: pd.DataFrame,
    country_name: str,
    affiliations: pd.DataFrame | None = None,
) -> dict:
    """Create the notebook's country dashboard and detailed statistical field guide."""
    if not country_name or country_name not in set(country_stats["Country"]):
        matches = [
            country for country in country_stats["Country"].astype(str)
            if str(country_name).lower() in country.lower()
        ]
        suggestion = f" Possible matches: {', '.join(matches[:10])}." if matches else ""
        raise ValueError(f"Country '{country_name}' was not found.{suggestion}")
    if "Publication Year" not in data.columns:
        raise ValueError("Publication Year is required for the country temporal dashboard.")

    configure_publication_style()
    frame = data.copy()
    frame["Publication Year"] = pd.to_numeric(frame["Publication Year"], errors="coerce")
    if "Cited by" not in frame.columns:
        frame["Cited by"] = 0
    frame["Cited by"] = pd.to_numeric(frame["Cited by"], errors="coerce").fillna(0)
    if "Countries_Extracted_List" not in frame.columns:
        frame["Countries_Extracted_List"] = frame["Countries_Extracted"].apply(ensure_country_list)
    else:
        frame["Countries_Extracted_List"] = frame["Countries_Extracted_List"].apply(ensure_country_list)

    exploded = exploded_countries.copy()
    exploded["Publication Year"] = pd.to_numeric(exploded["Publication Year"], errors="coerce")
    exploded = exploded.dropna(subset=["Publication Year", "Country_Exploded"])
    exploded["Publication Year"] = exploded["Publication Year"].astype(int)
    country_data = exploded[exploded["Country_Exploded"] == country_name]
    if country_data.empty:
        raise ValueError(f"No publications were found for {country_name}.")

    publications_per_year = (
        exploded.groupby(["Publication Year", "Country_Exploded"]).size()
        .reset_index(name="Publications")
    )
    publications_pivot = publications_per_year.pivot(
        index="Publication Year", columns="Country_Exploded", values="Publications"
    ).fillna(0).sort_index()
    country_totals = country_stats.set_index("Country")["Articles"].astype(int)
    q1, q2, q3 = country_totals.quantile([0.25, 0.50, 0.75])

    def categorize(count):
        if count < q1:
            return "Category 1: Very Low Activity"
        if q1 <= count < q2:
            return "Category 2: Low/Moderate Activity"
        if q2 <= count < q3:
            return "Category 3: Moderate/High Activity"
        return "Category 4: Very High Activity"

    country_categories = country_totals.apply(categorize)
    country_category = country_categories.loc[country_name]
    category_table = pd.DataFrame({
        "Country": country_totals.index,
        "Total Articles": country_totals.values,
        "Productivity Category": country_categories.values,
    }).sort_values("Total Articles", ascending=False).reset_index(drop=True)
    country_timeline = (
        country_data.groupby("Publication Year").size().reset_index(name="Publications")
        .sort_values("Publication Year")
    )

    # Exact 2x2 notebook dashboard.
    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    ax1, ax2, ax3, ax4 = axes.flatten()
    ax1.plot(
        country_timeline["Publication Year"], country_timeline["Publications"],
        marker="o", linewidth=3, markersize=8, color="red", label=country_name,
    )
    for _, row in country_timeline.iterrows():
        ax1.annotate(
            f"{int(row['Publications'])}", (row["Publication Year"], row["Publications"]),
            textcoords="offset points", xytext=(0, 10), ha="center",
            fontsize=10, fontweight="bold", color="darkred",
        )
    ax1.set_title(f"{country_name} Publications Over Time", fontsize=14, fontweight="bold")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Number of Publications")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend()
    ax1.set_ylim(bottom=0)

    peers = country_categories[country_categories == country_category].index
    peer_countries = [country for country in peers if country in publications_pivot.columns]
    if peer_countries:
        peer_data = publications_pivot[peer_countries]
        colors = _country_palette(len(peer_data.columns))
        for i, country in enumerate(peer_data.columns):
            if country == country_name:
                ax2.plot(
                    peer_data.index, peer_data[country], marker="o", linewidth=3,
                    markersize=8, label=country, color="red", zorder=10,
                )
            else:
                ax2.plot(
                    peer_data.index, peer_data[country], marker="o", linewidth=1,
                    markersize=4, label=country, color=colors[i], alpha=0.7,
                )
        ax2.set_title(f"{country_name} vs Peers ({country_category})", fontsize=14, fontweight="bold")
        ax2.set_xlabel("Year")
        ax2.set_ylabel("Number of Publications")
        ax2.grid(True, linestyle="--", alpha=0.5)
        if len(peer_countries) <= 20:
            ax2.legend(fontsize=8, bbox_to_anchor=(1.05, 1), loc="upper left")

    top_ten = country_totals.nlargest(10).index
    leaders = [country for country in top_ten if country in publications_pivot.columns]
    if leaders:
        leader_data = publications_pivot[leaders]
        colors = _country_palette(len(leader_data.columns))
        for i, country in enumerate(leader_data.columns):
            ax3.plot(
                leader_data.index, leader_data[country], marker="o", linewidth=2,
                markersize=5, label=country, color=colors[i], alpha=0.8,
            )
        if country_name not in top_ten and country_name in publications_pivot.columns:
            ax3.plot(
                publications_pivot.index, publications_pivot[country_name], marker="o",
                linewidth=3, markersize=8, label=f"{country_name} (Not Top 10)",
                color="red", zorder=10,
            )
        ax3.set_title(f"{country_name} vs Top 10 Most Active Countries", fontsize=14, fontweight="bold")
        ax3.set_xlabel("Year")
        ax3.set_ylabel("Number of Publications (Log Scale)")
        ax3.grid(True, linestyle="--", alpha=0.5)
        ax3.set_yscale("log")
        ax3.legend(fontsize=8, bbox_to_anchor=(1.05, 1), loc="upper left")

    yearly_rankings = []
    for year in publications_pivot.index:
        year_data = publications_pivot.loc[year].sort_values(ascending=False)
        try:
            rank = list(year_data.index).index(country_name) + 1
            yearly_rankings.append({"Year": year, "Rank": rank})
        except ValueError:
            yearly_rankings.append({"Year": year, "Rank": np.nan})
    ranking = pd.DataFrame(yearly_rankings).dropna()
    if not ranking.empty:
        ax4.plot(ranking["Year"], ranking["Rank"], marker="o", linewidth=3, markersize=8, color="red")
        for row in ranking.itertuples():
            ax4.annotate(
                f"#{int(row.Rank)}", (row.Year, row.Rank), textcoords="offset points",
                xytext=(0, 10), ha="center", fontsize=10, fontweight="bold", color="darkred",
            )
        ax4.set_title(f"{country_name}'s Global Rank Over Time", fontsize=14, fontweight="bold")
        ax4.set_xlabel("Year")
        ax4.set_ylabel("Ranking (1 = Most Publications)")
        ax4.grid(True, linestyle="--", alpha=0.5)
        ax4.invert_yaxis()
    fig.suptitle(
        f"{country_name}'s Contribution and Collaboration Analysis: A Temporal Deep Dive",
        fontsize=18, fontweight="bold", y=1.02,
    )
    fig.tight_layout()

    country_mask = frame["Countries_Extracted_List"].apply(
        lambda countries: country_name in {str(country).strip() for country in countries}
    )
    country_papers = frame[country_mask].copy()
    warnings: list[str] = []
    total_papers = len(country_papers)

    if "Database" in country_papers.columns:
        database = _frequency_table(country_papers["Database"], "Database", 100)
        database["Percentage"] = database["Count"] / max(1, total_papers) * 100
    else:
        database = pd.DataFrame(columns=["Database", "Count", "Percentage"])
        warnings.append("Database provenance was unavailable for this country report.")

    journal_column = "OriginalTitle" if "OriginalTitle" in country_papers.columns else "Source Title"
    journals = (
        _frequency_table(country_papers[journal_column], "Journal / Source", 10)
        if journal_column in country_papers.columns else pd.DataFrame(columns=["Journal / Source", "Count"])
    )
    if journal_column != "OriginalTitle":
        warnings.append("OriginalTitle was unavailable; Source Title was used for the venue ranking.")

    if "Document Type" in country_papers.columns:
        doc_values = country_papers["Document Type"].fillna("Missing/Incomplete data").astype(str).str.split("; ").explode()
        doc_types = doc_values.apply(normalize_doc_type).value_counts().rename_axis("Document Type").reset_index(name="Count")
        doc_types["Percentage of Papers"] = doc_types["Count"] / max(1, total_papers) * 100
    else:
        doc_types = pd.DataFrame(columns=["Document Type", "Count", "Percentage of Papers"])
    conferences = (
        _frequency_table(country_papers["Conference Title"], "Conference", 10)
        if "Conference Title" in country_papers.columns else pd.DataFrame(columns=["Conference", "Count"])
    )

    if (
        affiliations is not None and not affiliations.empty
        and {"Country_Standardized", "Institution_Extracted"}.issubset(affiliations.columns)
    ):
        country_affiliations = affiliations[affiliations["Country_Standardized"] == country_name]
        institutions = _frequency_table(country_affiliations["Institution_Extracted"], "Institution", 15)
        institution_basis = "Affiliation occurrences"
    elif "Institutions_Extracted" in country_papers.columns:
        institution_values = country_papers["Institutions_Extracted"].apply(ensure_country_list).explode()
        institutions = _frequency_table(institution_values, "Institution", 15)
        institution_basis = "Article-level institution appearances"
        warnings.append(
            "The exploded affiliation table was unavailable; institution counts use article-level institution appearances."
        )
    else:
        institutions = pd.DataFrame(columns=["Institution", "Count"])
        institution_basis = "Unavailable"
        warnings.append("Institution metadata was unavailable for this country report.")
    if not institutions.empty:
        institutions.insert(2, "Counting Basis", institution_basis)

    partners = country_papers["Countries_Extracted_List"].explode().dropna().astype(str).str.strip()
    partners = partners[partners != country_name]
    collaborators = _frequency_table(partners, "Partner Country", 15)
    keywords = (
        _frequency_table(
            country_papers["Author Keywords"].dropna().astype(str).str.split(";").explode().str.lower(),
            "Author Keyword", 20,
        ) if "Author Keywords" in country_papers.columns else pd.DataFrame(columns=["Author Keyword", "Count"])
    )
    funding = (
        _frequency_table(
            country_papers["Funding Orgs"].dropna().astype(str).str.split(";").explode(),
            "Funding Organization", 10,
        ) if "Funding Orgs" in country_papers.columns else pd.DataFrame(columns=["Funding Organization", "Count"])
    )
    funded_papers = int(country_papers["Funding Orgs"].notna().sum()) if "Funding Orgs" in country_papers else 0
    yearly_report = (
        country_papers.dropna(subset=["Publication Year"])
        .groupby("Publication Year")
        .agg(Papers=("Publication Year", "size"), Citations_Sum=("Cited by", "sum"))
        .reset_index()
    )
    yearly_report["Avg Cites per Paper"] = (
        yearly_report["Citations_Sum"] / yearly_report["Papers"].replace(0, np.nan)
    ).round(2)

    overall_rank = list(country_totals.sort_values(ascending=False).index).index(country_name) + 1
    peak = country_timeline.loc[country_timeline["Publications"].idxmax()]
    summary = pd.DataFrame([
        ("Country", country_name),
        ("Total publications (appearances)", int(country_totals.loc[country_name])),
        ("Unique papers", total_papers),
        ("Productivity category", country_category),
        ("Overall productivity rank", f"#{overall_rank} of {len(country_totals)}"),
        ("Active publication years", f"{int(country_timeline['Publication Year'].min())}–{int(country_timeline['Publication Year'].max())}"),
        ("Peak year", f"{int(peak['Publication Year'])} ({int(peak['Publications'])} publications)"),
        ("Average publications per active year", round(country_timeline["Publications"].mean(), 2)),
        ("Papers with funding information", funded_papers),
        ("Funding-information coverage", f"{funded_papers / max(1, total_papers):.1%}"),
    ], columns=["Measure", "Value"])

    tables = {
        "country_case_summary": summary,
        "country_publication_timeline": country_timeline,
        "country_rank_evolution": ranking,
        "country_productivity_categories": category_table,
        "database_provenance": database,
        "top_journals": journals,
        "document_types": doc_types,
        "top_conferences": conferences,
        "top_institutions": institutions,
        "collaboration_partners": collaborators,
        "author_keywords": keywords,
        "funding_organizations": funding,
        "yearly_statistical_summary": yearly_report,
    }
    report_parts = [f"COUNTRY CASE STUDY: {country_name.upper()}", "", summary.to_string(index=False)]
    report_titles = {
        "database_provenance": "DATABASE PROVENANCE",
        "top_journals": "TOP JOURNALS / SOURCES",
        "document_types": "DOCUMENT TYPES",
        "top_conferences": "CONFERENCE PARTICIPATION",
        "top_institutions": "TOP AFFILIATED INSTITUTIONS",
        "collaboration_partners": "INTERNATIONAL COLLABORATION PARTNERS",
        "author_keywords": "AUTHOR KEYWORDS",
        "funding_organizations": "FUNDING ORGANIZATIONS",
        "yearly_statistical_summary": "YEAR-BY-YEAR SUMMARY",
    }
    for key, title in report_titles.items():
        report_parts.extend(["", title, "-" * len(title), tables[key].to_string(index=False)])
    safe_name = re.sub(r"[^\w\-]+", "_", country_name).strip("_") or "Country"
    return {
        "country": country_name,
        "safe_country_name": safe_name,
        "figure": fig,
        "tables": tables,
        "report_text": "\n".join(report_parts),
        "warnings": warnings,
        "metadata": {
            "total_publication_appearances": int(country_totals.loc[country_name]),
            "unique_papers": total_papers,
            "category": country_category,
            "overall_rank": overall_rank,
            "total_countries": len(country_totals),
        },
    }
