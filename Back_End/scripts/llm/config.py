# config.py — absolute paths built from this file's location
# No matter where you run uvicorn from, paths always resolve correctly.
import os
from pathlib import Path

# config.py lives at:  Back_End/scripts/config.py
# DATA_DIR resolves to: Back_End/Data/
_HERE    = Path(__file__).resolve().parent          # Back_End/scripts/
DATA_DIR = _HERE.parent / "Data"                   # Back_End/Data/

EMBEDDING_MODEL  = "BAAI/bge-small-en-v1.5"

FAISS_INDEX_PATH = DATA_DIR / "vectorstore" / "bsc_faiss_index"
FAISS_DIVISION_INDEX_DIR = DATA_DIR / "vectorstore" / "divisions"
LOS_DATA_PATH    = DATA_DIR / "processed"   / "los_documents.JSON"
JD_DATA_PATH     = DATA_DIR / "processed"   / "jd_documents.JSON"
BSC_Data_PATH    = DATA_DIR / "processed"   / "bsc_documents.JSON"

# ── Scalability / async queue ────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# When true, POST /api/generate returns 202 + job_id (requires Redis + Celery worker).
USE_ASYNC_QUEUE = os.getenv("PMS_USE_ASYNC_QUEUE", "true").lower() in ("1", "true", "yes")

# Retrieval cache — repeat profiles skip FAISS/JD scan (LRU + TTL).
RETRIEVAL_CACHE_TTL = int(os.getenv("PMS_RETRIEVAL_CACHE_TTL", str(24 * 3600)))
RETRIEVAL_CACHE_MAX_SIZE = int(os.getenv("PMS_RETRIEVAL_CACHE_MAX_SIZE", "256"))

# Step 1 draft cache — repeat regeneration skips first LLM call when context unchanged.
STEP1_CACHE_TTL = int(os.getenv("PMS_STEP1_CACHE_TTL", str(24 * 3600)))
STEP1_CACHE_MAX_SIZE = int(os.getenv("PMS_STEP1_CACHE_MAX_SIZE", "128"))

# Job result TTL in Redis (seconds).
JOB_RESULT_TTL = int(os.getenv("PMS_JOB_RESULT_TTL", str(3600)))

# ── LLM backend: "ollama" (default) or "vllm" ─────────────────────────────────
LLM_BACKEND = os.getenv("PMS_LLM_BACKEND", "ollama").lower()
OLLAMA_MODEL = os.getenv("PMS_OLLAMA_MODEL", "llama3")
VLLM_BASE_URL = os.getenv("PMS_VLLM_BASE_URL", "http://localhost:8001/v1")
VLLM_MODEL = os.getenv("PMS_VLLM_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")

# Per-request LLM timeouts (seconds). Hung calls fail instead of blocking workers forever.
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("PMS_OLLAMA_TIMEOUT", "600"))
OLLAMA_HEALTH_TIMEOUT_SECONDS = float(os.getenv("PMS_OLLAMA_HEALTH_TIMEOUT", "5"))
VLLM_TIMEOUT_SECONDS = float(os.getenv("PMS_VLLM_TIMEOUT", "600"))

# Append-only timing log for LLM requests (speed / timeout tracking).
LLM_PERF_LOG_PATH = Path(os.getenv("PMS_LLM_PERF_LOG", str(DATA_DIR / "logs" / "llm_performance.log")))

# Max concurrent in-flight Ollama chat requests on this process (serialize when 1).
OLLAMA_MAX_CONCURRENT = max(1, int(os.getenv("PMS_OLLAMA_MAX_CONCURRENT", "1")))
