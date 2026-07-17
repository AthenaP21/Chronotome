"""Notebook-faithful institutional productivity and collaboration analysis."""

from __future__ import annotations

import ast
import re
import textwrap
from collections import Counter
from itertools import combinations

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from mpl_toolkits.axes_grid1 import make_axes_locatable

from .entity_resolution import canonicalize_country_name

try:
    import seaborn as sns
except ImportError:  # pragma: no cover - matplotlib fallback is exercised instead
    sns = None

try:
    from adjustText import adjust_text
    ADJUST_TEXT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    adjust_text = None
    ADJUST_TEXT_AVAILABLE = False


EU27_COUNTRIES = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary",
    "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta",
    "Netherlands", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia",
    "Spain", "Sweden",
}

ANALYSIS_CONFIGS = {
    "Global_All": {"network_type": "Global", "publication_type": "All", "is_eu": False},
    "Global_MCP": {"network_type": "Global", "publication_type": "MCP", "is_eu": False},
    "Global_SCP": {"network_type": "Global", "publication_type": "SCP", "is_eu": False},
    "EU_All": {"network_type": "EU", "publication_type": "All", "is_eu": True},
    "EU_MCP": {"network_type": "EU", "publication_type": "MCP", "is_eu": True},
    "EU_SCP": {"network_type": "EU", "publication_type": "SCP", "is_eu": True},
}


def ensure_list(value) -> list:
    """Parse a list-valued dataframe cell without treating plain text as a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set, np.ndarray, pd.Series)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return []
        return list(parsed) if isinstance(parsed, (list, tuple, set)) else []
    return []


def _clean_institution(value) -> str:
    if pd.isna(value):
        return ""
    text = " ".join(str(value).strip().split())
    if not text or text.lower() in {"nan", "none", "missing/incomplete institution data"}:
        return ""
    return text


def _country_classification(countries: list) -> str:
    clean = {str(country).strip() for country in countries if str(country).strip()}
    if len(clean) == 1:
        return "SCP"
    if len(clean) > 1:
        return "MCP"
    return "Unknown"


def prepare_institutional_dataset(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalize list columns and recreate safe geographic handoff fields when needed."""
    frame = data.copy().reset_index(drop=True)
    warnings: list[str] = []
    if "Institutions_Extracted" not in frame.columns:
        raise ValueError(
            "The institutional handoff dataset must contain `Institutions_Extracted` "
            "(the geographic export retains this column)."
        )
    frame["Institutions_Extracted"] = frame["Institutions_Extracted"].apply(
        lambda values: list(dict.fromkeys(filter(None, (_clean_institution(v) for v in ensure_list(values)))))
    )

    if "Countries_Extracted" not in frame.columns:
        frame["Countries_Extracted_List"] = [[] for _ in range(len(frame))]
        warnings.append("Country lists were unavailable; EU filtering will yield no records.")
    else:
        frame["Countries_Extracted_List"] = frame["Countries_Extracted"].apply(
            lambda values: list(dict.fromkeys(
                canonical for canonical in
                (canonicalize_country_name(value) for value in ensure_list(values))
                if canonical
            ))
        )
    frame["Countries_Extracted"] = frame["Countries_Extracted_List"]
    frame["Country_Classification"] = frame["Countries_Extracted_List"].apply(_country_classification)
    frame["Publication_ID"] = np.arange(1, len(frame) + 1)
    return frame, warnings


def is_exclusively_eu(countries: list) -> bool:
    clean = [
        canonical for canonical in
        (canonicalize_country_name(country) for country in ensure_list(countries))
        if canonical
    ]
    return bool(clean) and all(country in EU27_COUNTRIES for country in clean)


def _filter_analysis(frame: pd.DataFrame, analysis_name: str) -> pd.DataFrame:
    if analysis_name not in ANALYSIS_CONFIGS:
        raise ValueError(f"Unknown institutional analysis: {analysis_name}")
    config = ANALYSIS_CONFIGS[analysis_name]
    filtered = frame.copy()
    if config["publication_type"] in {"MCP", "SCP"}:
        filtered = filtered[filtered["Country_Classification"] == config["publication_type"]].copy()
    if config["is_eu"]:
        filtered = filtered[filtered["Countries_Extracted_List"].apply(is_exclusively_eu)].copy()
    return filtered


def _institution_ranking(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    exploded = frame[["Publication_ID", "Institutions_Extracted"]].explode("Institutions_Extracted")
    exploded = exploded.rename(columns={"Institutions_Extracted": "Institution"})
    exploded["Institution"] = exploded["Institution"].apply(_clean_institution)
    exploded = exploded[exploded["Institution"] != ""].copy()
    ranking = exploded["Institution"].value_counts().rename_axis("Institution").reset_index(
        name="Number_of_Publications"
    )
    return ranking, exploded


def _collaboration_graph(frame: pd.DataFrame, max_institutions_per_paper: int):
    pair_counter: Counter = Counter()
    excluded = 0
    eligible = 0
    for values in frame["Institutions_Extracted"]:
        institutions = sorted(set(filter(None, (_clean_institution(v) for v in ensure_list(values)))))
        if len(institutions) > int(max_institutions_per_paper):
            excluded += 1
            continue
        if len(institutions) >= 2:
            eligible += 1
            pair_counter.update(combinations(institutions, 2))
    graph = nx.Graph()
    rows = []
    for (first, second), weight in pair_counter.items():
        graph.add_edge(first, second, weight=int(weight))
        rows.append({
            "Institution_Pair": f"{first} | {second}", "Institution1": first,
            "Institution2": second, "Collaboration_Count": int(weight),
        })
    pairs = pd.DataFrame(rows, columns=[
        "Institution_Pair", "Institution1", "Institution2", "Collaboration_Count"
    ])
    if not pairs.empty:
        pairs = pairs.sort_values(
            ["Collaboration_Count", "Institution1", "Institution2"],
            ascending=[False, True, True],
        ).reset_index(drop=True)
    return graph, pairs, excluded, eligible


def _network_tables(graph: nx.Graph, ranking: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    productivity = ranking.set_index("Institution")["Number_of_Publications"].to_dict()
    degree_centrality = nx.degree_centrality(graph) if graph.number_of_nodes() else {}
    if 0 < graph.number_of_nodes() <= 1000:
        betweenness = nx.betweenness_centrality(graph, weight="weight")
    else:
        betweenness = {}
    nodes = pd.DataFrame([{
        "Id": node, "Label": node, "Degree": graph.degree(node),
        "Weighted_Degree": graph.degree(node, weight="weight"),
        "Degree_Centrality": degree_centrality.get(node, 0.0),
        "Betweenness_Centrality": betweenness.get(node, np.nan),
        "Productivity": int(productivity.get(node, 0)),
    } for node in graph.nodes()])
    if not nodes.empty:
        nodes = nodes.sort_values(["Weighted_Degree", "Label"], ascending=[False, True]).reset_index(drop=True)
    edges = pd.DataFrame([{
        "Source": first, "Target": second, "Weight": int(attributes.get("weight", 1))
    } for first, second, attributes in graph.edges(data=True)])
    if not edges.empty:
        edges = edges.sort_values(["Weight", "Source", "Target"], ascending=[False, True, True]).reset_index(drop=True)
    return nodes, edges


def _configure_style():
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "figure.dpi": 200, "savefig.dpi": 600, "font.family": "DejaVu Sans",
        "font.size": 11, "axes.titlesize": 14, "axes.labelsize": 12,
        "xtick.labelsize": 10, "ytick.labelsize": 10,
    })


def _top_institutions_figure(ranking: pd.DataFrame, analysis_name: str, total_articles: int):
    if ranking.empty:
        return None
    _configure_style()
    plot_data = ranking.head(10)
    figure, axis = plt.subplots(figsize=(10, 6))
    if sns is not None:
        sns.barplot(
            data=plot_data, x="Number_of_Publications", y="Institution",
            hue="Institution", palette="cividis", legend=False, ax=axis,
        )
    else:  # pragma: no cover
        colors = plt.cm.cividis(np.linspace(0, 0.9, len(plot_data)))
        axis.barh(plot_data["Institution"], plot_data["Number_of_Publications"], color=colors)
        axis.invert_yaxis()
    axis.set_xlabel("Number of Publications")
    axis.set_ylabel("Institution")
    axis.set_title(
        "Top 10 Institutions by Publication Count\n"
        f"({analysis_name} Level, N={len(ranking)} institutions, "
        f"N={total_articles} articles)", fontsize=14, fontweight="bold", pad=15,
    )
    figure.tight_layout()
    return figure


def _network_figure(graph: nx.Graph, ranking: pd.DataFrame, top_n: int, analysis_name: str):
    if graph.number_of_nodes() == 0 or ranking.empty:
        return None, nx.Graph()
    selected = [node for node in ranking.head(int(top_n))["Institution"] if node in graph]
    subgraph = graph.subgraph(selected).copy()
    subgraph.remove_nodes_from(list(nx.isolates(subgraph)))
    if subgraph.number_of_nodes() == 0:
        return None, subgraph

    _configure_style()
    figure, axis = plt.subplots(figsize=(18, 16))
    positions = nx.spring_layout(subgraph, k=3, scale=2, iterations=50, seed=42, weight="weight")
    centrality = nx.degree_centrality(subgraph)
    minimum, maximum = min(centrality.values()), max(centrality.values())
    norm = mcolors.Normalize(vmin=minimum, vmax=max(minimum + 1e-9, maximum))
    cmap = plt.cm.cividis
    node_colors = [cmap(norm(centrality[node])) for node in subgraph.nodes()]
    weighted_degree = dict(subgraph.degree(weight="weight"))
    node_sizes = [50 + np.sqrt(max(0, weighted_degree.get(node, 0))) * 40 for node in subgraph.nodes()]

    weights = [attributes.get("weight", 1) for _, _, attributes in subgraph.edges(data=True)]
    maximum_weight = max(weights) if weights else 1
    strong = [(u, v) for u, v, d in subgraph.edges(data=True) if d.get("weight", 1) > maximum_weight / 2]
    weak = [(u, v) for u, v, d in subgraph.edges(data=True) if d.get("weight", 1) <= maximum_weight / 2]
    nx.draw_networkx_edges(subgraph, positions, edgelist=weak, width=0.5, edge_color="lightgray", alpha=0.6, ax=axis)
    nx.draw_networkx_edges(subgraph, positions, edgelist=strong, width=1.5, edge_color="#00204d", alpha=0.7, ax=axis)
    nx.draw_networkx_nodes(
        subgraph, positions, node_size=node_sizes, node_color=node_colors,
        alpha=0.9, edgecolors="black", linewidths=0.5, ax=axis,
    )
    if ADJUST_TEXT_AVAILABLE:
        texts = [axis.text(
            positions[node][0], positions[node][1], node, fontsize=9, fontweight="bold",
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=0.1),
        ) for node in subgraph.nodes()]
        adjust_text(texts, ax=axis, arrowprops=dict(arrowstyle="-", color="grey", lw=0.3, alpha=0.5))
    else:
        nx.draw_networkx_labels(
            subgraph, positions, font_size=9,
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=0.1), ax=axis,
        )

    divider = make_axes_locatable(axis)
    color_axis = divider.append_axes("right", size="3%", pad=0.1)
    mapper = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    mapper.set_array([])
    colorbar = figure.colorbar(mapper, cax=color_axis)
    colorbar.set_label("Node Centrality (Degree)", fontsize=12)
    legend = [
        plt.Line2D([0], [0], marker="o", color="w", label="Node Size = Productivity (Pub. Count)",
                   markersize=12, markerfacecolor="lightgrey", markeredgecolor="black", markeredgewidth=0.5),
        plt.Line2D([0], [0], marker="o", color="w", label="High Centrality", markersize=10,
                   markerfacecolor=cmap(1.0), markeredgecolor="black", markeredgewidth=0.5),
        plt.Line2D([0], [0], marker="o", color="w", label="Low Centrality", markersize=10,
                   markerfacecolor=cmap(0.1), markeredgecolor="black", markeredgewidth=0.5),
        plt.Line2D([0], [0], color="#00204d", lw=2, label="Strong Collaboration", alpha=0.7),
        plt.Line2D([0], [0], color="lightgray", lw=1, label="Weak Collaboration", alpha=0.6),
    ]
    axis.legend(handles=legend, loc="upper left", frameon=True, facecolor="white", framealpha=0.8,
                fontsize=12, title="Legend", title_fontsize=13)
    figure.suptitle(
        f"Institutional Collaboration Network ({analysis_name})\n"
        f"(N={subgraph.number_of_nodes()} institutions, N={subgraph.number_of_edges()} links)",
        fontsize=20,
    )
    axis.set_axis_off()
    figure.tight_layout(rect=[0, 0, 1, 0.95])
    return figure, subgraph


def institutional_analysis(
    data: pd.DataFrame, analysis_name: str = "Global_All", top_n_list: int = 1000,
    top_n_plot: int = 30, max_institutions_per_paper: int = 50,
    output_name: str | None = None,
) -> dict:
    """Run one of the six Global/EU × All/MCP/SCP institutional analyses."""
    prepared, warnings = prepare_institutional_dataset(data)
    filtered = _filter_analysis(prepared, analysis_name)
    if filtered.empty:
        raise ValueError(f"No publications remain after applying the `{analysis_name}` filters.")
    output_name = output_name or analysis_name
    ranking, exploded = _institution_ranking(filtered)
    if ranking.empty:
        raise ValueError("No usable institutions were found in the selected publications.")
    graph, pairs, excluded, eligible = _collaboration_graph(filtered, max_institutions_per_paper)
    nodes, edges = _network_tables(graph, ranking)
    top = ranking.head(max(1, int(top_n_list))).copy()
    top_figure = _top_institutions_figure(top, output_name, len(filtered))
    network_figure, subgraph = _network_figure(graph, top, max(2, int(top_n_plot)), output_name)
    if excluded:
        warnings.append(
            f"Excluded {excluded:,} mega-consortium publications with more than "
            f"{int(max_institutions_per_paper)} institutions to prevent edge inflation."
        )
    if graph.number_of_edges() == 0:
        warnings.append("No multi-institution collaboration pairs were available for this filtered corpus.")
    summary = pd.DataFrame([{
        "Analysis": output_name, "Status": "Success", "Articles": len(filtered),
        "Institutions": len(ranking), "Network_Nodes": graph.number_of_nodes(),
        "Network_Edges": graph.number_of_edges(), "Eligible_Collaboration_Papers": eligible,
        "Mega_Consortium_Papers_Excluded": excluded,
        "Top_Institution": ranking.iloc[0]["Institution"],
        "Top_Institution_Publications": int(ranking.iloc[0]["Number_of_Publications"]),
    }])
    figures = {f"Top_10_Institutions_By_Publications_{output_name}": top_figure}
    if network_figure is not None:
        figures[f"Collaboration_Network_Top_{int(top_n_plot)}_{output_name}"] = network_figure
    return {
        "data": filtered, "prepared_data": prepared, "exploded_institutions": exploded,
        "tables": {
            "institution_ranking": ranking, "top_institutions": top,
            "collaboration_counts": pairs, "network_nodes": nodes,
            "network_edges": edges, "analysis_summary": summary,
        },
        "figures": figures, "full_graph": graph, "subgraph": subgraph,
        "warnings": list(dict.fromkeys(warnings)),
        "metadata": {
            "analysis_name": output_name, "filter_name": analysis_name, "articles": len(filtered),
            "institutions": len(ranking), "network_nodes": graph.number_of_nodes(),
            "network_edges": graph.number_of_edges(), "displayed_nodes": subgraph.number_of_nodes(),
            "excluded_large_papers": excluded, "max_institutions_per_paper": int(max_institutions_per_paper),
            "adjust_text_available": ADJUST_TEXT_AVAILABLE,
        },
        "config": {"top_n_list": int(top_n_list), "top_n_plot": int(top_n_plot)},
    }


def institutional_community_visualization(
    institutional_result: dict, top_n_to_plot: int | None = None,
) -> dict:
    """Generate the notebook's advanced Cividis community visualization on demand."""
    graph = institutional_result.get("full_graph")
    ranking = institutional_result.get("tables", {}).get("institution_ranking", pd.DataFrame())
    network_type = institutional_result.get("metadata", {}).get("analysis_name", "Institutional")
    if not isinstance(graph, nx.Graph) or graph.number_of_nodes() == 0:
        raise ValueError("The selected institutional graph is empty.")
    if graph.number_of_edges() == 0:
        raise ValueError("Community visualization requires at least one collaboration link.")
    if ranking.empty or "Institution" not in ranking.columns:
        raise ValueError("The institutional ranking is unavailable.")

    communities = [
        sorted(community) for community in nx.community.louvain_communities(
            graph, weight="weight", seed=42
        ) if len(community) > 1
    ]
    communities = sorted([list(community) for community in communities if community], key=len, reverse=True)
    if not communities:
        raise ValueError("No non-singleton communities were detected in the selected network.")

    if top_n_to_plot is None:
        top_n_to_plot = 50 if network_type.startswith("Global") else 30
    top_n_to_plot = max(2, int(top_n_to_plot))
    nodes_to_plot = [node for node in ranking.head(top_n_to_plot)["Institution"] if node in graph]
    plotted = graph.subgraph(nodes_to_plot).copy()
    plotted.remove_nodes_from(list(nx.isolates(plotted)))
    if plotted.number_of_nodes() == 0:
        raise ValueError("The top-ranked institutions do not form a connected subgraph.")

    valid_nodes = set(plotted.nodes())
    filtered_communities: list[list[str]] = []
    node_to_community: dict[str, int] = {}
    for community in communities:
        present = [node for node in community if node in valid_nodes]
        if present:
            community_id = len(filtered_communities)
            filtered_communities.append(present)
            for node in present:
                node_to_community.setdefault(node, community_id)
    number_of_communities = len(filtered_communities)
    if number_of_communities == 0:
        filtered_communities = [list(plotted.nodes())]
        node_to_community = {node: 0 for node in plotted.nodes()}
        colors = ["#AAAAAA"]
        number_of_communities = 1
    else:
        samples = [0.60] if number_of_communities == 1 else np.linspace(0.10, 0.90, number_of_communities)
        colors = [plt.cm.cividis(value) for value in samples]
    node_colors = [
        colors[node_to_community[node]] if node in node_to_community else "#E0E0E0"
        for node in plotted.nodes()
    ]

    figure_size = (22, 22) if network_type == "Global_All" else (20, 20)
    layout_k_factor = 0.7 if network_type == "Global_All" else 0.8
    figure, axis = plt.subplots(figsize=figure_size, facecolor="white")
    axis.set_facecolor("white")
    k_value = layout_k_factor / np.sqrt(max(1, plotted.number_of_nodes()))
    positions = nx.spring_layout(
        plotted, k=k_value, iterations=75, seed=123, scale=3, weight="weight"
    )
    weighted_degree = dict(graph.degree(weight="weight"))
    maximum_degree = max(weighted_degree.values()) if weighted_degree else 1.0
    node_sizes = [
        40 + (weighted_degree.get(node, 0) / maximum_degree) * 4500
        for node in plotted.nodes()
    ]
    edge_weights = [attributes.get("weight", 1) for _, _, attributes in plotted.edges(data=True)]
    maximum_weight = max(edge_weights) if edge_weights else 1.0
    minimum_weight = min(edge_weights) if edge_weights else 1.0
    intra, inter = [], []
    for first, second in plotted.edges():
        if node_to_community.get(first) is not None and node_to_community.get(first) == node_to_community.get(second):
            intra.append((first, second))
        else:
            inter.append((first, second))
    intra_widths = [0.4 + (plotted[u][v].get("weight", minimum_weight) / maximum_weight) * 2.5 for u, v in intra]
    inter_widths = [0.1 + (plotted[u][v].get("weight", minimum_weight) / maximum_weight) for u, v in inter]
    nx.draw_networkx_edges(plotted, positions, edgelist=inter, width=inter_widths,
                           alpha=0.08, edge_color="#AAAAAA", ax=axis)
    nx.draw_networkx_edges(plotted, positions, edgelist=intra, width=intra_widths,
                           alpha=0.4, edge_color="#333333", ax=axis)
    nx.draw_networkx_nodes(
        plotted, positions, node_color=node_colors, node_size=node_sizes,
        alpha=0.9, edgecolors="#333333", linewidths=0.5, ax=axis,
    )

    # Notebook execution labels every displayed top institution.
    labels = sorted(plotted.nodes(), key=lambda node: weighted_degree.get(node, 0), reverse=True)[:top_n_to_plot]
    if ADJUST_TEXT_AVAILABLE:
        texts = [axis.text(
            positions[node][0], positions[node][1], node, fontsize=8,
            fontfamily="sans-serif", fontweight="normal", color="#333333",
            bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=0.1),
        ) for node in labels]
        adjust_text(texts, ax=axis, arrowprops=dict(arrowstyle="-", color="grey", lw=0.3, alpha=0.5))
    else:
        nx.draw_networkx_labels(
            plotted, positions, labels={node: node for node in labels}, fontsize=8,
            fontfamily="sans-serif", font_weight="normal", font_color="#333333",
            bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=0.1), ax=axis,
        )

    source_label = "Louvain Communities"
    axis.set_title(
        f"{network_type}: {source_label} (Top {top_n_to_plot} Nodes) "
        f"(Top {plotted.number_of_nodes()} Institutions)\n"
        f"{number_of_communities} communities identified in subgraph",
        fontsize=16, y=1.01, fontfamily="sans-serif",
    )
    axis.set_axis_off()
    if 1 < number_of_communities <= 8:
        handles = []
        for community_id, community in enumerate(filtered_communities[:8]):
            top_node = max(community, key=lambda node: weighted_degree.get(node, 0))
            label = f"Comm. {community_id + 1}: {top_node} ({len(community)} nodes)"
            handles.append(plt.Line2D(
                [0], [0], marker="o", color="w", label="\n".join(textwrap.wrap(label, width=30)),
                markerfacecolor=colors[community_id], markersize=9,
            ))
        axis.legend(
            handles=handles, title=f"Top {len(handles)} Communities", loc="upper left",
            bbox_to_anchor=(1.01, 1), fontsize=9,
            title_fontproperties={"weight": "bold", "size": 10}, frameon=True,
            facecolor="white", framealpha=0.9, labelspacing=1.2,
        )
    elif number_of_communities > 8:
        axis.text(
            0.01, 0.01, f"{number_of_communities} communities in subgraph (legend omitted)",
            transform=axis.transAxes, fontsize=9, color="black",
            bbox=dict(facecolor="white", alpha=0.5, pad=0.2),
        )
    figure.tight_layout()

    productivity = ranking.set_index("Institution")["Number_of_Publications"].to_dict()
    membership_rows = []
    for community_id, community in enumerate(communities, 1):
        for node in community:
            membership_rows.append({
                "Institution": node, "Community": community_id,
                "Productivity": int(productivity.get(node, 0)),
                "Weighted_Degree": float(weighted_degree.get(node, 0)),
                "Included_in_Plot": node in valid_nodes,
            })
    membership = pd.DataFrame(membership_rows)
    if not membership.empty:
        membership = membership.sort_values(
            ["Community", "Weighted_Degree", "Institution"], ascending=[True, False, True]
        ).reset_index(drop=True)
    summary_rows = []
    for community_id, community in enumerate(communities, 1):
        leader = max(community, key=lambda node: weighted_degree.get(node, 0))
        summary_rows.append({
            "Community": community_id, "Full_Network_Size": len(community),
            "Displayed_Nodes": len(set(community) & valid_nodes),
            "Leading_Institution": leader,
            "Leader_Weighted_Degree": weighted_degree.get(leader, 0),
        })
    summary = pd.DataFrame(summary_rows)
    safe_suffix = re.sub(r"[^\w\-]+", "_", source_label)
    basename = f"community_plot_filtered_{network_type}_{safe_suffix}"
    return {
        "figure": figure, "basename": basename, "communities": communities,
        "tables": {"community_membership": membership, "community_summary": summary},
        "metadata": {
            "network_type": network_type, "community_source": source_label,
            "communities_full": len(communities), "communities_displayed": number_of_communities,
            "nodes_displayed": plotted.number_of_nodes(), "edges_displayed": plotted.number_of_edges(),
            "top_n": top_n_to_plot,
        },
        "warnings": [] if ADJUST_TEXT_AVAILABLE else [
            "adjustText is unavailable; community labels may overlap slightly."
        ],
    }
