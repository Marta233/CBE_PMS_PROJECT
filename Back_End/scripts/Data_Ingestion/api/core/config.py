"""
api/core/config.py
API-level paths and accepted file types only.
All pipeline logic lives in data_ingestion/bsc|jd|los/.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]   # E:\PMS\CBE_PMS_PROJECT
DATA_ROOT    = PROJECT_ROOT / "Back_End" / "Data"

UPLOAD_DIR = DATA_ROOT / "uploads"
DOCS_DIR   = DATA_ROOT / "documents"
INDEX_DIR  = DATA_ROOT / "vectorstore"          # ← was missing

for _d in (UPLOAD_DIR, DOCS_DIR, INDEX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DOC_FILES = {
    "BSC": DOCS_DIR / "bsc_documents.json",
    "JD":  DOCS_DIR / "jd_documents.json",
    "LOS": DOCS_DIR / "los_documents.json",
}

FAISS_INDEX_PATH = INDEX_DIR / "knowledge_base.index"
FAISS_META_PATH  = INDEX_DIR / "knowledge_base_meta.json"

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