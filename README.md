# Chronotome

Chronotome is a Streamlit conversion of the original reproducible Jupyter/Kaggle bibliometric workflow. It accepts Scopus and Web of Science exports, harmonizes their schemas, fuses and deduplicates records, corrects for collection-year indexing lag, and produces the notebook's descriptive, citation, source, author, country, thematic, and institutional-network outputs.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

No notebook interface or local data paths are required. All uploaded and generated files are handled in memory.

## App pages

- **Home** introduces Chronotome, its expected outputs, the Zenodo open-science release, the bundled institution aliases, and the suggested citation.
- **Data ingestion** provides separate Scopus and WoS configuration, Single file and Appendage modes, upload verification, deterministic preprocessing, schema harmonization, deduplication, textual PRISMA reporting, and final CSV/Excel/ZIP downloads.
- **Entity resolution** explodes affiliations, standardizes institutions and countries, accepts the bundled or an uploaded `institutions.json`, reports alias conflicts and unresolved geography, and exports affiliation/article-level tables.
- **Corpus & production** automatically analyzes the current entity-resolved article summary and reproduces notebook sections 9 and 11–16: corpus characteristics, internal MNCS, document typology, author productivity/contribution, annual growth, citation dynamics, and local journal/source impact.
- **Geographic analysis** automatically analyzes the current MNCS-enriched corpus and reproduces notebook Sections 17–18 and 20–21: country distribution, SCP/MCP collaboration, country MNCS, citation prestige, the productivity-impact matrix, the international collaboration network, and clickable country case studies.
- **Advanced analyses** runs after the geographic phase and produces the final paper-ready dataset summary, article and author impact rankings, Bradford scattering, hot papers, team-size impact, and the journal landscape.
- **Thematic analysis** uses the current geographic dataset or prepares one uploaded Chronotome dataset in the background. It provides staged NLTK setup, optional query-term removal, visible editable noise-list categories, 1–4 gram extraction and word clouds, automatic LDA/NMF topic selection, longitudinal topic evolution, topic impact/co-occurrence, canonical papers, and country specialization.
- **Institutional analysis** uses the current geographic dataset or the unchanged `article_summary_with_country_classification` handoff file. A six-option dropdown generates one Global/EU × All/MCP/SCP network at a time, with publication rankings, collaboration maps, on-demand Cividis community visualizations, GraphML/CSV/Excel exports, and optional topic-specific networks.
- **Full workflow** provides a single **Run all workflow** action. It starts from raw Scopus/WoS files or the current ingestion result, executes every modern stage through all six institutional community visualizations, and returns one structured ZIP containing the workflow's Excel files, plots, network exports, and manifest.
  The background runner streams stage artifacts directly into the master archive, releases completed figures and graphs, avoids nested ZIP/dataset duplication, and records process-memory usage after every stage.

## Input files

Upload one or more exports in `.csv`, `.txt`, `.xls`, or `.xlsx` format:

- Scopus CSV is recommended. The app recognizes fields such as `Title`, `Source title`, `Year`, `Cited by`, `Authors`, and `Affiliations`.
- Web of Science tab-delimited TXT, CSV, XLS, and XLSX are supported. WoS files with an `.xls` extension that are actually tab-delimited text use the notebook's fallback parser.
- Tagged WoS plain text (`PT`, `AU`, `TI`, …, `ER`) is also parsed.
- Split files from the same database can be uploaded together and are appended before harmonization.
- At minimum, the export must contain the source-specific title field (`Title` for Scopus or `Article Title` for WoS). Full records with cited references are strongly recommended.

The app detects the database from the export columns. It does not infer or fetch missing records from external services.

In **Appendage** mode, files must represent one numbered split-export series, such as `query_1.csv`, `query_2.csv`, and `query_3.csv`. Chronotome verifies the common base name and extension, checks for duplicate or missing part numbers, and sorts parts numerically before stacking them. Scopus and WoS appendages are always processed separately.

## Supported workflow

The Streamlit app preserves the notebook's current methods:

- Scopus/WoS schema mapping and merged common schema
- author-name and cited-reference preprocessing
- preprocessing audit tables for author delimiter changes, removed Scopus IDs, parsed references, and mapped fields
- DOI normalization, citation-prioritized DOI data fusion, and title/year deduplication for records without DOI
- optional collection-year cutoff for indexing-lag correction
- PRISMA-style identification, screening, and included counts
- notebook-style textual PRISMA report with an arithmetic integrity check (no PRISMA diagram)
- curated institution alias resolution using `chronotome_core/institutions.json`
- optional runtime upload of a manually updated or newer Zenodo `institutions.json`; uploaded JSON is validated and treated as authoritative
- affiliation-based institution and country extraction, including SCP/MCP classification
- internal year-normalized citation score (MNCS relative to the uploaded corpus)
- corpus summary, annual production, citation dynamics, and document-type taxonomy
- author full/fractional counts, citations, MNCS, and local h-index
- source productivity and local h-, g-, m-index and MNCS rankings, with the notebook's composite and prestige-versus-efficiency figures
- country-level full-counted production, SCP/MCP collaboration shares, total citations, and internal MNCS rankings
- advanced country citation distribution, productivity-impact matrix, and weighted international collaboration topology
- click-to-open country case studies with temporal dashboards and statistical field-guide exports
- final corpus summary plus advanced article, author, source, Bradford, hot-paper, and collaboration-impact outputs
- most-cited articles, recent highly cited papers, Bradford scattering, and team-size impact
- country productivity, collaboration, impact, and temporal tables
- Global and EU-only institutional networks for All, MCP, and SCP records
- optional topic-level institutional collaboration networks after LDA modeling
- opt-in, auto-scaled K-fold centrality robustness, Louvain community stability, and configuration-model significance testing
- one-click background execution from ingestion through six institutional community visualizations, with a consolidated non-nested ZIP package
- unigram, bigram, trigram, quadgram, LDA/NMF evaluation, topic-assignment, and topic-evolution tables
- CSV, Excel, 600-DPI PNG, vector SVG/PDF, and complete ZIP exports

The main entry point is:

```python
from chronotome_core import run_chronotome

results = run_chronotome(uploaded_files, config)
```

`results` contains processed data, tables, figures, warnings, metadata, network objects, PRISMA counts, and in-memory export files.

## Notebook assumptions retained

- DOI duplicates retain the most-cited record as the base and fill its missing fields from duplicates.
- Records without DOI are deduplicated by normalized title plus publication year.
- Citation normalization uses the uploaded corpus's mean citations for each publication year; it is not an external field benchmark.
- The collection year and later are excluded by default because those years may be incompletely indexed.
- Country and institution extraction uses semicolon-separated affiliations and comma-separated address components.
- Multi-country publications are MCP; one-country publications are SCP.
- EU network subsets include publications whose detected countries are exclusively EU member states.
- At most 50 institutions per paper are used to construct collaboration pairs by default.
- “Hot papers” means papers from the current year and previous three years, ranked by raw citations.
- Source and country impact rankings default to a minimum of five papers.
- Thematic analysis combines title, abstract, author keywords, and Keywords Plus.

## Not yet supported

- **OpenAlex integration is not implemented yet.**
- No APIs are called to enrich incomplete metadata.
- The app does not replace missing affiliations, abstracts, references, or citation counts.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub, including `app.py`, `requirements.txt`, `chronotome_core/`, and `chronotome_core/institutions.json`.
2. In [Streamlit Community Cloud](https://streamlit.io/cloud), create an app from the repository.
3. Set the main file path to `app.py`.
4. Deploy. No secrets or external API keys are needed.

Large exports and dense networks can approach Community Cloud memory/time limits. For those datasets, disable thematic analysis or reduce the number of institutions displayed in network plots.

Analytical figure downloads preserve the notebook styling and filenames. Standard figures are exported as 600-DPI PNG plus vector SVG and PDF; oversized network rasters are safely bounded while SVG/PDF remain resolution-independent. Tables are available as individual CSV files and combined Excel workbooks inside ZIP folders organized into `Plots/` and `Results/`.

For memory safety, oversized raster figures use an adaptive pixel ceiling while retaining their original aspect ratio and layout. Full-resolution SVG and PDF remain the publication masters. The one-click background workflow uses a stricter raster budget, streams outputs stage by stage, and keeps only its final archive and manifest in session memory.
