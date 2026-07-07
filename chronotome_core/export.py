"""In-memory CSV, figure, and ZIP exports for the Streamlit app."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd


def dataframe_csv(data: pd.DataFrame) -> bytes:
    """Serialize a DataFrame as Excel-friendly UTF-8 CSV."""
    export = data.copy()
    for column in export.columns:
        if export[column].map(lambda x: isinstance(x, (list, dict, tuple, set))).any():
            export[column] = export[column].map(lambda x: json.dumps(list(x) if isinstance(x, set) else x, ensure_ascii=False) if isinstance(x, (list, dict, tuple, set)) else x)
    return export.to_csv(index=False).encode("utf-8-sig")


def dataframe_excel(data: pd.DataFrame, sheet_name="Chronotome") -> bytes:
    """Serialize a DataFrame as an in-memory XLSX workbook."""
    export = data.copy()
    for column in export.columns:
        if export[column].map(lambda x: isinstance(x, (list, dict, tuple, set))).any():
            export[column] = export[column].map(
                lambda x: json.dumps(list(x) if isinstance(x, set) else x, ensure_ascii=False)
                if isinstance(x, (list, dict, tuple, set)) else x
            )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


def figure_png(figure, dpi=220) -> bytes:
    """Render a Matplotlib figure to PNG bytes."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    return buffer.getvalue()


def figure_pdf(figure) -> bytes:
    """Render a Matplotlib figure to PDF bytes."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="pdf", bbox_inches="tight")
    return buffer.getvalue()


def figure_svg(figure) -> bytes:
    """Render a resolution-independent SVG for sharp browser previews."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight")
    return buffer.getvalue()


def create_exports(processed_data, tables, figures) -> dict[str, bytes]:
    """Create individual files and a ZIP containing every generated output."""
    files: dict[str, bytes] = {"cleaned_bibliometric_dataset.csv": dataframe_csv(processed_data)}
    for name, table in tables.items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            files[f"tables/{name}.csv"] = dataframe_csv(table)
    for name, figure in figures.items():
        files[f"figures/{name}.png"] = figure_png(figure)
        files[f"figures/{name}.svg"] = figure_svg(figure)
        files[f"figures/{name}.pdf"] = figure_pdf(figure)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    files["chronotome_outputs.zip"] = buffer.getvalue()
    return files
