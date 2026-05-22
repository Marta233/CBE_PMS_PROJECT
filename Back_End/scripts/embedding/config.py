# embedding_config.py
"""Embedding + FAISS configuration"""

from pathlib import Path


# =========================================================
# PATHS
# =========================================================

# prepare_all_embeddings.py
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from scripts.Data_Ingestion.BSC_Data.bsc_main import run_bsc_pipeline
from scripts.Data_Ingestion.LOS_Data.LOS_main import run_los_pipeline
from scripts.Data_Ingestion.JD_Data.jd_main import run_pipeline   # JD pipeline

jd_df, jd_docs = run_pipeline()
print('JD Data successfully processed. Shape:', jd_df.shape)
bsc_df, bsc_docs = run_bsc_pipeline()
print('BSC Data successfully processed. Shape:', bsc_df.shape)
los_df, los_docs = run_los_pipeline()
print('LOS Data successfully processed. Shape:', los_df.shape)


VECTORSTORE_PATH = Path("Back_End/Data/vectorstore")

VECTORSTORE_PATH.mkdir(parents=True, exist_ok=True)


# =========================================================
# INPUT FILES
# =========================================================

BSC_DOCUMENTS = bsc_docs

LOS_DOCUMENTS = los_docs

JD_DOCUMENTS = jd_docs

# =========================================================
# FAISS OUTPUT
# =========================================================

FAISS_INDEX_PATH = (
    VECTORSTORE_PATH / "bsc_faiss_index"
)

# =========================================================
# EMBEDDING MODEL
# =========================================================

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"