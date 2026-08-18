"""
Back_End/scripts/API/routers/ingest.py

POST /api/ingest — receives a file + doc_type, runs the matching pipeline,
merges documents into the shared knowledge_base.json, and rebuilds the
BSC FAISS index on every BSC upload.
"""
import gc
import json
import logging
import math
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import (
    ACCEPTED_TYPES,
    EMBEDDING_MODEL,
    FAISS_INDEX_PATH,
    KNOWLEDGE_BASE_FILE,
    UPLOAD_DIR,
)

logger = logging.getLogger("pms.ingest")
router = APIRouter()

DocType = Literal["BSC", "JD", "LOS"]

# ── Extension → MIME mapping ──────────────────────────────────────────────────
_EXT_TO_MIME = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls":  "application/vnd.ms-excel",
    ".csv":  "text/csv",
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    ".txt":  "text/plain",
}


# ── JSON encoder that handles pandas / numpy types ────────────────────────────
class _SafeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        try:
            import numpy as np
            if isinstance(obj, np.integer):  return int(obj)
            if isinstance(obj, np.floating): return None if math.isnan(float(obj)) else float(obj)
            if isinstance(obj, np.ndarray):  return obj.tolist()
        except ImportError:
            pass
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp): return obj.isoformat()
        except ImportError:
            pass
        return str(obj)

    def iterencode(self, obj: Any, _one_shot: bool = False):
        return super().iterencode(_sanitise(obj), _one_shot)


def _sanitise(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict): return {k: _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_sanitise(v) for v in obj]
    return obj


def _safe_dumps(data: Any) -> str:
    return json.dumps(data, cls=_SafeEncoder, indent=2, ensure_ascii=False)


# ── Pipeline dispatch ─────────────────────────────────────────────────────────
def _run_pipeline(doc_type: str, file_path: Path) -> list:
    if doc_type == "BSC":
        from bsc import run   # type: ignore
        return run(file_path)
    if doc_type == "JD":
        from jd import run    # type: ignore
        return run(file_path)
    if doc_type == "LOS":
        from los import run   # type: ignore
        return run(file_path)
    raise ValueError(f"Unknown doc_type: {doc_type}")


# ── BSC FAISS rebuild ─────────────────────────────────────────────────────────
def _rebuild_bsc_faiss(merged_kb: list) -> tuple[bool, str]:
    """
    Delete existing BSC FAISS index and rebuild it from all BSC docs
    currently in the knowledge base.
    Returns (success: bool, message: str).
    """
    import shutil
    try:
        from langchain_core.documents import Document
        from embedding.embedder import PMSVectorStore  # type: ignore
    except ImportError as exc:
        return False, f"Import error: {exc}"

    bsc_lc = [
        Document(page_content=doc["text"], metadata=doc.get("metadata", {}))
        for doc in merged_kb
        if isinstance(doc, dict) and doc.get("metadata", {}).get("source") == "BSC"
    ]

    if not bsc_lc:
        return False, "No BSC documents found in knowledge base — FAISS not built"

    if FAISS_INDEX_PATH.exists():
        shutil.rmtree(FAISS_INDEX_PATH, ignore_errors=True)
        logger.info(f"🗑  Removed old FAISS index at {FAISS_INDEX_PATH}")

    FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=FAISS_INDEX_PATH)
    store.create_vectorstore(bsc_lc)
    store.save_vectorstore()

    n = store.vectorstore.index.ntotal
    msg = f"FAISS rebuilt with {n} BSC vectors from {len(bsc_lc)} chunks"
    logger.info(f"✅ {msg}")
    return True, msg


# ── Response model ────────────────────────────────────────────────────────────
class IngestResult(BaseModel):
    filename:            str
    doc_type:            str
    chunks:              int
    status:              str
    detail:              str  = ""
    vectorstore_updated: bool = False


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/ingest", response_model=IngestResult, tags=["ingestion"])
async def ingest_file(
    file:     UploadFile = File(...),
    doc_type: DocType    = Form(...),
):
    # ── 1. Validate extension ─────────────────────────────────────────────────
    suffix         = Path(file.filename or "").suffix.lower()
    effective_mime = _EXT_TO_MIME.get(suffix, file.content_type or "")
    if effective_mime not in ACCEPTED_TYPES[doc_type]:
        allowed = [e for e, m in _EXT_TO_MIME.items() if m in ACCEPTED_TYPES[doc_type]]
        raise HTTPException(
            415,
            detail=f"'{suffix}' not accepted for {doc_type}. Use: {', '.join(allowed)}",
        )

    # ── 2. Save temp file ─────────────────────────────────────────────────────
    temp_path = UPLOAD_DIR / f"{doc_type}_{uuid.uuid4().hex}{suffix}"
    try:
        temp_path.write_bytes(await file.read())
    except Exception as exc:
        raise HTTPException(500, detail=f"Could not save upload: {exc}")

    # ── 3. Run pipeline ───────────────────────────────────────────────────────
    try:
        new_docs = _run_pipeline(doc_type, temp_path)
    except Exception as exc:
        logger.error(f"Pipeline error [{doc_type}]: {exc}", exc_info=True)
        raise HTTPException(422, detail=f"Pipeline failed: {exc}")
    finally:
        try:
            gc.collect()
            time.sleep(0.3)
            temp_path.unlink(missing_ok=True)
        except PermissionError as e:
            logger.warning(f"Could not delete temp file {temp_path}: {e}")

    if not new_docs:
        raise HTTPException(422, detail="Pipeline produced 0 documents. Check file format.")

    # ── 4. Load existing knowledge base ───────────────────────────────────────
    existing: list = []
    if KNOWLEDGE_BASE_FILE.exists():
        try:
            existing = json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Could not read existing knowledge base: {exc}")

    # ── 5. Deduplicate: remove old chunks for the same (source, division) keys ─
    new_keys = {
        (doc.get("metadata", {}).get("source"), doc.get("metadata", {}).get("division"))
        for doc in new_docs
        if isinstance(doc, dict)
    }
    filtered = [
        doc for doc in existing
        if (
            doc.get("metadata", {}).get("source"),
            doc.get("metadata", {}).get("division"),
        ) not in new_keys
    ]
    removed = len(existing) - len(filtered)
    if removed:
        logger.info(f"♻️  Removed {removed} old chunks for keys: {new_keys}")

    # ── 6. Merge and save knowledge base ──────────────────────────────────────
    merged = filtered + new_docs
    try:
        KNOWLEDGE_BASE_FILE.write_text(_safe_dumps(merged), encoding="utf-8")
    except Exception as exc:
        logger.error(f"JSON serialisation failed: {exc}", exc_info=True)
        raise HTTPException(500, detail=f"Could not serialise documents: {exc}")

    logger.info(
        f"✅ Knowledge base updated — removed={removed}, "
        f"added={len(new_docs)}, total={len(merged)}"
    )

    # ── 7. BSC only: rebuild FAISS index ─────────────────────────────────────
    vectorstore_updated = False
    embed_note = ""
    if doc_type == "BSC":
        try:
            vectorstore_updated, embed_note = _rebuild_bsc_faiss(merged)
        except Exception as exc:
            logger.error(f"⚠️  BSC FAISS rebuild failed: {exc}", exc_info=True)
            embed_note = f"FAISS rebuild failed: {exc}"

    # ── 8. Return result ──────────────────────────────────────────────────────
    detail = (
        f"Removed {removed} old chunks, added {len(new_docs)} new chunks "
        f"({len(merged)} total in knowledge base)"
    )
    if embed_note:
        detail += f" | {embed_note}"

    return IngestResult(
        filename            = file.filename or temp_path.name,
        doc_type            = doc_type,
        chunks              = len(new_docs),
        status              = "success",
        detail              = detail,
        vectorstore_updated = vectorstore_updated,
    )