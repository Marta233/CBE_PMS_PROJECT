"""
embedding/config.py
Paths and model settings only.
Data is loaded from knowledge_base.json — no pipeline re-runs.
"""
from pathlib import Path

PROJECT_ROOT     = Path(__file__).resolve().parents[3]
DATA_ROOT        = PROJECT_ROOT / "Back_End" / "Data"

KNOWLEDGE_BASE_FILE = DATA_ROOT / "documents" / "knowledge_base.json"
VECTORSTORE_PATH    = DATA_ROOT / "vectorstore"
FAISS_INDEX_PATH    = VECTORSTORE_PATH / "bsc_faiss_index"

VECTORSTORE_PATH.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
