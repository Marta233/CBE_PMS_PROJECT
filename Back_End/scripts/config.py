# config.py — absolute paths built from this file's location
# No matter where you run uvicorn from, paths always resolve correctly.
from pathlib import Path

# config.py lives at:  Back_End/scripts/config.py
# DATA_DIR resolves to: Back_End/Data/
_HERE    = Path(__file__).resolve().parent          # Back_End/scripts/
DATA_DIR = _HERE.parent / "Data"                   # Back_End/Data/

EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"

FAISS_INDEX_PATH = DATA_DIR / "vectorstore" / "bsc_faiss_index"
LOS_DATA_PATH    = DATA_DIR / "processed"   / "los_documents.JSON"
JD_DATA_PATH     = DATA_DIR / "processed"   / "jd_documents.JSON"
BSC_Data_PATH    = DATA_DIR / "processed"   / "bsc_documents.JSON"