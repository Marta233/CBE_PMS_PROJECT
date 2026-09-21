"""
Back_End/scripts/API/config.py
Ingestion-specific paths and MIME types. Shared runtime settings live in scripts/config.py.
"""
from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent          # Back_End/scripts/API/
_SCRIPTS_DIR = _HERE.parent                        # Back_End/scripts/
_BACK_END = _SCRIPTS_DIR.parent                    # Back_End/
PROJECT_ROOT = _BACK_END.parent                    # CBE_PMS_PROJECT/
DATA_DIR = _BACK_END / "Data"

for _p in (str(_SCRIPTS_DIR), str(_BACK_END), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import EMBEDDING_MODEL, FAISS_INDEX_PATH, KNOWLEDGE_BASE_FILE  # noqa: E402

UPLOAD_DIR = DATA_DIR / "uploads"
DOCS_DIR = DATA_DIR / "documents"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"

# Keyed by metadata["source"] — the tag stored INSIDE each parsed document
# (see work_plan_loader.py's to_documents(): metadata["source"] = "WorkPlan").
# Used by status.py to count documents already in knowledge_base.json.
DOC_FILES = {
    "BSC": DOCS_DIR / "bsc_documents.json",
    "JD": DOCS_DIR / "jd_documents.json",
    "LOS": DOCS_DIR / "los_documents.json",
    "WorkPlan": DOCS_DIR / "work_plan_documents.json",
}

# Keyed by doc_type — the value the UPLOAD FORM sends (DocType Literal in
# ingest.py: "BSC" | "JD" | "LOS" | "WP"). This is a DIFFERENT key space
# from DOC_FILES above — "WP" here, not "WorkPlan" — because this dict is
# looked up as ACCEPTED_TYPES[doc_type], and doc_type is always "WP".
ACCEPTED_TYPES = {
    "BSC": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "application/pdf",
    },
    "JD": {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
    },
    "LOS": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "application/pdf",
    },
    "WP": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    },
}

for _d in (UPLOAD_DIR, DOCS_DIR, VECTORSTORE_DIR):
    _d.mkdir(parents=True, exist_ok=True)