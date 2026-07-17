"""Guided Part 3 thematic-analysis module."""

from __future__ import annotations

import hashlib
import io
import re

import pandas as pd
import streamlit as st

from chronotome_core import (
    prepare_uploaded_thematic_dataset, run_advanced_thematic_analysis,
    run_final_topic_models, run_thematic_preprocessing, run_topic_model_evaluation,
)
from chronotome_core.runner import DEFAULT_CONFIG
from chronotome_core.thematic_bibliometrics import (
    DEFAULT_BLOCKLIST_PHRASES, DEFAULT_NOISE_LISTS,
    install_nltk_resources, thematic_resource_status,
)
from chronotome_ui.figure_controls import render_customizable_figure
from chronotome_ui.navigation import navigate_to_page
from chronotome_ui.state import clear_downstream_state


def _section(number: int, title: str, caption: str | None = None):
    st.markdown("---")
    st.markdown(f"## {number}. {title}")
    if caption:
        st.caption(caption)


def _read_dataset(uploaded_file) -> pd.DataFrame:
    content = uploaded_file.getvalue()
    if uploaded_file.name.lower().endswith((".xls", ".xlsx")):
        frame = pd.read_excel(io.BytesIO(content))
    else:
        frame = pd.read_csv(io.BytesIO(content), low_memory=False)
        if frame.shape[1] == 1:
            frame = pd.read_csv(io.BytesIO(content), sep="\t", low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _select_dataset():
    geographic = st.session_state.get("geographic_analysis_results")
    options = []
    if geographic is not None:
        options.append("Use current geographic-analysis dataset")
    options.append("Upload a Chronotome dataset")
    choice = st.radio("Thematic dataset", options, horizontal=True, key="thematic_dataset_source")
    if choice.startswith("Use current geographic"):
        data = geographic["data"]
        return data, (
            "geographic", st.session_state.get("geographic_analysis_signature"),
            len(data), tuple(data.columns),
        )
    upload = st.file_uploader("Upload CSV or Excel", type=["csv", "xls", "xlsx"], key="thematic_upload")
    if not upload:
        return None, None
    signature = (upload.name, len(upload.getvalue()), hashlib.sha256(upload.getvalue()).hexdigest())
    if st.session_state.get("thematic_uploaded_dataset_signature") != signature:
        raw = _read_dataset(upload)
        with st.spinner("Preparing the uploaded dataset through entity, MNCS, and geographic handoff rules…"):
            prepared = prepare_uploaded_thematic_dataset(raw)
        st.session_state["thematic_uploaded_dataset"] = prepared
        st.session_state["thematic_uploaded_dataset_signature"] = signature
    prepared = st.session_state["thematic_uploaded_dataset"]
    for warning in prepared["warnings"]:
        st.warning(warning)
    st.success("The uploaded dataset has been prepared to the thematic-analysis handoff state.")
    return prepared["data"], ("prepared-upload", *signature)


def _parse_terms(text: str) -> set[str]:
    return {term.strip().lower() for term in re.split(r"[\n,;]+", text or "") if term.strip()}


def _render_figure(result: dict, basename: str, prefix: str):
    exports = result["exports"]
    figure = result.get("figures", {}).get(basename)
    render_customizable_figure(exports, basename, prefix, figure=figure)


def _stage_downloads(result: dict, archive: str, workbook: str, prefix: str):
    left, right = st.columns(2)
    left.download_button("Download this stage (ZIP)", result["exports"][archive], archive,
                         "application/zip", key=f"{prefix}-zip")
    right.download_button("Download all stage tables (Excel)", result["exports"][f"Results/{workbook}"], workbook,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{prefix}-xlsx")


def render_thematic_analysis():
    st.title("Thematic Analysis")
    st.markdown(
        "Part 3 extracts emergent concepts from titles, abstracts, author keywords, and Keywords Plus, "
        "then evaluates LDA/NMF topic solutions and tracks their evolution over time."
    )
    st.info(
        "Use this module to prepare clean thematic terms, inspect n-grams, evaluate topic models, "
        "and study topic evolution and specialization."
    )

    _section(1, "Select the thematic dataset")
    try:
        data, dataset_signature = _select_dataset()
    except Exception as exc:
        st.error(f"The thematic dataset could not be read: {exc}")
        data, dataset_signature = None, None
    if data is not None:
        available = [column for column in ("Title", "Abstract", "Author Keywords", "Keywords Plus") if column in data]
        c1, c2, c3 = st.columns(3)
        c1.metric("Documents", f"{len(data):,}")
        c2.metric("Text fields detected", f"{len(available)} of 4")
        c3.metric("Year coverage", f"{pd.to_numeric(data.get('Publication Year'), errors='coerce').notna().mean()*100:.1f}%" if "Publication Year" in data else "Unavailable")
        if not available:
            st.error("No thematic text fields were detected.")
            data = None
        else:
            st.caption("Detected fields: " + ", ".join(available))

    _section(2, "NLTK setup", "Resources are checked locally; downloads occur only when you request them.")
    status = thematic_resource_status()
    labels = (("NLTK package", "nltk_package"), ("WordNet", "wordnet"), ("Stopwords", "stopwords"),
              ("Tokenizer", "punkt"), ("POS tagger", "tagger"))
    columns = st.columns(5)
    for column, (label, key) in zip(columns, labels):
        column.metric(label, "Ready" if status[key] else "Missing")
    if not status["nltk_package"]:
        st.warning("NLTK is not installed. Install the package requirements to use NLTK text processing.")
    elif not all(status.values()):
        if st.button("Download or repair NLTK resources", key="thematic-nltk-download"):
            try:
                with st.spinner("Downloading NLTK language resources…"):
                    repaired = install_nltk_resources()
                if all(repaired.values()):
                    st.success("NLTK resources are ready.")
                    st.rerun()
                else:
                    st.warning("Some NLTK resources are unavailable. Chronotome will use regex-based text processing.")
            except Exception as exc:
                st.error(f"NLTK resources could not be downloaded: {exc}")
    else:
        st.success("NLTK tokenization, POS tagging, stopwords, and WordNet lemmatization are ready.")

    _section(3, "Search string and noise-word lists",
             "Optionally remove the Scopus/WoS query terms. Add or remove one term or phrase per line in each category.")
    remove_search_terms = st.toggle(
        "Remove database search terms from the thematic vocabulary", value=False,
        key="thematic_remove_search_terms_v2",
    )
    search_string = st.text_area(
        "Database search string", value="", height=150, key="thematic_search_string_v2",
        placeholder='Example: ("exoplanet*" OR "planetary transit*") AND ("machine learning" OR "AI")',
        disabled=not remove_search_terms,
    )
    if not remove_search_terms:
        st.caption("Query-term removal is currently off. Terms such as “artificial intelligence” or “machine learning” can remain visible in the results.")
    if st.button("Restore all default noise lists", key="thematic-reset-noise"):
        for category in DEFAULT_NOISE_LISTS:
            st.session_state.pop(f"thematic_noise_{category}", None)
        st.session_state.pop("thematic_blocklist", None)
        st.rerun()
    noise_lists = {}
    for category, defaults in DEFAULT_NOISE_LISTS.items():
        with st.expander(f"{category} ({len(defaults)} defaults)"):
            value = st.text_area(
                f"{category} terms", value="\n".join(sorted(defaults)), height=220,
                key=f"thematic_noise_{category}", label_visibility="collapsed",
            )
            noise_lists[category] = _parse_terms(value)
            st.caption(f"Active terms in this category: {len(noise_lists[category]):,}")
    with st.expander(f"Blocked phrases ({len(DEFAULT_BLOCKLIST_PHRASES)} defaults)"):
        block_text = st.text_area(
            "Blocked phrases", value="\n".join(sorted(DEFAULT_BLOCKLIST_PHRASES)), height=150,
            key="thematic_blocklist", label_visibility="collapsed",
        )
        blocklist = _parse_terms(block_text)

    st.markdown("### Thematic extraction settings")
    ng_left, ng_mid, ng_right = st.columns(3)
    automatic_min_df = ng_left.checkbox("Automatic n-gram minimum frequency", value=True, key="thematic_auto_min_df")
    manual_min_df = ng_mid.number_input(
        "N-gram minimum document frequency", min_value=1, max_value=1000,
        value=2, disabled=automatic_min_df, key="thematic_min_df",
    )
    ngram_max_df = ng_right.slider(
        "N-gram maximum document share", 0.50, 1.00, 0.90, 0.01,
        key="thematic_ngram_max_df",
    )
    with st.expander("Topic-model vectorizer settings", expanded=False):
        model_left, model_right = st.columns(2)
        model_min_df = model_left.number_input(
            "Topic-model minimum document frequency", 1, 100,
            int(DEFAULT_CONFIG["topic_model_min_df"]), key="thematic_model_min_df",
        )
        model_max_df = model_right.slider(
            "Topic-model maximum document share", 0.50, 1.00, 0.95, 0.01,
            key="thematic_model_max_df",
        )

    settings_signature = (
        "thematic-v2", dataset_signature, bool(remove_search_terms), search_string if remove_search_terms else "",
        tuple((category, tuple(sorted(values))) for category, values in noise_lists.items()),
        tuple(sorted(blocklist)), None if automatic_min_df else int(manual_min_df), float(ngram_max_df),
    )
    _section(4, "Text preprocessing and n-gram extraction",
             "Combines available text fields, removes query/noise terms, and extracts 1–4 grams.")
    if st.button("Run text preprocessing and n-gram analysis", type="primary",
                 disabled=data is None or (remove_search_terms and not search_string.strip()),
                 key="run-thematic-preprocessing"):
        try:
            with st.spinner("Preprocessing text, extracting n-grams, and rendering word clouds…"):
                result = run_thematic_preprocessing(
                    data, search_string if remove_search_terms else "", noise_lists, blocklist,
                    min_df=None if automatic_min_df else int(manual_min_df), max_df=float(ngram_max_df),
                )
                clear_downstream_state("thematic")
                st.session_state["thematic_preprocessing_results"] = result
                st.session_state["thematic_preprocessing_signature"] = settings_signature
                st.session_state.pop("topic_evaluation_results", None)
                st.session_state.pop("final_topic_model_results", None)
            st.success("Text preprocessing and n-gram analysis complete.")
        except (ValueError, KeyError) as exc:
            st.error(f"Thematic preprocessing could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected text value stopped preprocessing: {exc}")
    preprocessing = st.session_state.get("thematic_preprocessing_results")
    pre_current = preprocessing is not None and st.session_state.get("thematic_preprocessing_signature") == settings_signature
    if preprocessing and not pre_current:
        st.warning("The dataset, query, or noise settings changed. Rerun preprocessing for this configuration.")
    if pre_current:
        for warning in preprocessing["warnings"]: st.warning(warning)
        c1, c2, c3 = st.columns(3)
        c1.metric("Preprocessing method", preprocessing["preprocessing_method"])
        c2.metric("Query terms removed", f"{len(preprocessing['search_terms']):,}")
        c3.metric("Minimum document frequency", preprocessing["min_df"])
        with st.expander("Extracted query terms"):
            st.write(", ".join(preprocessing["search_terms"]) or "None")
        preview_cols = [column for column in ("Title", "Processed_Text") if column in preprocessing["data"]]
        st.dataframe(preprocessing["data"][preview_cols].head(20), width="stretch", hide_index=True)
        for label, key, figure in (
            ("Unigrams", "unigram_frequency", "wordcloud_unigrams"),
            ("Bigrams", "bigram_frequency", "wordcloud_bigrams"),
            ("Trigrams", "trigram_frequency", "wordcloud_trigrams"),
            ("Quadgrams", "quadgram_frequency", "wordcloud_quadgrams"),
            ("Combined n-grams", "combined_ngram_frequency", "wordcloud_combined_ngrams"),
        ):
            st.markdown(f"#### {label}")
            st.dataframe(preprocessing["tables"][key].head(30), width="stretch", hide_index=True)
            _render_figure(preprocessing, figure, f"thematic-{figure}")
        _stage_downloads(preprocessing, "chronotome_thematic_preprocessing_outputs.zip",
                         "thematic_preprocessing_tables.xlsx", "thematic-pre")

    _section(5, "Automatic topic selection and evolution",
             "Chronotome evaluates the configured k values, selects the highest-coherence LDA and NMF candidates, and trains both models.")
    option_left, option_right = st.columns(2)
    bin_duration = option_left.number_input(
        "Time-bin width (years)", 1, 25, int(DEFAULT_CONFIG["topic_bin_duration"]),
        key="thematic-bin-duration",
    )
    top_words = option_right.number_input("Terms retained per topic", 5, 30, 15, key="thematic-top-words")
    candidate_k = tuple(DEFAULT_CONFIG["topic_k_values"])
    modeling_signature = (
        settings_signature, candidate_k, int(model_min_df), float(model_max_df),
        int(bin_duration), int(top_words),
    )
    if st.button("Run automatic topic modeling and evolution", type="primary", disabled=not pre_current,
                 key="run-automatic-topic-modeling"):
        try:
            with st.spinner("Evaluating candidate models, selecting optimal k, and training final LDA/NMF models…"):
                evaluation = run_topic_model_evaluation(
                    preprocessing["data"], candidate_k,
                    min_df=int(model_min_df), max_df=float(model_max_df),
                )
                final = run_final_topic_models(
                    preprocessing["data"], evaluation["best_k"], evaluation["best_nmf_k"],
                    bin_duration=int(bin_duration), top_words=int(top_words),
                    min_df=int(model_min_df), max_df=float(model_max_df),
                )
                st.session_state["topic_evaluation_results"] = evaluation
                st.session_state["final_topic_model_results"] = final
                st.session_state["automatic_topic_model_signature"] = modeling_signature
                st.session_state.pop("advanced_thematic_results", None)
            st.success("Automatic topic selection and final model training complete.")
        except (ValueError, KeyError) as exc:
            st.error(f"Automatic topic modeling could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected value stopped topic modeling: {exc}")
    evaluation = st.session_state.get("topic_evaluation_results")
    final = st.session_state.get("final_topic_model_results")
    final_current = (
        evaluation is not None and final is not None
        and st.session_state.get("automatic_topic_model_signature") == modeling_signature
    )
    if final_current:
        for warning in evaluation["warnings"] + final["warnings"]:
            st.warning(warning)
        c1, c2, c3 = st.columns(3)
        c1.metric("Automatically selected LDA k", evaluation["best_k"])
        c2.metric("Automatically selected NMF k", evaluation["best_nmf_k"])
        c3.metric("Coherence method", evaluation["coherence_method"])
        st.markdown("#### LDA topic evolution")
        _render_figure(final, "Topic_Evolution_Proportion", "thematic-final-proportion")
        _render_figure(final, "Topic_Publication_Trends", "thematic-final-lda-counts")
        st.markdown("#### NMF topic evolution")
        _render_figure(final, "NMF_Topic_Trends", "thematic-final-nmf-counts")
        with st.expander("Topic descriptions and article assignments"):
            st.markdown("##### LDA topic descriptions")
            st.dataframe(final["tables"]["lda_topic_descriptions"], width="stretch", hide_index=True)
            st.markdown("##### NMF topic descriptions")
            st.dataframe(final["tables"]["nmf_topic_descriptions"], width="stretch", hide_index=True)
            st.dataframe(final["tables"]["article_topic_assignments"], width="stretch", hide_index=True)
        with st.expander("Automatic model-selection diagnostics and exports"):
            st.dataframe(evaluation["tables"]["topic_model_evaluation"], width="stretch", hide_index=True)
            _stage_downloads(evaluation, "chronotome_topic_evaluation_outputs.zip",
                             "topic_evaluation_tables.xlsx", "thematic-eval")
        _stage_downloads(final, "chronotome_final_topic_models_outputs.zip",
                         "final_topic_model_tables.xlsx", "thematic-final")
    elif final or evaluation:
        st.warning("The preprocessing or evolution settings changed. Rerun automatic topic modeling.")

    _section(6, "Advanced thematic analyses",
             "Topic impact, intellectual intersections, most-cited papers, and country specialization.")
    advanced_left, advanced_middle, advanced_right = st.columns(3)
    cooccurrence_threshold = advanced_left.slider(
        "Co-occurrence probability threshold", 0.01, 0.50, 0.10, 0.01,
        key="thematic-cooccurrence-threshold",
    )
    min_country_documents = advanced_middle.number_input(
        "Minimum documents per country", 1, 500, 10, key="thematic-country-min-docs",
    )
    top_countries = advanced_right.number_input(
        "Countries in specialization heatmap", 1, 50, 20, key="thematic-top-countries",
    )
    advanced_signature = (
        modeling_signature, float(cooccurrence_threshold), int(min_country_documents), int(top_countries),
    )
    if st.button("Run advanced thematic analyses", type="primary", disabled=not final_current,
                 key="run-advanced-thematic"):
        try:
            with st.spinner("Calculating topic impact, co-occurrence, most-cited papers, and specialization…"):
                advanced = run_advanced_thematic_analysis(
                    final["data"], cooccurrence_threshold=float(cooccurrence_threshold),
                    min_country_documents=int(min_country_documents), top_countries=int(top_countries),
                    include_dataset=False,
                )
                advanced.pop("data", None)
                st.session_state["advanced_thematic_results"] = advanced
                st.session_state["advanced_thematic_signature"] = advanced_signature
            st.success("Advanced thematic analyses complete.")
        except (ValueError, KeyError) as exc:
            st.error(f"Advanced thematic analysis could not run: {exc}")
        except Exception as exc:
            st.error(f"An unexpected value stopped advanced thematic analysis: {exc}")
    advanced = st.session_state.get("advanced_thematic_results")
    advanced_current = advanced is not None and st.session_state.get("advanced_thematic_signature") == advanced_signature
    if advanced_current:
        for warning in advanced["warnings"]:
            st.warning(warning)
        st.markdown("#### Topic citation impact (MNCS)")
        st.caption(
            "Topic impact aggregates the corpus-internal year-normalized citation score; "
            "each defined paper score uses the mean citations of retained papers from the same publication year."
        )
        st.dataframe(advanced["tables"]["topic_citation_impact_mncs"], width="stretch", hide_index=True)
        _render_figure(advanced, "topic_citation_impact_mncs", "thematic-advanced-impact")
        st.markdown("#### Topic co-occurrence")
        _render_figure(advanced, "topic_cooccurrence_heatmap", "thematic-advanced-cooccurrence")
        with st.expander("Topic co-occurrence matrix"):
            st.dataframe(advanced["tables"]["topic_cooccurrence_matrix"], width="stretch", hide_index=True)
        st.markdown("#### Most cited article per topic")
        st.dataframe(advanced["tables"]["most_cited_article_per_topic"], width="stretch", hide_index=True)
        with st.expander("All articles by topic and citation"):
            st.dataframe(advanced["tables"]["all_articles_by_topic_and_citation"], width="stretch", hide_index=True)
        if "topic_country_activity_index" in advanced["tables"]:
            st.markdown("#### Topic specialization by country (Activity Index)")
            st.dataframe(advanced["tables"]["topic_country_activity_index"], width="stretch", hide_index=True)
            _render_figure(advanced, "topic_country_specialization_heatmap", "thematic-advanced-country")
        _stage_downloads(advanced, "chronotome_advanced_thematic_outputs.zip",
                         "advanced_thematic_tables.xlsx", "thematic-advanced")
    elif advanced:
        st.warning("The final model or advanced settings changed. Rerun advanced thematic analysis.")

    st.markdown("---")
    if st.button("Continue to institutional analysis", type="primary", key="thematic-to-institutional"):
        navigate_to_page("Institutional analysis")
