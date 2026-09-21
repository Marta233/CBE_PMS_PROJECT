"""
WP package — exposes run(file_path) for the API layer, exactly the same
way Data_Ingestion/los/__init__.py exposes run() for LOS. No separate
top-level wp.py module — this __init__.py IS the entry point ingest.py's
dispatch table imports.
"""
from pathlib import Path
from typing import Any, Dict, List

from .config import DEPARTMENT_ALIASES, QUARTER_LABELS, QUARTER_NUMBERS
from .work_plan_loader import WorkPlanLoader

_LOADER_CONFIG = {
    "QUARTER_LABELS": QUARTER_LABELS,
    "QUARTER_NUMBERS": QUARTER_NUMBERS,
    "DEPARTMENT_ALIASES": DEPARTMENT_ALIASES,
}


def run(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parse one Work Plan docx into embedding-ready YEARLY objective
    documents (one per Division Objective + Unit, spanning Q1-Q4).
    Matches bsc/jd/los's run(file_path) -> list[dict] contract exactly,
    so ingest.py's dispatch table treats WP identically to the other
    three sources.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in (".docx", ".doc"):
        raise ValueError(f"Unsupported Work Plan file type '{ext}' — expected .docx")

    loader = WorkPlanLoader(Path(file_path), config=_LOADER_CONFIG)
    loader.load().clean()
    return loader.to_documents()