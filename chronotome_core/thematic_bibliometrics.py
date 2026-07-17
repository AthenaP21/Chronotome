"""Notebook-faithful thematic preprocessing, topic evaluation, and evolution."""

from __future__ import annotations

import ast
import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.feature_extraction.text import CountVectorizer

from .descriptive_bibliometrics import add_internal_mncs
from .entity_resolution import canonicalize_country_name
from .preprocessing import select_author_text


DEFAULT_NOISE_LISTS = {
    "Generic academic terms": {
        "article", "study", "paper", "analysis", "method", "result", "conclusion", "introduction",
        "background", "data", "approach", "model", "system", "review", "survey", "case", "example",
        "framework", "research", "issue", "problem", "purpose", "abstract", "objective", "methodology",
        "discussion", "finding", "limitation", "implication", "contribution", "scope", "field", "literature",
        "chapter", "report", "document", "project", "activity", "process", "information", "high", "low",
        "large", "small", "recent", "new", "old", "current", "future", "previous", "different",
        "difference", "significant", "significantly", "several", "various", "multiple", "certain",
        "individual", "particular", "good", "better", "best", "effective", "efficient", "novel", "general",
        "specific", "main", "major", "important", "possible", "potential",
    },
    "Bibliometric and publisher noise": {
        "scopus", "elsevier", "web of science", "wos", "clarivate", "pubmed", "journal of informetrics",
        "scientometrics", "bibliometric", "bibliometrix", "vosviewer", "citespace", "incites", "researcherid",
        "orcid", "ieee", "springer", "wiley", "mdpi", "database", "index", "publication", "author",
        "journal", "conference", "proceeding", "university", "institute", "society", "nature", "switzerland",
        "ag", "license", "exclusive", "taylor", "francis", "group", "oxford", "press", "behalf", "reserved",
        "right", "publishing", "ltd", "copyright", "homepage", "visit", "download", "online", "open", "access",
        "creative", "commons", "attribution", "distribution", "reproduction", "medium", "american", "japan",
        "japanese", "chinese", "european",
    },
    "LaTeX and mathematical artifacts": {
        "amsbsy", "mathrsfs", "upgreek", "minimal", "amsmath", "wasysym", "amsfonts", "amssymb",
        "document", "mathrm", "mathbf", "mathcal", "text", "begin", "end", "equation", "array", "comment",
    },
    "Extended stopwords": {
        "whether", "also", "still", "every", "across", "through", "however", "although", "maybe", "could",
        "would", "may", "without", "among", "amongst", "various", "well", "within", "often", "mainly",
        "rather", "either", "neither", "another", "already", "always", "due", "first", "second", "third",
        "one", "two", "three", "fig", "figure", "table", "et", "al", "etal", "inc", "ltd", "corp", "via",
        "around",
    },
    "Non-substantive verbs": {
        "use", "using", "used", "show", "provide", "propose", "suggest", "present", "train", "training",
        "trained", "implement", "implementing", "implemented", "perform", "performing", "performed", "apply",
        "applying", "applied", "develop", "developing", "developed", "allow", "base", "include", "require",
        "achieve", "identify", "evaluate", "compare", "demonstrate", "find", "found", "describe", "consider",
        "investigate", "explore", "aim", "obtain", "report", "change", "contain", "occur", "observe", "exist",
        "remain", "seem", "appear", "indicate", "associate", "relate", "consist", "compose", "comprise",
        "increase", "measure", "take",
    },
}

DEFAULT_BLOCKLIST_PHRASES = {
    "nature switzerland ag", "license nature switzerland", "exclusive license nature",
    "taylor francis", "taylor francis group", "oxford press",
}


def prepare_thematic_dataset(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Bring an uploaded merged Chronotome dataset forward to the thematic handoff state."""
    if data is None or data.empty:
        raise ValueError("The uploaded Chronotome dataset is empty.")
    work = data.copy()
    warnings = []
    if "Countries_Extracted" not in work:
        if "Affiliations" not in work:
            work["Countries_Extracted"] = [[] for _ in range(len(work))]
            warnings.append("Affiliations were unavailable; country-dependent thematic analyses will be limited.")
        else:
            from .entity_resolution import resolve_entities
            resolved = resolve_entities(work)
            work = resolved["article_summary"]
            warnings.extend(resolved.get("warnings", []))
    work["Countries_Extracted"] = work["Countries_Extracted"].map(_country_list)
    if "Cited by" not in work:
        work["Cited by"] = np.nan
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce")
    if "MNCS" not in work or "MNCS_Defined" not in work:
        work, _, mncs_warnings = add_internal_mncs(work)
        warnings.extend(mncs_warnings)
    work["Country_Classification"] = work["Countries_Extracted"].map(
        lambda values: "MCP" if len(set(values)) > 1 else ("SCP" if len(set(values)) == 1 else "Unknown")
    )
    if "OriginalTitle" not in work and "Source Title" in work:
        work["OriginalTitle"] = work["Source Title"]
    return work.reset_index(drop=True), warnings


def thematic_resource_status() -> dict[str, bool]:
    try:
        import nltk
    except ImportError:
        return {"nltk_package": False, "wordnet": False, "stopwords": False, "punkt": False, "tagger": False}
    resources = {
        "wordnet": ("corpora/wordnet", "corpora/wordnet.zip"),
        "stopwords": ("corpora/stopwords",),
        "punkt": ("tokenizers/punkt", "tokenizers/punkt_tab"),
        "tagger": ("taggers/averaged_perceptron_tagger_eng", "taggers/averaged_perceptron_tagger"),
    }
    status = {"nltk_package": True}
    for key, paths in resources.items():
        status[key] = any(_nltk_find(nltk, path) for path in paths)
    return status


def _nltk_find(nltk, path: str) -> bool:
    try:
        nltk.data.find(path)
        return True
    except LookupError:
        return False


def install_nltk_resources() -> dict[str, bool]:
    import nltk
    for resource in ("wordnet", "stopwords", "omw-1.4", "punkt", "punkt_tab",
                     "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"):
        nltk.download(resource, quiet=True)
    return thematic_resource_status()


def parse_search_string(query: str) -> set[str]:
    query = (query or "").lower().replace("*", "")
    phrases = re.findall(r'"([^"]+)"', query)
    unquoted = re.sub(r'"[^"]+"', " ", query)
    operators = {"and", "or", "not", "title", "abs", "key", "all", "tak", "near", "pre", "w"}
    loose = [token for token in re.findall(r"[a-z][a-z-]+", unquoted) if token not in operators]
    terms = set(phrases + loose)
    for phrase in list(terms):
        terms.update(phrase.split())
    return {term.strip() for term in terms if term.strip()}


def _english_stopwords() -> set[str]:
    try:
        from nltk.corpus import stopwords
        return set(stopwords.words("english"))
    except Exception:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        return set(ENGLISH_STOP_WORDS)


def _simple_lemma(word: str) -> str:
    if len(word) > 5 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _preprocessor(noise_terms: set[str]):
    try:
        from nltk import pos_tag
        from nltk.stem import WordNetLemmatizer
        from nltk.tokenize import word_tokenize
        lemmatizer = WordNetLemmatizer()
        word_tokenize("resource check")
        pos_tag(["resource", "check"])
        lemmatizer.lemmatize("checks")
        def process(text):
            text = str(text).lower()
            final = []
            for word, tag in pos_tag(word_tokenize(text)):
                if not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", word):
                    continue
                lemma = lemmatizer.lemmatize(word, "v" if tag.startswith("VB") else "n")
                if lemma not in noise_terms:
                    final.append(lemma)
            return " ".join(final)
        return process, "NLTK tokenization, POS tagging, and WordNet lemmatization"
    except Exception:
        def process(text):
            text = str(text).lower()
            tokens = re.findall(r"\b[a-z]+(?:-[a-z]+)*\b", text)
            return " ".join(
                lemma for token in tokens
                if token not in noise_terms and (lemma := _simple_lemma(token)) not in noise_terms
            )
        return process, "deterministic regex fallback (NLTK resources unavailable)"


def _wordcloud(freq: pd.DataFrame, title: str):
    if freq.empty:
        return None
    try:
        from wordcloud import WordCloud
    except ImportError:
        return None
    cloud = WordCloud(width=1600, height=800, background_color="white", colormap="cividis", collocations=False)
    cloud.generate_from_frequencies(dict(zip(freq["ngram"], freq["count"])))
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(cloud, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(title, fontsize=20)
    fig.tight_layout()
    return fig


def thematic_preprocessing(data: pd.DataFrame, search_string: str, noise_lists: dict[str, set[str]],
                           blocklist: set[str], min_df: int | None = None, max_df: float = 0.90) -> dict:
    if data is None or data.empty:
        raise ValueError("The thematic-analysis dataset is empty.")
    work = data.reset_index(drop=True).copy()
    text_columns = [column for column in ("Keywords Plus", "Author Keywords", "Abstract", "Title") if column in work]
    if not text_columns:
        raise ValueError("At least one thematic text column is required: Title, Abstract, Author Keywords, or Keywords Plus.")
    search_terms = parse_search_string(search_string)
    noise = _english_stopwords() | search_terms
    for values in noise_lists.values():
        noise.update(term.lower().strip() for term in values if term.strip())
    processor, method = _preprocessor(noise)
    work["Combined_Raw_Text"] = work[text_columns].fillna("").astype(str).agg(" ".join, axis=1)
    work["Processed_Text"] = work["Combined_Raw_Text"].map(processor)
    n_docs = len(work)
    threshold = int(min_df) if min_df else max(5, int(n_docs * 0.01))
    threshold = max(1, min(threshold, n_docs))
    warnings = []
    vectorizer = CountVectorizer(
        ngram_range=(1, 4), max_df=max_df, min_df=threshold,
        token_pattern=r"(?u)\b\w[\w-]*\w\b",
    )
    try:
        matrix = vectorizer.fit_transform(work["Processed_Text"])
        frequencies = np.asarray(matrix.sum(axis=0)).ravel()
        combined = pd.DataFrame({"ngram": vectorizer.get_feature_names_out(), "count": frequencies})
        combined = combined.sort_values("count", ascending=False).reset_index(drop=True)
        combined = combined[~combined["ngram"].map(lambda value: len(value.split()) != len(set(value.split())))]
        def acronym_redundancy(value):
            parts = value.split()
            return len(parts) > 1 and parts[-1] == "".join(word[0] for word in parts[:-1])
        combined = combined[~combined["ngram"].map(acronym_redundancy)]
        combined = combined[~combined["ngram"].isin({x.lower() for x in blocklist})]
        combined["n_tokens"] = combined["ngram"].str.split().map(len)
    except ValueError as exc:
        combined = pd.DataFrame(columns=["ngram", "count", "n_tokens"])
        warnings.append(f"N-gram extraction produced no vocabulary: {exc}")
    tables = {"combined_ngram_frequency": combined}
    labels = {1: "unigram", 2: "bigram", 3: "trigram", 4: "quadgram"}
    figures = {}
    for size, label in labels.items():
        table = combined[combined["n_tokens"] == size].reset_index(drop=True)
        tables[f"{label}_frequency"] = table
        figure = _wordcloud(table.head(150), f"Top 150 {label.title()}s (N={n_docs} articles)")
        if figure is not None:
            figures[f"wordcloud_{label}s"] = figure
    combined_figure = _wordcloud(combined.head(150), f"Top 150 Combined N-grams (N={n_docs} articles)")
    if combined_figure is not None:
        figures["wordcloud_combined_ngrams"] = combined_figure
    if "fallback" in method:
        warnings.append("NLTK resources were unavailable; preprocessing used the documented regex fallback.")
    if not figures:
        warnings.append("The wordcloud package is unavailable; frequency tables were still generated.")
    return {
        "data": work, "tables": tables, "figures": figures, "warnings": warnings,
        "search_terms": sorted(search_terms), "noise_terms": sorted(noise),
        "preprocessing_method": method, "min_df": threshold, "max_df": max_df,
    }


def _topic_coherence(model, feature_names, tokenized, top_n=20):
    topics = []
    for component in model.components_:
        topics.append([feature_names[index] for index in component.argsort()[:-top_n - 1:-1]])
    try:
        from gensim.corpora.dictionary import Dictionary
        from gensim.models import CoherenceModel
        dictionary = Dictionary(tokenized)
        corpus = [dictionary.doc2bow(text) for text in tokenized]
        score = CoherenceModel(topics=topics, texts=tokenized, dictionary=dictionary,
                               corpus=corpus, coherence="c_v", processes=1).get_coherence()
        return float(score), "c_v (Gensim)"
    except Exception:
        documents = [set(tokens) for tokens in tokenized]
        scores = []
        for topic in topics:
            for i in range(1, len(topic)):
                for j in range(i):
                    both = sum(topic[i] in doc and topic[j] in doc for doc in documents)
                    base = sum(topic[j] in doc for doc in documents)
                    scores.append(np.log((both + 1) / max(1, base)))
        return float(np.mean(scores)) if scores else np.nan, "UMass fallback"


def topic_model_evaluation(data: pd.DataFrame, k_values, min_df: int = 2, max_df: float = 0.95,
                           max_iter: int = 500) -> dict:
    if "Processed_Text" not in data:
        raise ValueError("Run thematic preprocessing before topic evaluation.")
    texts = data["Processed_Text"].fillna("").astype(str)
    vectorizer = CountVectorizer(max_df=max_df, min_df=min_df)
    try:
        dtm = vectorizer.fit_transform(texts)
    except ValueError as exc:
        raise ValueError(f"Topic-model vocabulary is empty: {exc}") from exc
    features = vectorizer.get_feature_names_out()
    tokenized = [text.split() for text in texts if text.strip()]
    maximum_k = max(2, min(dtm.shape[0] - 1, dtm.shape[1] - 1))
    values = sorted({int(k) for k in k_values if 2 <= int(k) <= maximum_k})
    if not values:
        values = [maximum_k]
    rows, coherence_method = [], None
    for k in values:
        lda = LatentDirichletAllocation(n_components=k, random_state=42, learning_method="batch")
        lda.fit(dtm)
        lda_coherence, coherence_method = _topic_coherence(lda, features, tokenized)
        nmf = NMF(n_components=k, random_state=42, max_iter=max_iter, init="nndsvda")
        nmf.fit(dtm)
        nmf_coherence, _ = _topic_coherence(nmf, features, tokenized)
        rows.append({"k": k, "LDA_Perplexity": lda.perplexity(dtm),
                     "LDA_Coherence": lda_coherence, "NMF_Coherence": nmf_coherence})
    evaluation = pd.DataFrame(rows)
    best_lda = int(evaluation.loc[evaluation["LDA_Coherence"].idxmax(), "k"])
    best_nmf = int(evaluation.loc[evaluation["NMF_Coherence"].idxmax(), "k"])
    colors = {"perplexity": "#00204d", "coherence": "#b9ac70", "nmf": "#414d6b", "mid": "#666666"}
    fig_lda, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    ax1.plot(evaluation["k"], evaluation["LDA_Perplexity"], marker="o", color=colors["perplexity"], linewidth=2)
    ax2.plot(evaluation["k"], evaluation["LDA_Coherence"], marker="s", color=colors["coherence"], linewidth=2)
    ax1.set_xlabel("Number of Topics (k)", fontsize=12, fontweight="medium")
    ax1.set_ylabel("Perplexity (lower is better)", color=colors["perplexity"], fontsize=12, fontweight="medium")
    ax2.set_ylabel("Coherence (higher is better)", color=colors["coherence"], fontsize=12, fontweight="medium")
    ax1.tick_params(axis="y", labelcolor=colors["perplexity"]); ax2.tick_params(axis="y", labelcolor=colors["coherence"])
    ax1.axvline(best_lda, color=colors["mid"], linestyle="--", alpha=0.7)
    ax2.annotate(f"Optimal k = {best_lda}", xy=(best_lda, evaluation.loc[evaluation["k"] == best_lda, "LDA_Coherence"].iloc[0]),
                 xytext=(10, -20), textcoords="offset points", arrowprops=dict(arrowstyle="->", color=colors["mid"]),
                 bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f8", ec=colors["mid"]), fontsize=10)
    ax1.set_title(f"LDA Topic Model Evaluation Metrics (N={len(data)} articles)", fontsize=16, fontweight="bold", pad=20)
    ax1.grid(alpha=0.3, linestyle="--"); fig_lda.tight_layout()
    fig_nmf, ax = plt.subplots(figsize=(10, 6))
    ax.plot(evaluation["k"], evaluation["NMF_Coherence"], marker="o", color=colors["nmf"], linewidth=2, markersize=8)
    ax.axvline(best_nmf, color=colors["mid"], linestyle="--", alpha=0.7)
    ax.annotate(f"Best NMF k = {best_nmf}",
                xy=(best_nmf, evaluation.loc[evaluation["k"] == best_nmf, "NMF_Coherence"].iloc[0]),
                xytext=(10, -20), textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color=colors["mid"]),
                bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f8", ec=colors["mid"]), fontsize=10)
    ax.set_xlabel("Number of Topics (k)", fontsize=12, fontweight="medium")
    ax.set_ylabel("Coherence", fontsize=12, fontweight="medium")
    ax.set_title(f"NMF Model Coherence by Number of Topics (N={len(data)} articles)",
                 fontsize=16, fontweight="bold", pad=20)
    ax.grid(alpha=0.3, linestyle="--"); fig_nmf.tight_layout()
    warnings = [] if coherence_method.startswith("c_v") else ["Gensim c_v coherence was unavailable; evaluation used a UMass fallback."]
    return {"tables": {"topic_model_evaluation": evaluation},
            "figures": {"LDA_Evaluation_Metrics": fig_lda, "NMF_Coherence": fig_nmf},
            "warnings": warnings, "best_k": best_lda, "best_nmf_k": best_nmf,
            "coherence_method": coherence_method, "min_df": min_df, "max_df": max_df}


def _topic_descriptions(model, features, top_words):
    rows = []
    for index, component in enumerate(model.components_, 1):
        words = features[component.argsort()[:-top_words - 1:-1]]
        rows.append({"Topic": index, "Top Terms": " | ".join(words)})
    return pd.DataFrame(rows)


def final_topic_models(data: pd.DataFrame, lda_k: int, nmf_k: int, bin_duration: int = 5,
                       top_words: int = 15, min_df: int = 2, max_df: float = 0.95) -> dict:
    texts = data["Processed_Text"].fillna("").astype(str)
    vectorizer = CountVectorizer(max_df=max_df, min_df=min_df)
    dtm = vectorizer.fit_transform(texts); features = vectorizer.get_feature_names_out()
    maximum_k = max(2, min(dtm.shape[0] - 1, dtm.shape[1] - 1))
    lda_k, nmf_k = min(int(lda_k), maximum_k), min(int(nmf_k), maximum_k)
    lda = LatentDirichletAllocation(n_components=lda_k, random_state=42, learning_method="batch", max_iter=50)
    lda_output = lda.fit_transform(dtm)
    nmf = NMF(n_components=nmf_k, random_state=42, max_iter=500, init="nndsvda")
    nmf_output = nmf.fit_transform(dtm)
    work = data.reset_index(drop=True).copy()
    work["Dominant_Topic"] = np.argmax(lda_output, axis=1) + 1
    work["Topic_Distribution"] = list(lda_output)
    work["NMF_Dominant_Topic"] = np.argmax(nmf_output, axis=1) + 1
    tables = {
        "lda_topic_descriptions": _topic_descriptions(lda, features, top_words),
        "nmf_topic_descriptions": _topic_descriptions(nmf, features, top_words),
    }
    figures, warnings = {}, []
    years = pd.to_numeric(work.get("Publication Year"), errors="coerce")
    valid = work.loc[years.notna()].copy(); valid["Publication Year"] = years.dropna().astype(int)
    if valid.empty:
        warnings.append("Publication Year is unavailable; topic-evolution figures were skipped.")
    else:
        valid["Time_Slice"] = valid["Publication Year"].map(
            lambda year: f"{(int(year)//bin_duration)*bin_duration}-{(int(year)//bin_duration)*bin_duration+bin_duration-1}"
        )
        start = (valid["Publication Year"].min() // bin_duration) * bin_duration
        end = (valid["Publication Year"].max() // bin_duration) * bin_duration
        slices = [f"{year}-{year+bin_duration-1}" for year in range(start, end + bin_duration, bin_duration)]
        props = pd.DataFrame(lda_output[valid.index], columns=[f"Topic {i}" for i in range(1, lda_k + 1)])
        props["Time_Slice"] = valid["Time_Slice"].values
        avg = props.groupby("Time_Slice").mean().reindex(slices, fill_value=0)
        counts = valid.groupby(["Time_Slice", "Dominant_Topic"]).size().unstack(fill_value=0).reindex(slices, fill_value=0)
        nmf_counts = valid.groupby(["Time_Slice", "NMF_Dominant_Topic"]).size().unstack(fill_value=0).reindex(slices, fill_value=0)
        tables.update({"topic_evolution_proportions": avg.reset_index(),
                       "topic_publication_counts": counts.reset_index(),
                       "nmf_topic_publication_counts": nmf_counts.reset_index()})
        colors_lda = plt.cm.cividis(np.linspace(0, 0.9, lda_k)); colors_nmf = plt.cm.cividis(np.linspace(0, 0.9, nmf_k))
        fig, ax = plt.subplots(figsize=(12, 8))
        for i, column in enumerate(avg.columns): ax.plot(avg.index, avg[column], marker="o", linewidth=2, color=colors_lda[i], label=column)
        ax.set(xlabel=f"Time Period ({bin_duration}-Year Bins)", ylabel="Average Topic Proportion")
        ax.set_title(f"Evolution of Research Topics Over Time (Proportional)\n(N={lda_k} topics, N={len(work)} articles)", fontsize=16, fontweight="bold", pad=20)
        ax.legend(title="Topics", bbox_to_anchor=(1.05, 1), loc="upper left"); ax.tick_params(axis="x", rotation=45); ax.grid(alpha=0.3, linestyle="--"); fig.tight_layout()
        figures["Topic_Evolution_Proportion"] = fig
        def count_plot(table, k, colors, title, legend):
            figure, axis = plt.subplots(figsize=(14, 8))
            for topic in range(1, k + 1):
                if topic in table: axis.plot(table.index, table[topic], marker="o", linewidth=2, label=f"Topic {topic}", color=colors[topic-1])
            axis.set(xlabel=f"Time Period ({bin_duration}-Year Bins)", ylabel="Number of Publications")
            axis.set_title(title, fontsize=16, fontweight="bold", pad=20); axis.legend(title=legend, bbox_to_anchor=(1.05, 1), loc="upper left")
            axis.tick_params(axis="x", rotation=45); axis.grid(alpha=0.3, linestyle="--"); figure.tight_layout(); return figure
        figures["Topic_Publication_Trends"] = count_plot(counts, lda_k, colors_lda, f"Publication Counts by Topic Over Time\n(N={lda_k} topics, N={len(work)} articles)", "Topics")
        figures["NMF_Topic_Trends"] = count_plot(nmf_counts, nmf_k, colors_nmf, f"NMF Topic Distribution Over Time\n(N={nmf_k} topics, N={len(work)} articles)", "NMF Topics")
        work.loc[valid.index, "Time_Slice"] = valid["Time_Slice"]
    tables["article_topic_assignments"] = work[[column for column in ("Title", "Publication Year", "Dominant_Topic", "NMF_Dominant_Topic") if column in work]]
    return {"data": work, "tables": tables, "figures": figures, "warnings": warnings,
            "best_k": lda_k, "best_nmf_k": nmf_k, "bin_duration": bin_duration}


def _country_list(value):
    if isinstance(value, (list, tuple, set)):
        values = value
    elif isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            parsed = [value]
        values = parsed if isinstance(parsed, (list, tuple, set)) else [parsed]
    else:
        values = []
    if isinstance(values, set):
        values = sorted(values, key=lambda item: str(item).casefold())
    canonical = (canonicalize_country_name(item) for item in values)
    return list(dict.fromkeys(country for country in canonical if country))


def advanced_thematic_analysis(data: pd.DataFrame, cooccurrence_threshold: float = 0.1,
                               min_country_documents: int = 10, top_countries: int = 20) -> dict:
    """Run notebook Section 25 topic impact, intersections, canonical papers, and specialization."""
    if "Dominant_Topic" not in data or "Topic_Distribution" not in data:
        raise ValueError("Final LDA topic assignments and distributions are required.")
    work = data.reset_index(drop=True).copy()
    if "Cited by" not in work:
        work["Cited by"] = np.nan
    work["Cited by"] = pd.to_numeric(work["Cited by"], errors="coerce")
    work["Publication Year"] = pd.to_numeric(work.get("Publication Year"), errors="coerce")
    distributions = np.vstack([
        np.asarray(value, dtype=float) for value in work["Topic_Distribution"]
    ])
    n_topics = distributions.shape[1]
    warnings, tables, figures = [], {}, {}

    if "MNCS" not in work or "MNCS_Defined" not in work:
        work, _, mncs_warnings = add_internal_mncs(work)
        warnings.extend(mncs_warnings)
    impact = work.groupby("Dominant_Topic").agg(
        Topic_MNCS=("MNCS", "mean"),
        Number_of_Documents=("Dominant_Topic", "size"),
    ).reset_index().sort_values("Topic_MNCS", ascending=False)
    impact["Topic_Label"] = "Topic " + impact["Dominant_Topic"].astype(int).astype(str)
    tables["topic_citation_impact_mncs"] = impact
    plot = impact.dropna(subset=["Topic_MNCS"]).sort_values("Topic_MNCS")
    if plot.empty:
        warnings.append("Topic impact could not be plotted because MNCS is undefined for all topics.")
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.barh(plot["Topic_Label"], plot["Topic_MNCS"], color="#00204d")
        ax.axvline(
            1.0, color="#b9ac70", linestyle="--", linewidth=2,
            label="Same-year corpus baseline (1.0)",
        )
        ax.set_title(f"Relative Citation Impact of Research Topics (MNCS)\n(N={len(impact)} topics, N={len(work)} articles)",
                     fontsize=14, fontweight="bold", pad=20)
        ax.set_xlabel("Corpus-internal year-normalized citation score (MNCS)", fontsize=12); ax.set_ylabel(None)
        ax.spines[["top", "right", "left"]].set_visible(False); ax.grid(axis="x", linestyle="--", alpha=0.6)
        ax.legend(loc="lower right"); maximum = plot["Topic_MNCS"].max()
        ax.set_xlim(0, max(1.1, maximum * 1.15))
        for bar in bars:
            ax.annotate(f" {bar.get_width():.2f}", xy=(bar.get_width(), bar.get_y()+bar.get_height()/2),
                        xytext=(3, 0), textcoords="offset points", ha="left", va="center", fontsize=10)
        fig.tight_layout(); figures["topic_citation_impact_mncs"] = fig

    binary = (distributions > float(cooccurrence_threshold)).astype(int)
    cooccurrence = binary.T @ binary; np.fill_diagonal(cooccurrence, 0)
    labels = [f"T{i+1}" for i in range(n_topics)]
    cooccurrence_df = pd.DataFrame(cooccurrence, index=labels, columns=labels)
    tables["topic_cooccurrence_matrix"] = cooccurrence_df.reset_index(names="Topic")
    import seaborn as sns
    fig, ax = plt.subplots(figsize=(max(8, n_topics * 0.8), max(6, n_topics * 0.7)))
    sns.heatmap(cooccurrence_df, annot=n_topics <= 12, fmt=".0f", cmap="cividis", linewidths=.5,
                linecolor="white", cbar_kws={"label": "Co-occurring Documents"}, ax=ax)
    ax.set_title(f"Topic Co-occurrence Matrix\n(Threshold > {cooccurrence_threshold}, N={n_topics} topics, N={len(work)} articles)",
                 fontsize=14, fontweight="bold", pad=20)
    ax.set_xlabel("Topic", fontsize=12); ax.set_ylabel("Topic", fontsize=12)
    ax.tick_params(axis="x", rotation=0); ax.tick_params(axis="y", rotation=0)
    fig.tight_layout(); figures["topic_cooccurrence_heatmap"] = fig

    work["Selected Author Names"] = select_author_text(work)
    article_columns = [column for column in (
        "Dominant_Topic", "Title", "Authors", "Author Full Names", "Selected Author Names",
        "Publication Year", "OriginalTitle", "Source Title", "Cited by", "DOI"
    ) if column in work]
    articles = work[article_columns].copy().sort_values("Cited by", ascending=False)
    if "OriginalTitle" not in articles and "Source Title" in articles:
        articles["OriginalTitle"] = articles["Source Title"]
    articles = articles.rename(columns={"Dominant_Topic": "Topic", "OriginalTitle": "Source", "Cited by": "Citations"})
    tables["all_articles_by_topic_and_citation"] = articles
    canonical = articles.drop_duplicates("Topic", keep="first").sort_values("Topic").copy()
    canonical["First Author"] = canonical["Selected Author Names"].fillna("N/A").astype(str).str.split(";").str[0].str.strip()
    canonical["Title (Short)"] = canonical.get("Title", pd.Series("N/A", index=canonical.index)).astype(str).map(
        lambda title: title[:50] + "..." if len(title) > 50 else title
    )
    display_columns = [column for column in ("Topic", "Title (Short)", "First Author", "Publication Year", "Citations") if column in canonical]
    tables["most_cited_article_per_topic"] = canonical[display_columns]

    if "Countries_Extracted" not in work:
        warnings.append("Countries_Extracted is unavailable; country specialization was skipped.")
    else:
        country_topic = work[["Dominant_Topic", "Countries_Extracted"]].copy()
        country_topic["Countries"] = country_topic["Countries_Extracted"].map(_country_list)
        exploded = country_topic.explode("Countries").dropna(subset=["Countries"])
        exploded = exploded[exploded["Countries"].astype(str).str.strip().ne("")]
        if exploded.empty:
            warnings.append("No valid country metadata was available for specialization analysis.")
        else:
            pivot = pd.pivot_table(exploded, index="Countries", columns="Dominant_Topic", aggfunc="size", fill_value=0)
            pivot.columns = [f"Topic {int(column)}" for column in pivot.columns]
            counts = pivot.sum(axis=1); valid = counts[counts >= int(min_country_documents)].index
            filtered = pivot.loc[valid]
            global_distribution = pivot.sum(axis=0) / max(1, pivot.to_numpy().sum())
            activity = filtered.div(filtered.sum(axis=1), axis=0).div(global_distribution, axis=1).fillna(0)
            tables["topic_country_activity_index"] = activity.reset_index(names="Country")
            selected = counts.loc[valid].nlargest(int(top_countries)).index
            plot_activity = activity.loc[selected]
            if plot_activity.empty:
                warnings.append(f"No country met the minimum of {int(min_country_documents)} documents; specialization heatmap skipped.")
            else:
                fig, ax = plt.subplots(figsize=(10, max(6, len(plot_activity) * 0.4)))
                sns.heatmap(plot_activity, annot=False, cmap="cividis", linewidths=.5, linecolor="white",
                            cbar_kws={"label": "Activity Index (AI)"}, ax=ax)
                ax.set_title(f"Topic Specialization by Country (Activity Index)\n(N={len(plot_activity)} countries, N={len(plot_activity.columns)} topics)",
                             fontsize=14, fontweight="bold", pad=20)
                ax.set_xlabel("Topic", fontsize=12); ax.set_ylabel("Country", fontsize=12)
                ax.tick_params(axis="x", rotation=45); ax.tick_params(axis="y", rotation=0)
                fig.tight_layout(); figures["topic_country_specialization_heatmap"] = fig
    return {"data": work, "tables": tables, "figures": figures, "warnings": warnings,
            "cooccurrence_threshold": float(cooccurrence_threshold),
            "min_country_documents": int(min_country_documents)}
