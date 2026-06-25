"""
jd package — exposes run(file_path) for the API layer.
"""
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd


def _df_to_documents(df: pd.DataFrame, division: str) -> List[Dict[str, Any]]:
    docs = []
    for _, row in df.iterrows():
        resps = row.get("responsibilities", [])
        resp_text = "\n".join(f"- {r}" for r in resps) if isinstance(resps, list) else str(resps)
        text = (
            f"Division: {row.get('division', division)}\n"
            f"Unit: {row.get('unit','')}\n"
            f"Department: {row.get('department','')}\n"
            f"Job Title: {row.get('job_title','')}\n"
            f"Job Grade: {row.get('job_grade','N/A')}\n"
            f"Job Objective: {row.get('job_objective','N/A')}\n"
            f"Responsibilities:\n{resp_text}"
        )
        docs.append({
            "text": text.strip(),
            "metadata": {
                "source":     "JD",
                "division":   str(row.get("division", division)),
                "department": str(row.get("department","")),
                "unit":       str(row.get("unit","")),
                "job_title":  str(row.get("job_title","")),
                "job_grade":  str(row.get("job_grade","")),
            }
        })
    return docs


def run(file_path: Path) -> List[Dict[str, Any]]:
    ext = file_path.suffix.lower()

    if ext in (".docx", ".doc"):
        from .rbb_loader import RBBLoader
        return _df_to_documents(RBBLoader(file_path).load(), "Retail & Branch Banking")

    if ext == ".pdf":
        from .digital_loader import DigitalLoader
        return _df_to_documents(DigitalLoader(file_path).load(), "Digital Banking")

    if ext == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return [{"text": text[:8000], "metadata": {"source": "JD", "division": "Unknown"}}]

    raise ValueError(f"Unsupported JD file type '{ext}'")
