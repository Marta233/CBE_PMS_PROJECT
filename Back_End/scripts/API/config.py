"""
Back_End/scripts/API/config.py
Unified configuration for both ingestion and generation APIs.
"""
from pathlib import Path
import sys

# ── Anchor paths ──────────────────────────────────────────────────────────────
_HERE        = Path(__file__).resolve().parent          # Back_End/scripts/API/
_SCRIPTS_DIR = _HERE.parent                             # Back_End/scripts/
_BACK_END    = _SCRIPTS_DIR.parent                      # Back_End/
PROJECT_ROOT = _BACK_END.parent                         # CBE_PMS_PROJECT/
DATA_DIR     = _BACK_END / "Data"                       # Back_End/Data/

# ── Add scripts root to sys.path so embedding/llm packages are importable ─────
for _p in (str(_SCRIPTS_DIR), str(_BACK_END), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Embedding model ───────────────────────────────────────────────────────────
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# ── Shared data directories ───────────────────────────────────────────────────
UPLOAD_DIR    = DATA_DIR / "uploads"
DOCS_DIR      = DATA_DIR / "documents"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"

# ── Knowledge base (single merged JSON used by generation) ───────────────────
KNOWLEDGE_BASE_FILE = DOCS_DIR / "knowledge_base.json"

# ── FAISS index (BSC embeddings, used by generation) ─────────────────────────
FAISS_INDEX_PATH = VECTORSTORE_DIR / "bsc_faiss_index"

# ── Per-type document stores (legacy, kept for status endpoint) ───────────────
DOC_FILES = {
    "BSC": DOCS_DIR / "bsc_documents.json",
    "JD":  DOCS_DIR / "jd_documents.json",
    "LOS": DOCS_DIR / "los_documents.json",
}

# ── Accepted MIME types per doc type ─────────────────────────────────────────
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
}

# ── Ensure all directories exist ──────────────────────────────────────────────
for _d in (UPLOAD_DIR, DOCS_DIR, VECTORSTORE_DIR):
    _d.mkdir(parents=True, exist_ok=True)