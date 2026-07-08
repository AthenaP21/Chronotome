"""Metric, ranking, thematic, and network computations used by Chronotome."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats


def calculate_h_index(citations) -> int:
    """Calculate the local h-index from citation counts."""
    values = sorted((int(x) for x in pd.to_numeric(pd.Series(citations), errors="coerce").fillna(0)), reverse=True)
    return sum(value >= rank for rank, value in enumerate(values, 1))


def calculate_g_index(citations) -> int:
    """Calculate the local g-index from citation counts."""
    values = sorted((int(x) for x in pd.to_numeric(pd.Series(citations), errors="coerce").fillna(0)), reverse=True)
    cumulative, g = 0, 0
    for rank, value in enumerate(values, 1):
        cumulative += value
        if cumulative >= rank * rank:
            g = rank
    return g


def add_mncs(data: pd.DataFrame) -> pd.DataFrame:
    """Add the notebook's internal year-normalized citation score."""
    result = data.copy()
    if result["Publication Year"].notna().any():
        baselines = result.groupby("Publication Year")["Cited by"].mean()
        baseline = result["Publication Year"].map(baselines).replace(0, 1).fillna(1)
        result["MNCS"] = result["Cited by"] / baseline
    else:
        result["MNCS"] = 1.0
    return result


def main_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Compute the notebook's high-level corpus characteristics."""
    metrics: dict[str, object] = {"Total Documents": len(data)}
    years = pd.to_numeric(data["Publication Year"], errors="coerce").dropna().astype(int)
    if not years.empty:
        counts = years.value_counts().sort_index()
        first, last = int(counts.index.min()), int(counts.index.max())
        metrics["Timespan"] = f"{first} - {last}"
        if last > first and counts.iloc[0] > 0:
            metrics["Annual Growth Rate (CAGR %)"] = ((counts.iloc[-1] / counts.iloc[0]) ** (1 / (last - first)) - 1) * 100
        timeline = counts.reindex(range(first, last + 1), fill_value=0)
        metrics["Linear Growth Reliability (R²)"] = stats.linregress(timeline.index, timeline.values).rvalue ** 2 if len(timeline) > 1 else np.nan
        metrics["Average Document Age"] = (datetime.now().year - years).mean()
    metrics["Unique Sources"] = data["Source Title"].nunique(dropna=True)
    metrics["Avg. Citations per Doc"] = data["Cited by"].mean()
    metrics["Total Citations"] = data["Cited by"].sum()
    metrics["Total References (Intellectual Base)"] = pd.to_numeric(data["Cited Reference Count"], errors="coerce").sum()
    metrics["Author Keywords (DE)"] = data["Author Keywords"].dropna().astype(str).str.split(";").explode().str.strip().nunique()
    metrics["Keywords Plus (ID)"] = data["Keywords Plus"].dropna().astype(str).str.split(";").explode().str.strip().nunique()
    author_col = choose_author_column(data)
    if author_col:
        author_lists = data[author_col].fillna("").astype(str).str.split(";")
        metrics["Authors"] = author_lists.explode().str.strip().replace("", np.nan).nunique()
        sizes = author_lists.apply(lambda values: len([x for x in values if x.strip()]))
        metrics["Co-Authors per Doc"] = sizes.mean()
        metrics["Single-authored Docs"] = int((sizes == 1).sum())
    if "Country_Classification" in data:
        metrics["International Collab %"] = (data["Country_Classification"] == "MCP").mean() * 100
    return pd.DataFrame(metrics.items(), columns=["Metric", "Value"])


DOC_TYPE_MAP = {
    "article": "Article", "journal article": "Article", "review": "Review", "review article": "Review",
    "survey": "Review", "conference paper": "Conference", "proceeding paper": "Conference",
    "conference proceeding": "Conference", "book chapter": "Book Chapter", "book": "Book",
}


def document_types(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize document types using the taxonomy embedded in the notebook."""
    values = data["Document Type"].fillna("Missing/Incomplete data").astype(str).str.split("; ").explode()
    normalized = values.str.lower().str.strip().map(DOC_TYPE_MAP).fillna("Other")
    counts = normalized.value_counts()
    return pd.DataFrame({"Document Type": counts.index, "Count": counts.values,
                         "Percentage": counts.values / max(1, len(data)) * 100})


def choose_author_column(data: pd.DataFrame) -> str | None:
    for column in ("Author Full Names", "Authors"):
        if column in data and data[column].dropna().astype(str).str.strip().ne("").any():
            return column
    return None


def author_metrics(data: pd.DataFrame) -> pd.DataFrame:
    """Compute full counts, fractional credit, citations, MNCS, and local h-index."""
    column = choose_author_column(data)
    if not column:
        return pd.DataFrame()
    work = data[[column, "Cited by", "MNCS"]].dropna(subset=[column]).copy()
    work["Author"] = work[column].astype(str).str.split(";")
    work["num_authors"] = work["Author"].apply(lambda x: max(1, len([a for a in x if a.strip()])))
    work["Fractional_Credit"] = 1 / work["num_authors"]
    exploded = work.explode("Author")
    exploded["Author"] = exploded["Author"].str.strip()
    exploded = exploded[exploded["Author"] != ""]
    grouped = exploded.groupby("Author").agg(
        Total_Papers=("Author", "size"), Total_Citations=("Cited by", "sum"),
        Fractional_Credit=("Fractional_Credit", "sum"), Avg_MNCS=("MNCS", "mean")
    ).reset_index()
    h = exploded.groupby("Author")["Cited by"].apply(calculate_h_index)
    grouped["h_index"] = grouped["Author"].map(h)
    return grouped.sort_values(["Total_Papers", "Total_Citations"], ascending=False).reset_index(drop=True)


def annual_production(data: pd.DataFrame) -> pd.DataFrame:
    """Count publications for every year, inserting zero-count gaps."""
    years = pd.to_numeric(data["Publication Year"], errors="coerce").dropna().astype(int)
    if years.empty:
        return pd.DataFrame(columns=["Publication Year", "Count"])
    counts = years.value_counts().sort_index().reindex(range(years.min(), years.max() + 1), fill_value=0)
    return counts.rename_axis("Publication Year").reset_index(name="Count")


def citation_dynamics(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate accumulated and annualized citation velocity by publication year."""
    valid = data.dropna(subset=["Publication Year"]).copy()
    valid["Document Age"] = (datetime.now().year - valid["Publication Year"]).clip(lower=1)
    valid["Annualized Citations"] = valid["Cited by"] / valid["Document Age"]
    return valid.groupby("Publication Year").agg(
        Mean_Total_Citations=("Cited by", "mean"), Mean_Annualized_Citations=("Annualized Citations", "mean"),
        Documents=("Title", "size")
    ).reset_index()


def source_metrics(data: pd.DataFrame) -> pd.DataFrame:
    """Compute notebook source productivity and local h/g/m/MNCS indicators."""
    valid = data.dropna(subset=["Source Title", "Publication Year"]).copy()
    if valid.empty:
        return pd.DataFrame()
    valid["Source_Key"] = (valid["Source Title"].astype(str).str.lower().str.replace(" & ", " and ", regex=False)
                           .str.replace("&", "and", regex=False).str.replace("-", " ", regex=False)
                           .str.replace(r"[^\w\s]", "", regex=True).str.strip())
    rows = []
    for key, group in valid.groupby("Source_Key"):
        citations = group["Cited by"]
        first = int(group["Publication Year"].min())
        h = calculate_h_index(citations)
        rows.append({"Source_Key": key, "OriginalTitle": group["Source Title"].mode().iloc[0], "h_index": h,
                     "g_index": calculate_g_index(citations), "Total_Citations": citations.sum(),
                     "Number_of_Publications": len(group), "Avg_MNCS": group["MNCS"].mean(),
                     "First_Publication_Year": first, "Years_Active": max(1, datetime.now().year - first + 1),
                     "m_index": h / max(1, datetime.now().year - first + 1)})
    return pd.DataFrame(rows).sort_values("Number_of_Publications", ascending=False).reset_index(drop=True)


def country_metrics(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute SCP/MCP counts, impact, and country-year publication totals."""
    valid = data[data["Country_Classification"] != "Unknown"].copy()
    if valid.empty:
        return pd.DataFrame(), pd.DataFrame()
    exploded = valid.explode("Countries_Extracted").rename(columns={"Countries_Extracted": "Country"})
    exploded = exploded[exploded["Country"].notna() & exploded["Country"].astype(str).str.strip().ne("")]
    counts = exploded.groupby("Country")["Country_Classification"].agg(
        Articles="size", SCP=lambda x: (x == "SCP").sum(), MCP=lambda x: (x == "MCP").sum()).reset_index()
    counts["SCP %"] = counts["SCP"] / counts["Articles"] * 100
    counts["MCP %"] = counts["MCP"] / counts["Articles"] * 100
    impact = exploded.groupby("Country").agg(MNCS=("MNCS", "mean"), Total_Citations=("Cited by", "sum")).reset_index()
    master = counts.merge(impact, on="Country").sort_values("Articles", ascending=False).reset_index(drop=True)
    timeline = exploded.groupby(["Publication Year", "Country"]).size().reset_index(name="Publications")
    return master, timeline


def bradford_table(sources: pd.DataFrame) -> pd.DataFrame:
    """Create the cumulative source distribution and Bradford zones."""
    if sources.empty:
        return pd.DataFrame()
    result = sources[["OriginalTitle", "Number_of_Publications"]].rename(columns={"Number_of_Publications": "Count"})
    result = result.sort_values("Count", ascending=False).reset_index(drop=True)
    result["Rank"] = np.arange(1, len(result) + 1)
    result["Cumulative_Articles"] = result["Count"].cumsum()
    total = result["Count"].sum()
    result["Zone"] = np.select([result["Cumulative_Articles"] <= total / 3,
                                result["Cumulative_Articles"] <= 2 * total / 3], [1, 2], default=3)
    return result


def ranked_articles(data: pd.DataFrame) -> pd.DataFrame:
    """Rank all articles by raw citation count."""
    columns = ["Title", "Authors", "Publication Year", "Cited by", "DOI", "MNCS"]
    return data[columns].sort_values("Cited by", ascending=False).reset_index(drop=True)


def hot_papers(data: pd.DataFrame) -> pd.DataFrame:
    """Return papers from the current and previous three years, ranked by citations."""
    recent_year = datetime.now().year - 3
    return ranked_articles(data[data["Publication Year"] >= recent_year])


def team_size_impact(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate citation impact for teams of 1–5 and 6+ authors."""
    work = data.copy()
    work["Author_Count"] = work["Authors"].fillna("").astype(str).apply(lambda x: len([a for a in x.split(";") if a.strip()]))
    work = work[work["Author_Count"] > 0]
    work["Team Size"] = work["Author_Count"].map(lambda x: str(x) if x < 6 else "6+")
    order = ["1", "2", "3", "4", "5", "6+"]
    return work.groupby("Team Size")["Cited by"].agg(Average_Citations="mean", Number_of_Articles="count").reindex(order).reset_index()


def institution_networks(data: pd.DataFrame, max_institutions_per_paper=50) -> tuple[dict, pd.DataFrame]:
    """Build the notebook's Global/EU × All/MCP/SCP institutional networks."""
    eu = {"Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland",
          "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
          "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"}
    networks, summary = {}, []
    for region, publication_type in ((r, p) for r in ("Global", "EU") for p in ("All", "MCP", "SCP")):
        subset = data.copy()
        if publication_type != "All":
            subset = subset.loc[subset["Country_Classification"] == publication_type].copy()
        if region == "EU":
            eu_mask = subset["Countries_Extracted"].apply(
                lambda x: bool(x) and set(x).issubset(eu)
            ).astype(bool)
            subset = subset.loc[eu_mask].copy()
        counts = Counter(inst for values in subset["Institutions_Extracted"] for inst in values)
        ranking = pd.DataFrame(counts.most_common(), columns=["Institution", "Number_of_Publications"])
        edges = Counter()
        for values in subset["Institutions_Extracted"]:
            unique = sorted(set(values))[:max_institutions_per_paper]
            edges.update(combinations(unique, 2))
        edge_table = pd.DataFrame([(a, b, n) for (a, b), n in edges.items()],
                                  columns=["Institution1", "Institution2", "Collaboration_Count"])
        graph = nx.Graph()
        graph.add_nodes_from(counts)
        graph.add_weighted_edges_from((a, b, n) for (a, b), n in edges.items())
        communities = []
        if graph.number_of_edges():
            try:
                communities = [
                    sorted(group) for group in nx.community.louvain_communities(
                        graph, weight="weight", seed=42
                    )
                ]
            except (AttributeError, nx.NetworkXError):
                communities = [sorted(group) for group in nx.community.greedy_modularity_communities(graph, weight="weight")]
        key = f"{region}_{publication_type}"
        networks[key] = {"graph": graph, "ranking": ranking, "edges": edge_table, "communities": communities}
        summary.append({"Analysis": key, "Articles": len(subset), "Nodes": graph.number_of_nodes(),
                        "Edges": graph.number_of_edges(), "Communities": len(communities),
                        "Density": nx.density(graph) if graph.number_of_nodes() > 1 else 0,
                        "Top Institution": ranking.iloc[0]["Institution"] if not ranking.empty else "N/A"})
    return networks, pd.DataFrame(summary)


def thematic_analysis(data: pd.DataFrame, topic_count=8, min_document_frequency=None) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Run the notebook-style n-grams and NMF topic model on title/abstract/keywords."""
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

    warnings: list[str] = []
    corpus = (data["Title"].fillna("") + " " + data["Abstract"].fillna("") + " " +
              data["Author Keywords"].fillna("") + " " + data["Keywords Plus"].fillna(""))
    corpus = corpus.str.lower().str.replace(r"[^a-z\s-]", " ", regex=True).str.replace(r"\s+", " ", regex=True)
    n_docs = len(corpus)
    min_df = int(min_document_frequency or max(5, int(n_docs * 0.01)))
    min_df = max(1, min(min_df, max(1, n_docs)))
    tables: dict[str, pd.DataFrame] = {}
    for name, span in (("unigrams", (1, 1)), ("bigrams", (2, 2)), ("trigrams", (3, 3))):
        try:
            vec = CountVectorizer(stop_words="english", ngram_range=span, min_df=min_df, max_features=3000)
            matrix = vec.fit_transform(corpus)
            frequencies = np.asarray(matrix.sum(axis=0)).ravel()
            tables[name] = pd.DataFrame({"Term": vec.get_feature_names_out(), "Frequency": frequencies}).sort_values("Frequency", ascending=False).reset_index(drop=True)
        except ValueError:
            tables[name] = pd.DataFrame(columns=["Term", "Frequency"])
            warnings.append(f"Not enough repeated text for {name} at minimum frequency {min_df}.")
    try:
        tfidf = TfidfVectorizer(stop_words="english", min_df=min_df, max_df=0.95, max_features=5000, ngram_range=(1, 2))
        matrix = tfidf.fit_transform(corpus)
        k = max(2, min(int(topic_count), matrix.shape[0] - 1, matrix.shape[1] - 1))
        model = NMF(n_components=k, random_state=42, init="nndsvda", max_iter=500)
        weights = model.fit_transform(matrix)
        terms = tfidf.get_feature_names_out()
        topic_rows = []
        for number, component in enumerate(model.components_, 1):
            topic_rows.append({"Topic": number, "Top Terms": ", ".join(terms[component.argsort()[-10:][::-1]])})
        tables["topics"] = pd.DataFrame(topic_rows)
        assignments = weights.argmax(axis=1) + 1
        tables["article_topics"] = data[["Title", "Publication Year", "Cited by", "DOI"]].assign(Dominant_Topic=assignments)
        topic_impact = data.assign(Dominant_Topic=assignments).groupby("Dominant_Topic").agg(
            Articles=("Title", "size"), Mean_Citations=("Cited by", "mean"), MNCS=("MNCS", "mean")).reset_index()
        tables["topic_impact"] = topic_impact
        tables["topic_evolution"] = data.assign(Dominant_Topic=assignments).groupby(["Publication Year", "Dominant_Topic"]).size().reset_index(name="Articles")
    except ValueError as exc:
        warnings.append(f"Topic modeling skipped: {exc}")
    return tables, warnings
