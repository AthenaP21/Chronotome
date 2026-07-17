# Chronotome

Chronotome is a bibliometric workflow for Scopus and Web of Science exports. It provides a local Streamlit application and a Python API for data preparation, descriptive bibliometrics, geographic analysis, thematic analysis, and institutional collaboration networks.

- PyPI: [pypi.org/project/chronotome](https://pypi.org/project/chronotome/)
- Source code: [github.com/AthenaP21/Chronotome](https://github.com/AthenaP21/Chronotome)
- Zenodo record: [doi.org/10.5281/zenodo.17514930](https://doi.org/10.5281/zenodo.17514930)

## Install Chronotome

Chronotome supports Python 3.11 and 3.12. Python 3.11 is used in the examples below.

### 1. Verify Python 3.11

On macOS or Linux:

```bash
python3.11 --version
```

On Windows PowerShell:

```powershell
py -3.11 --version
```

The result should begin with:

```text
Python 3.11
```

If the command is unavailable, install Python 3.11 from [python.org/downloads](https://www.python.org/downloads/), reopen the terminal, and run the version command again.

### 2. Create a virtual environment

A virtual environment keeps Chronotome and its dependencies separate from other Python installations.

On macOS or Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python --version
```

On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python --version
```

After activation, `python --version` should report Python 3.11.x.

If PowerShell blocks activation, run the following command in the same terminal and activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
```

### 3. Verify and update pip

```bash
python -m pip --version
python -m pip install --upgrade pip
```

### 4. Install Chronotome from PyPI

Chronotome is installable as a local Python package. Python 3.11 is recommended.

```bash
git clone https://github.com/AthenaP21/Chronotome.git
cd Chronotome
python3.11 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: .
chronotome
```

The `chronotome` command starts the app at `http://127.0.0.1:8501`; it is deliberately limited to the local machine. Use `chronotome --port 8502` if port 8501 is already occupied. For local development, the familiar command remains available:

```bash
pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1
```

No notebook interface or local data paths are required. All uploaded and generated files are handled in memory. See the in-app **Local installation** page and [SECURITY.md](SECURITY.md) for the installation and release-safety guidance.

### Local installation

- **Home** introduces Chronotome, its expected outputs, the Zenodo open-science release, the bundled institution aliases, and the suggested citation.
- **Data ingestion** provides separate Scopus and WoS configuration, Single file and Appendage modes, upload verification, deterministic preprocessing, schema harmonization, deduplication, textual PRISMA reporting, and final CSV/Excel/ZIP downloads.
- **Entity resolution** explodes affiliations, standardizes institutions and countries, accepts the bundled or an uploaded `institutions.json`, reports alias conflicts and unresolved geography, and exports affiliation/article-level tables.
- **Corpus & production** uses the current entity-resolved article summary and starts only when **Generate corpus analysis** is selected. It reproduces notebook sections 9 and 11–16: corpus characteristics, internal MNCS, document typology, author productivity/contribution, annual growth, citation dynamics, and local journal/source impact.
- **Geographic analysis** starts only when **Generate geographic analysis** is selected. It reproduces notebook Sections 17–18 and 20–21: country distribution, SCP/MCP collaboration, country MNCS, citation prestige, the productivity-impact matrix, the international collaboration network, and clickable country case studies.
- **Advanced analyses** runs after the geographic phase and produces the final paper-ready dataset summary, article and author impact rankings, Bradford scattering, hot papers, team-size impact, and the journal landscape.
- **Thematic analysis** uses the current geographic dataset or prepares one uploaded Chronotome dataset in the background. It provides staged NLTK setup, optional query-term removal, visible editable noise-list categories, 1–4 gram extraction and word clouds, automatic LDA/NMF topic selection, longitudinal topic evolution, topic impact/co-occurrence, canonical papers, and country specialization.
- **Institutional analysis** uses the current geographic dataset or the unchanged `article_summary_with_country_classification` handoff file. Choose one Global/EU × All/MCP/SCP scope and select **Generate institutional network** to create it. Completed scopes can be compared side by side using their original network graphs; the page also offers community visualizations, GraphML/CSV/Excel exports, and optional topic-specific networks.
- **Full workflow** provides a single **Run all workflow** action. It starts from raw Scopus/WoS files or the current ingestion result, executes every modern stage through all six institutional community visualizations, and returns one structured ZIP containing the workflow's Excel files, plots, network exports, and manifest.
  The background runner streams stage artifacts directly into the master archive, releases completed figures and graphs, avoids nested ZIP/dataset duplication, and records process-memory usage after every stage.
- **Local installation** is a step-by-step guide to installing, launching, updating, and securing Chronotome on your own computer.

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
- one-click background execution from ingestion through six institutional community visualizations, with a consolidated non-nested ZIP package
- unigram, bigram, trigram, quadgram, LDA/NMF evaluation, topic-assignment, and topic-evolution tables
- CSV, Excel, 600-DPI PNG, vector SVG/PDF, and complete ZIP exports

The main entry point is:

```python
from chronotome import run_chronotome
```

Signature:

```python
def run_chronotome(
    *,
    scopus_files=None,
    wos_files=None,
    modes=None,
    config=None,
    ingestion_result=None,
    progress_callback=None,
) -> dict:
    ...
```

Example:

```python
from pathlib import Path
from chronotome import run_chronotome

with Path("scopus_export.csv").open("rb") as scopus:
    result = run_chronotome(
        scopus_files=[scopus],
        modes={"Scopus": "single", "WoS": "single"},
        config={"collection_year": 2026},
    )

processed_data = result["processed_data"]
workflow_zip = result["exports"]["chronotome_complete_background_workflow.zip"]
```

The result contains:

| Key | Contents |
|---|---|
| `processed_data` | Enriched article-level pandas DataFrame |
| `stages` | Status and resource summaries for completed stages |
| `manifest` | Workflow stage manifest |
| `warnings` | Data-quality and availability warnings |
| `exports` | Downloadable files stored as bytes |
| `metadata` | Workflow and input metadata |
| `config` | Resolved configuration values |

### Configuration keys

| Key | Default | Purpose |
|---|---:|---|
| `enable_time_filter` | `True` | Keep records before the collection year |
| `collection_year` | `None` | Collection-year cutoff; `None` uses the current year |
| `top_n` | `10` | Number of records in applicable rankings |
| `min_source_papers` | `5` | Minimum papers in source-impact rankings |
| `max_source_title_length` | `30` | Maximum source-title length used in source plots |
| `country_min_papers` | `5` | Minimum papers in country-impact rankings |
| `institutional_top_n_plot` | `30` | Institutions shown in an institutional network |
| `max_institutions_per_paper` | `50` | Institution threshold for collaboration-edge construction |
| `topic_k_values` | `3` through `10` | Topic counts evaluated for LDA and NMF |
| `thematic_min_df` | `None` | Automatic n-gram document-frequency threshold |
| `topic_model_min_df` | `2` | Topic-model document-frequency threshold |
| `topic_bin_duration` | `5` | Years in each topic-evolution interval |
| `run_topic_institutional` | `True` | Run topic-specific institutional analysis when topic results are available |
| `community_top_n_global` | `50` | Institutions shown in global community figures |
| `community_top_n_eu` | `30` | Institutions shown in EU community figures |

Unknown configuration keys raise `ValueError`.

## Citation

```text
Popescu-Apreutesei, L.-E., & Iosupescu, M.-S. (2025). Chronotome. Zenodo. https://doi.org/10.5281/zenodo.17514930
```

## Security

The packaged launcher binds Streamlit to `127.0.0.1`. Uploaded bibliographic files and generated outputs are processed by the local Python process. See [SECURITY.md](SECURITY.md) for the project security policy.
