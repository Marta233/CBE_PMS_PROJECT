"""api/routers/index.py — POST /api/rebuild-index"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from ..core.config import DOC_FILES, FAISS_INDEX_PATH, FAISS_META_PATH
from ..core.indexer import build_index

logger = logging.getLogger(__name__)
router = APIRouter()

class RebuildResult(BaseModel):
    message: str
    vectors: int

@router.post("/rebuild-index", response_model=RebuildResult, tags=["index"])
def rebuild_index():
    """Rebuild FAISS vector index from all ingested documents."""
    total, message = build_index(DOC_FILES, FAISS_INDEX_PATH, FAISS_META_PATH)
    return RebuildResult(message=message, vectors=total)
