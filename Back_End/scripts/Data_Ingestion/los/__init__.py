"""
los package — exposes run(file_path) for the API layer.
"""
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

_COL_CONFIG = {
    "perspective_col":    0,
    "strategic_obj_col":  1,
    "division_obj_col":   2,
    "department_obj_col": 3,
    "unit_obj_col":       4,
}


def run(file_path: Path) -> List[Dict[str, Any]]:
    ext = file_path.suffix.lower()

    if ext in (".xlsx", ".xls"):
        from .LOS_loader import LOSLoader
        loader = LOSLoader(file_path, config=_COL_CONFIG)
        loader.load_all_sheets()
        loader.clean_all_sheets(start_row=1)
        loader.merge_data()
        return loader.to_documents()

    if ext == ".csv":
        df = pd.read_csv(file_path)
        df.columns = [c.lower().strip() for c in df.columns]
        docs = []
        for _, row in df.iterrows():
            text = "\n".join(f"{k.replace('_',' ').title()}: {v}" for k, v in row.items() if pd.notna(v))
            docs.append({"text": text, "metadata": {"source": "LOS", "division": str(row.get("division","Digital Banking Division")), "department": str(row.get("department",""))}})
        return docs

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        docs = []
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                docs.append({"text": text, "metadata": {"source": "LOS", "division": "Unknown", "department": ""}})
        return docs

    raise ValueError(f"Unsupported LOS file type '{ext}'")
