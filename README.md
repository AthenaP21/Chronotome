# Chronotome

Chronotome is a bibliometric workflow for Scopus and Web of Science exports. It provides a local Streamlit application and a Python API for data preparation, descriptive bibliometrics, geographic analysis, thematic analysis, and institutional collaboration networks.

- PyPI: [pypi.org/project/chronotome](https://pypi.org/project/chronotome/)
- Source code: [github.com/AthenaP21/Chronotome](https://github.com/AthenaP21/Chronotome)
- Zenodo record: [doi.org/10.5281/zenodo.17514930](https://doi.org/10.5281/zenodo.22646135)

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

```bash
python -m pip install chronotome
```

Confirm the installed version and location:

```bash
python -m pip show chronotome
chronotome --help
```

### 5. Start Chronotome

```bash
chronotome
```

Chronotome opens at `http://127.0.0.1:8501`. If the browser does not open, enter that address manually. Keep the terminal open while the application is running and press `Ctrl+C` to stop it.

Alternative commands:

```bash
python -m chronotome
chronotome --port 8502
chronotome --no-browser
```

### Open Chronotome again later

Activate the same virtual environment before starting the application.

On macOS or Linux:

```bash
source .venv/bin/activate
chronotome
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
chronotome
```

### Upgrade Chronotome

```bash
python -m pip install --upgrade chronotome
```

### Uninstall Chronotome

```bash
python -m pip uninstall chronotome
```

## Application pages

### Home

Introduces the workflow, principal outputs, Zenodo record, institution alias resource, and suggested citation.

### Local installation

Lists the PyPI installation, update, launch, and removal commands for macOS, Linux, and Windows. This page is the second item in the sidebar.

### Data ingestion

Loads Scopus and Web of Science exports in single-file or split-export mode. It verifies filenames and schemas, harmonizes database fields, preprocesses author and reference data, fuses duplicate records, applies the optional collection-year cutoff, reports PRISMA-style counts, and exports the processed corpus.

### Entity resolution

Resolves affiliation strings into institution and country fields. It uses the bundled institution alias file or a user-supplied `institutions.json`, reports alias conflicts and unresolved values, and exports affiliation-level and article-level tables.

### Corpus & production

Uses the current entity-resolved article dataset. Configure the corpus settings and select **Generate corpus analysis** to calculate corpus descriptors, MNCS, document types, author indicators, annual production, citation dynamics, and source indicators.

### Geographic analysis

Uses the current corpus dataset. Configure the country settings and select **Generate geographic analysis** to calculate country output, SCP/MCP collaboration, country impact, citation distributions, the performance matrix, and the international collaboration network. Country names in the results open a country profile.

### Advanced analyses

Produces the final dataset summary, most-cited article and author rankings, Bradford scattering, recent highly cited papers, team-size citation analysis, and the source productivity-impact landscape.

### Thematic analysis

Uses the current geographic-analysis dataset or an uploaded Chronotome dataset. It provides editable noise-word lists, optional removal of database search terms, n-gram tables and word clouds, automatic LDA and NMF topic-count evaluation, final topic models, topic evolution, topic impact, topic co-occurrence, representative papers, and country specialization.

### Institutional analysis

Uses the current geographic dataset or the geographic-analysis handoff file. Choose one of six scopes: Global All, Global MCP, Global SCP, EU All, EU MCP, or EU SCP. Select **Generate institutional network** to produce the institution ranking and collaboration graph. Completed scopes can be compared side by side. Community and topic-specific institutional views are available from the same page.

### Full workflow

Runs the sequence from data ingestion through institutional community figures. Select **Run all workflow** to execute the analyses and download one ZIP containing tables, figures, network files, the enriched dataset, and the workflow manifest.

## Input files

Chronotome accepts Scopus and Web of Science exports in these formats:

- `.csv`
- `.txt`
- `.xls`
- `.xlsx`

Scopus CSV and Web of Science tab-delimited TXT are the preferred formats. Web of Science tagged plain text is also recognized. Some Web of Science exports use an `.xls` filename for tab-delimited text; Chronotome checks the file content before selecting the reader.

At minimum, each source file must contain its database-specific title field. Complete records should include:

- article title;
- authors and full author names;
- publication year;
- source title;
- document type;
- DOI;
- citation count;
- affiliations and addresses;
- abstract;
- author keywords;
- Keywords Plus or indexed keywords;
- cited references or cited-reference count.

### Single-file mode

Use this mode when one file contains the complete export from a database. Scopus-only, Web of Science-only, and combined Scopus/Web of Science workflows are accepted.

### Split-export mode

Use this mode when a database export was divided into numbered files. Files must share the same base name and extension, with a continuous numeric suffix such as:

```text
query_1.csv
query_2.csv
query_3.csv
```

Scopus and Web of Science split series are checked and combined separately.

## Workflow

Chronotome implements the following operations from the project notebook:

1. File verification and source detection.
2. Single-file and split-export ingestion.
3. Scopus and Web of Science schema harmonization.
4. Author-name preprocessing and row-level full-name fallback.
5. Cited-reference preservation and reference counting.
6. DOI normalization.
7. Citation-prioritized duplicate fusion.
8. Title-year matching for no-DOI records with complete matching fields.
9. Collection-year filtering for indexing lag.
10. PRISMA-style record accounting.
11. Institution and country resolution.
12. Corpus characteristics and production trends.
13. Corpus-internal year-normalized citation scores.
14. Document-type, author, source, and citation indicators.
15. Country productivity, SCP/MCP collaboration, impact, and networks.
16. Final corpus summary and article, author, source, Bradford, hot-paper, and team-size analyses.
17. N-gram extraction and word clouds.
18. Automatic LDA and NMF topic-count evaluation.
19. Topic assignment, evolution, impact, co-occurrence, representative papers, and country specialization.
20. Global and EU institutional networks for All, MCP, and SCP publications.
21. Topic-specific institutional networks.
22. Seeded single-pass institutional community figures.

Tables are exported as CSV and Excel files. Figures retain the notebook layouts and are exported as PNG, SVG, and PDF where applicable. Institutional networks also include GraphML, node tables, and edge tables.

## Notebook parallels

The bundled [`chronotome.ipynb`](chronotome.ipynb) remains the complete notebook edition. The application organizes its implemented methods as follows:

| Application page | Notebook sections |
|---|---|
| Data ingestion | Phase 1, Sections 1-7 |
| Entity resolution | Section 8 |
| Corpus & production | Part 2, Sections 9-16 |
| Geographic analysis | Sections 17-18 and the country-profile elements of Section 20 |
| Advanced analyses | Final Summary, Core Impact Analyses, and Advanced Visualizations |
| Thematic analysis | Part 3, Sections 21-25 |
| Institutional analysis | Part 4, Sections 26-27, thematic-institutional networks, and community visualization |
| Full workflow | The implemented application sequence above |

The notebook also contains analyses that remain notebook-only:

- longitudinal country productivity cohorts;
- standalone statistical country-report generation;
- repeated institutional network validation, consensus clustering, resampling, null models, stability statistics, and NMI analysis.

These notebook sections can be used when their additional computational requirements and manual controls are appropriate for a study.

## Data preparation details

### Database and file provenance

The processed dataset records:

- `Primary Database`: the source of the record selected during duplicate fusion;
- `Databases`: all databases represented in a fused record;
- `Source Files`: the input filenames represented in a fused record.

Only filename basenames are retained. Local directory paths are not included in exported provenance.

### Duplicate fusion

DOI values are normalized for resolver prefixes, labels, case, whitespace, and trailing citation punctuation. Records sharing a normalized DOI can be fused. Records without a DOI are matched only when both normalized title and publication year are available.

Within a duplicate group, the record with the highest citation count is selected first. Original row order resolves citation ties. Missing fields in that record may be filled from other records in the same group.

### Cited references

`Cited References Raw` retains the exported reference text. `Cited Reference Count` retains a valid database count or derives the number of non-empty semicolon-delimited references when a count is unavailable.

### MNCS

Chronotome defines `MNCS` as the corpus-internal year-normalized citation score:

> A paper's citation count divided by the mean citation count of retained Chronotome corpus papers from the same publication year.

Zero-citation papers are included in the yearly mean. MNCS is undefined when the publication year or citation count is missing, or when the same-year citation mean is zero. Undefined values remain missing in tables and exports.

### Authors and entities

For each paper, Chronotome uses `Author Full Names` when available and falls back to `Authors` for that row. Institution names are standardized during entity resolution. Country aliases are resolved consistently throughout the workflow; for example, `Czech Republic`, `Czech Rep.`, and `Czechia` are reported as `Czechia`.

## Python API

The full workflow is available through:

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
Popescu, L., & Iosupescu, M.-S. (2026). Chronotome: An open-source Python library for bibliometric analysis and network visualization (Version v1) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.22646135
```

## Security

The packaged launcher binds Streamlit to `127.0.0.1`. Uploaded bibliographic files and generated outputs are processed by the local Python process. See [SECURITY.md](SECURITY.md) for the project security policy.
