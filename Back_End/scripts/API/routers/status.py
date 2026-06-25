"""
Back_End/scripts/API/routers/status.py

GET /api/health  — quick liveness check
GET /api/status  — document counts + index info
"""
import json
from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import DOC_FILES, FAISS_INDEX_PATH, KNOWLEDGE_BASE_FILE

router = APIRouter()


class StatusResult(BaseModel):
    status:              str
    knowledge_base_docs: int
    document_counts:     Dict[str, int]
    index_exists:        bool


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@router.get("/status", response_model=StatusResult, tags=["health"])
def get_status():
    # ── Knowledge base total ──────────────────────────────────────────────────
    kb_total = 0
    if KNOWLEDGE_BASE_FILE.exists():
        try:
            kb_total = len(json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8")))
        except Exception:
            kb_total = -1

    # ── Per-type counts (from knowledge base, grouped by source metadata) ─────
    counts: Dict[str, int] = {t: 0 for t in DOC_FILES}
    if KNOWLEDGE_BASE_FILE.exists():
        try:
            all_docs = json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8"))
            for doc in all_docs:
                src = doc.get("metadata", {}).get("source", "")
                if src in counts:
                    counts[src] += 1
        except Exception:
            pass

    return StatusResult(
        status              = "ok",
        knowledge_base_docs = kb_total,
        document_counts     = counts,
        index_exists        = FAISS_INDEX_PATH.exists(),
    )