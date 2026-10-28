"""
jd package — exposes run(file_path) for the API layer.

ONE loader (jd_loader.JDLoader) reads Job Descriptions of every division. The file format picks
the reader (.docx tables / .pdf text blocks); the division is read from each JD itself.
"""
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd


def _df_to_documents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Text is ONLY the main content the model needs — Job Objective + Responsibilities.
    Division/Unit/Department/Job Title/Job Grade are already stated once in the employee's own
    query, so repeating them on every JD document is pure redundant token cost. Those fields
    stay in `metadata` only — QueryExtractor._match_jd_flexible() matches against metadata.
    """
    docs = []
    for _, row in df.iterrows():
        resps = row.get("responsibilities", [])
        resp_text = "\n".join(f"- {r}" for r in resps) if isinstance(resps, list) else str(resps)
        text = (
            f"Job Objective: {row.get('job_objective','N/A')}\n"
            f"Responsibilities:\n{resp_text}"
        )
        docs.append({
            "text": text.strip(),
            "metadata": {
                "source":     "JD",
                "division":   str(row.get("division", "") or ""),
                "department": str(row.get("department", "") or ""),
                "unit":       str(row.get("unit", "") or ""),
                "job_title":  str(row.get("job_title", "") or ""),
                "job_grade":  str(row.get("job_grade", "")),
            }
        })
    return docs


def run(file_path: Path) -> List[Dict[str, Any]]:
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext in (".docx", ".doc", ".pdf"):
        from .jd_loader import JDLoader
        return _df_to_documents(JDLoader(file_path).load())

    if ext == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return [{"text": text[:8000], "metadata": {"source": "JD", "division": ""}}]

    raise ValueError(f"Unsupported JD file type '{ext}'")
