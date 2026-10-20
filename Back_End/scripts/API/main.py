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

# all  — local launcher (python run_app.py): ingest and generation in one process
# api  — daily container: generation, jobs, status. No ingest.
# ingest — quarterly upload container: ingest only.
_APP_ROLE = os.getenv("PMS_APP_ROLE", "all").strip().lower() or "all"
if _APP_ROLE not in {"all", "api", "ingest"}:
    raise RuntimeError(
        f"PMS_APP_ROLE must be all, api, or ingest (got {_APP_ROLE!r})"
    )

_ROLE_DESCRIPTION = {
    "all": (
        "- `/api/ingest` — Upload BSC, JD, LOS, or work-plan files\n"
        "- `/api/generate` — Generate SMART objectives for an employee\n"
        "- `/api/jobs/{job_id}` — Poll a generation job\n"
        "- `/api/reload-index` — Drop the cached retrieval index\n"
        "- `/api/status` — Check document counts and index state\n"
        "- `/api/org` — Division, department, and unit tree\n"
        "- `/api/health` — Liveness probe\n"
    ),
    "api": (
        "- `/api/generate` — Generate SMART objectives for an employee\n"
        "- `/api/jobs/{job_id}` — Poll a generation job\n"
        "- `/api/reload-index` — Drop the cached retrieval index\n"
        "- `/api/status` — Check document counts and index state\n"
        "- `/api/org` — Division, department, and unit tree\n"
        "- `/api/health` — Liveness probe\n"
    ),
    "ingest": (
        "- `/api/ingest` — Upload BSC, JD, LOS, or work-plan files\n"
        "- `/api/org` — Division, department, and unit tree\n"
        "- `/api/health` — Liveness probe\n"
    ),
}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "CBE PMS API",
    description = (
        "**Commercial Bank of Ethiopia — Performance Management System**\n\n"
        f"Role: `{_APP_ROLE}`\n\n"
        + _ROLE_DESCRIPTION[_APP_ROLE]
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import org

app.include_router(org.router, prefix="/api")

if _APP_ROLE in {"all", "ingest"}:
    from .routers import ingest

    app.include_router(ingest.router, prefix="/api")

if _APP_ROLE in {"all", "api"}:
    from .routers import generate, status

    app.include_router(generate.router, prefix="/api")
    app.include_router(status.router, prefix="/api")


if _APP_ROLE == "ingest":
    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok", "role": "ingest"}


@app.get("/", tags=["root"])
def root():
    payload = {
        "message": "CBE PMS API running.",
        "role":    _APP_ROLE,
        "docs":    "http://localhost:8000/docs",
        "health":  "GET  /api/health",
    }
    if _APP_ROLE in {"all", "ingest"}:
        payload["ingest"] = "POST /api/ingest"
    if _APP_ROLE in {"all", "api"}:
        payload["generate"] = "POST /api/generate"
        payload["reload_index"] = "POST /api/reload-index"
        payload["status"] = "GET  /api/status"
    return payload