"""
Back_End/scripts/API/main.py
CBE PMS — Unified API (Ingestion + Generation)

Run from Back_End/ directory:
    python -m uvicorn scripts.API.main:app --host 0.0.0.0 --port 8000 --reload

Swagger UI:  http://localhost:8000/docs
"""

# ── Fix sys.path FIRST — before any other imports ────────────────────────────
import sys
from pathlib import Path

_HERE        = Path(__file__).resolve().parent   # Back_End/scripts/API/
_SCRIPTS_DIR = _HERE.parent                      # Back_End/scripts/
_BACK_END    = _SCRIPTS_DIR.parent               # Back_End/
_DATA_ING    = _SCRIPTS_DIR / "Data_Ingestion"   # Back_End/scripts/Data_Ingestion/

# Insert in reverse so _SCRIPTS_DIR ends up first (avoids data_ingestion/config shadowing scripts/config).
for _p in (str(_DATA_ING), str(_BACK_END), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Now safe to import everything else ───────────────────────────────────────
import logging
import os
import warnings

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("faiss").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_VERBOSITY"]       = "error"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pms")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ingest, generate, status

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "CBE PMS API",
    description = (
        "**Commercial Bank of Ethiopia — Performance Management System**\n\n"
        "- `/api/ingest` — Upload BSC, JD, or LOS files to build the knowledge base\n"
        "- `/api/generate` — Generate SMART objectives for an employee\n"
        "- `/api/status` — Check document counts and index state\n"
        "- `/api/health` — Liveness probe\n"
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router,   prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(status.router,   prefix="/api")


@app.get("/", tags=["root"])
def root():
    return {
        "message":  "CBE PMS API running.",
        "docs":     "http://localhost:8000/docs",
        "ingest":   "POST /api/ingest",
        "generate": "POST /api/generate",
        "status":   "GET  /api/status",
        "health":   "GET  /api/health",
    }