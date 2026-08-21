# config.py — shared paths and runtime settings for embedding, cache, tasks, and LLM.
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # Back_End/scripts/
DATA_DIR = _HERE.parent / "Data"                 # Back_End/Data/
DOCS_DIR = DATA_DIR / "documents"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

FAISS_INDEX_PATH = DATA_DIR / "vectorstore" / "bsc_faiss_index"
KNOWLEDGE_BASE_FILE = DOCS_DIR / "knowledge_base.json"
RETRIEVED_CONTEXT_PATH = DOCS_DIR / "retrieved_context.json"
GENERATED_OBJECTIVES_PATH = DOCS_DIR / "generated_objectives.json"

# Legacy batch CLI outputs (Data_Ingestion *_main.py only)
LOS_DATA_PATH = DATA_DIR / "processed" / "los_documents.JSON"
JD_DATA_PATH = DATA_DIR / "processed" / "jd_documents.JSON"
BSC_Data_PATH = DATA_DIR / "processed" / "bsc_documents.JSON"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

USE_ASYNC_QUEUE = os.getenv("PMS_USE_ASYNC_QUEUE", "true").lower() in ("1", "true", "yes")

RETRIEVAL_CACHE_TTL = int(os.getenv("PMS_RETRIEVAL_CACHE_TTL", str(24 * 3600)))
RETRIEVAL_CACHE_MAX_SIZE = int(os.getenv("PMS_RETRIEVAL_CACHE_MAX_SIZE", "256"))

STEP1_CACHE_TTL = int(os.getenv("PMS_STEP1_CACHE_TTL", str(24 * 3600)))
STEP1_CACHE_MAX_SIZE = int(os.getenv("PMS_STEP1_CACHE_MAX_SIZE", "128"))

JOB_RESULT_TTL = int(os.getenv("PMS_JOB_RESULT_TTL", str(3600)))

LLM_BACKEND = os.getenv("PMS_LLM_BACKEND", "ollama").lower()
OLLAMA_MODEL = os.getenv("PMS_OLLAMA_MODEL", "llama3")
VLLM_BASE_URL = os.getenv("PMS_VLLM_BASE_URL", "http://localhost:8001/v1")
VLLM_MODEL = os.getenv("PMS_VLLM_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")

OLLAMA_TIMEOUT_SECONDS = float(os.getenv("PMS_OLLAMA_TIMEOUT", "3000"))
OLLAMA_HEALTH_TIMEOUT_SECONDS = float(os.getenv("PMS_OLLAMA_HEALTH_TIMEOUT", "5"))
VLLM_TIMEOUT_SECONDS = float(os.getenv("PMS_VLLM_TIMEOUT", "600"))

LLM_PERF_LOG_PATH = Path(os.getenv("PMS_LLM_PERF_LOG", str(DATA_DIR / "logs" / "llm_performance.log")))

OLLAMA_MAX_CONCURRENT = max(1, int(os.getenv("PMS_OLLAMA_MAX_CONCURRENT", "1")))
