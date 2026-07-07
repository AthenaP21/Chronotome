"""Publication-style Matplotlib figures for Chronotome results."""

from __future__ import annotations

import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd


def _finish(fig, title=None):
    if title:
        fig.suptitle(title, fontweight="bold")
    fig.tight_layout()
    return fig


def barh(table, label, value, title, xlabel):
    """Create a notebook-style horizontal ranking plot."""
    plot = table.dropna(subset=[label, value]).head(15).sort_values(value)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(plot[label].astype(str), plot[value], color="#333333")
    ax.set(xlabel=xlabel, title=title)
    ax.spines[["top", "right", "left"]].set_visible(False)
    return _finish(fig)


def annual_plot(table: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(table["Publication Year"], table["Count"], marker="o", color=plt.cm.cividis(0.15), linewidth=2)
    if len(table) > 1:
        fit = np.polyfit(table["Publication Year"], table["Count"], 1)
        ax.plot(table["Publication Year"], np.polyval(fit, table["Publication Year"]), "--", color="#666666", label="Linear trend")
        ax.legend()
    ax.set(title="Annual Scientific Production", xlabel="Publication Year", ylabel="Documents")
    return _finish(fig)


def citation_plot(table: pd.DataFrame):
    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax2 = ax1.twinx()
    ax1.plot(table["Publication Year"], table["Mean_Total_Citations"], color="#333333", marker="o")
    ax2.plot(table["Publication Year"], table["Mean_Annualized_Citations"], color=plt.cm.cividis(0.8), marker="s")
    ax1.set(xlabel="Publication Year", ylabel="Mean Total Citations", title="Citation Dynamics: Accumulation and Velocity")
    ax2.set_ylabel("Mean Annualized Citations")
    return _finish(fig)


def author_impact_plot(authors: pd.DataFrame, top_n=10):
    plot = authors.sort_values(["Fractional_Credit", "Avg_MNCS"], ascending=False).head(top_n).sort_values("Fractional_Credit")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    ax1.barh(plot["Author"], plot["Fractional_Credit"], color="#333333")
    ax1.set(xlabel="Fractionalized Credit", title="Contribution (adjusted for team size)")
    ax2.hlines(plot["Author"], 0, plot["Avg_MNCS"], color="gray")
    ax2.plot(plot["Avg_MNCS"], plot["Author"], "o", color=plt.cm.cividis(0.1))
    ax2.axvline(1, color="black", linestyle="--")
    ax2.set(xlabel="Mean Normalized Citation Score", title="Normalized Citation Impact")
    return _finish(fig, "Author Performance")


def source_panel(sources: pd.DataFrame):
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    specs = [("Number_of_Publications", "Most Productive Sources"), ("h_index", "Highest Local H-Index"),
             ("g_index", "Highest Local G-Index"), ("m_index", "Highest Local M-Index")]
    for ax, (metric, title) in zip(axes.flat, specs):
        plot = sources.nlargest(10, metric).sort_values(metric)
        labels = plot["OriginalTitle"].astype(str).apply(lambda x: textwrap.shorten(x, 42, placeholder="…"))
        ax.barh(labels, plot[metric], color="#333333")
        ax.set_title(title)
        ax.spines[["top", "right", "left"]].set_visible(False)
    return _finish(fig, "Descriptive Bibliometric Indicators: Top Sources")


def country_collaboration_plot(countries: pd.DataFrame):
    plot = countries.head(10).sort_values("Articles")
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(plot["Country"], plot["SCP"], label="Single-Country (SCP)", color=plt.cm.cividis(0.9))
    ax.barh(plot["Country"], plot["MCP"], left=plot["SCP"], label="Multi-Country (MCP)", color=plt.cm.cividis(0.1))
    ax.set(title="Country Production: Domestic vs. International", xlabel="Article Appearances")
    ax.legend()
    return _finish(fig)


def country_impact_plot(countries: pd.DataFrame, min_papers=5):
    plot = countries[countries["Articles"] >= min_papers].nlargest(15, "MNCS").sort_values("MNCS")
    fig, ax = plt.subplots(figsize=(10, 7))
    if not plot.empty:
        colors = plt.cm.cividis(np.linspace(0.1, 0.9, len(plot)))
        ax.barh(plot["Country"], plot["MNCS"], color=colors)
    ax.axvline(1, color="black", linestyle="--", label="Corpus average")
    ax.set(title=f"Country Impact (minimum {min_papers} papers)", xlabel="MNCS")
    ax.legend()
    return _finish(fig)


def bradford_plot(table: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(table["Rank"], table["Cumulative_Articles"], color="#333333", linewidth=2)
    ax.set_xscale("log")
    for boundary in (1, 2):
        rows = table[table["Zone"] == boundary]
        if not rows.empty:
            row = rows.iloc[-1]
            ax.axvline(row["Rank"], color="#777777", linestyle="--")
            ax.axhline(row["Cumulative_Articles"], color="#777777", linestyle="--")
    ax.set(title="Bradford's Law of Scattering", xlabel="Source Rank (log scale)", ylabel="Cumulative Articles")
    return _finish(fig)


def team_size_plot(table: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 6))
    values = table["Average_Citations"].fillna(0)
    ax.bar(table["Team Size"], values, color=plt.cm.cividis(np.linspace(0.1, 0.9, len(table))))
    ax.set(title="Impact of Team Size on Citation Performance", xlabel="Number of Authors", ylabel="Average Citations")
    return _finish(fig)


def institution_network_plot(network: dict, top_n=30, title="Institutional Collaboration Network"):
    graph, ranking = network["graph"], network["ranking"]
    nodes = [node for node in ranking.head(top_n)["Institution"] if node in graph]
    subgraph = graph.subgraph(nodes).copy()
    subgraph.remove_nodes_from(list(nx.isolates(subgraph)))
    fig, ax = plt.subplots(figsize=(14, 12))
    if subgraph.number_of_nodes():
        position = nx.spring_layout(subgraph, seed=42, weight="weight", iterations=100)
        degrees = dict(subgraph.degree(weight="weight"))
        sizes = [100 + 35 * np.sqrt(degrees[node]) for node in subgraph]
        weights = [0.3 + subgraph[u][v].get("weight", 1) for u, v in subgraph.edges]
        nx.draw_networkx_edges(subgraph, position, width=weights, alpha=0.18, ax=ax)
        nx.draw_networkx_nodes(subgraph, position, node_size=sizes, node_color=list(degrees.values()), cmap="cividis", ax=ax)
        nx.draw_networkx_labels(subgraph, position, font_size=7, ax=ax)
    ax.set_title(f"{title}\n({subgraph.number_of_nodes()} institutions, {subgraph.number_of_edges()} links)")
    ax.axis("off")
    return _finish(fig)


def topic_evolution_plot(table: pd.DataFrame):
    pivot = table.pivot(index="Publication Year", columns="Dominant_Topic", values="Articles").fillna(0)
    fig, ax = plt.subplots(figsize=(12, 7))
    pivot.plot(ax=ax, colormap="cividis", marker="o")
    ax.set(title="Topic Publication Trends", ylabel="Articles")
    return _finish(fig)


def build_figures(tables: dict[str, pd.DataFrame], networks: dict, config: dict) -> dict:
    """Build all figures whose required result tables are available."""
    figures = {}
    if not tables["document_types"].empty:
        figures["document_types"] = barh(tables["document_types"], "Document Type", "Count", "Structural Morphology: Document Types", "Documents")
    if not tables["annual_production"].empty:
        figures["annual_scientific_production"] = annual_plot(tables["annual_production"])
    if not tables["citation_dynamics"].empty:
        figures["citation_dynamics"] = citation_plot(tables["citation_dynamics"])
    if not tables["author_metrics"].empty:
        figures["author_impact"] = author_impact_plot(tables["author_metrics"], config.get("top_n", 10))
    if not tables["source_metrics"].empty:
        figures["source_rankings"] = source_panel(tables["source_metrics"])
    if not tables["country_metrics"].empty:
        figures["country_collaboration"] = country_collaboration_plot(tables["country_metrics"])
        figures["country_impact"] = country_impact_plot(tables["country_metrics"], config.get("min_papers", 5))
    if not tables["bradford"].empty:
        figures["bradford_scattering"] = bradford_plot(tables["bradford"])
    if not tables["team_size_impact"].empty:
        figures["team_size_impact"] = team_size_plot(tables["team_size_impact"])
    for key in ("Global_All", "Global_MCP", "EU_All"):
        if key in networks and networks[key]["graph"].number_of_edges():
            figures[f"institution_network_{key.lower()}"] = institution_network_plot(
                networks[key], config.get("network_top_n", 30), key.replace("_", " ")
            )
    if "topic_evolution" in tables and not tables["topic_evolution"].empty:
        figures["topic_evolution"] = topic_evolution_plot(tables["topic_evolution"])
    return figures
