"""api/routers/status.py — GET /api/status"""
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict
from ..core.config import DOC_FILES, FAISS_INDEX_PATH

router = APIRouter()

class StatusResult(BaseModel):
    status:           str
    document_counts:  Dict[str, int]
    index_exists:     bool
    total_documents:  int

@router.get("/status", response_model=StatusResult, tags=["health"])
def get_status():
    counts: Dict[str, int] = {}
    for doc_type, path in DOC_FILES.items():
        if path.exists():
            try:
                counts[doc_type] = len(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                counts[doc_type] = -1
        else:
            counts[doc_type] = 0

    return StatusResult(
        status          = "ok",
        document_counts = counts,
        index_exists    = FAISS_INDEX_PATH.exists(),
        total_documents = sum(v for v in counts.values() if v > 0),
    )
