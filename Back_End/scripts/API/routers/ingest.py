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
import shutil
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

DocType = Literal["BSC", "JD", "LOS", "WP"]

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
    if doc_type == "WP":
        from WP import run    # type: ignore  (Data_Ingestion/WP/__init__.py — same pattern as los/__init__.py)
        return run(file_path)
    raise ValueError(f"Unknown doc_type: {doc_type}")


def _replace_index(staging: Path, live: Path) -> None:
    """Swap a finished staging index into place. The live index is removed only after the swap."""
    backup = live.with_name(live.name + ".bak")
    if backup.exists():
        shutil.rmtree(backup)
    if live.exists():
        live.rename(backup)
    try:
        staging.rename(live)
    except Exception:
        if backup.exists() and not live.exists():
            backup.rename(live)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


# ── BSC FAISS rebuild ─────────────────────────────────────────────────────────
def _rebuild_bsc_faiss(merged_kb: list) -> tuple[bool, str]:
    """
    Rebuild the BSC FAISS index in a staging directory and swap it in only
    after save succeeds. A failed rebuild leaves the live index untouched.
    Returns (success: bool, message: str).
    """
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

    staging = FAISS_INDEX_PATH.with_name(FAISS_INDEX_PATH.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    store = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=staging)
    try:
        store.create_vectorstore(bsc_lc)
        store.save_vectorstore()
        n = store.vectorstore.index.ntotal
        del store
        gc.collect()
        _replace_index(staging, FAISS_INDEX_PATH)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

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


def dedup_key(doc: dict) -> tuple:
    """Identity used when a re-upload replaces older knowledge-base chunks.

    BSC, JD, and LOS replace by (source, division).
    Work plans replace by (source, department, fiscal year, unit).
    """
    meta = doc.get("metadata", {})
    source = meta.get("source")
    if source == "WorkPlan":
        return (source, meta.get("department"), meta.get("fiscal_year"), meta.get("unit"))
    return (source, meta.get("division"))


def merge_knowledge_base(existing: list, new_docs: list) -> tuple[list, int]:
    """Drop chunks the upload replaces, then append the new documents.

    A work plan stored with a blank department can never match a query, and its
    key differs from the corrected plan. Re-uploading the same fiscal year and
    unit replaces that stale chunk too.
    """
    new_keys = {dedup_key(doc) for doc in new_docs if isinstance(doc, dict)}
    new_wp_slots = {
        (doc["metadata"].get("fiscal_year"), doc["metadata"].get("unit"))
        for doc in new_docs
        if isinstance(doc, dict) and doc.get("metadata", {}).get("source") == "WorkPlan"
    }

    def _is_stale_blank_wp(doc: dict) -> bool:
        meta = doc.get("metadata", {})
        return (
            meta.get("source") == "WorkPlan"
            and not str(meta.get("department") or "").strip()
            and (meta.get("fiscal_year"), meta.get("unit")) in new_wp_slots
        )

    filtered = [
        doc for doc in existing
        if dedup_key(doc) not in new_keys and not _is_stale_blank_wp(doc)
    ]
    removed = len(existing) - len(filtered)
    return filtered + new_docs, removed


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
    # If the file exists but can't be read, STOP. Falling back to an empty list
    # would make step 6 overwrite the whole knowledge base with only this upload.
    existing: list = []
    if KNOWLEDGE_BASE_FILE.exists() and KNOWLEDGE_BASE_FILE.stat().st_size > 0:
        try:
            existing = json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                raise ValueError("top-level JSON is not a list")
        except Exception as exc:
            logger.error(f"Knowledge base unreadable: {exc}", exc_info=True)
            raise HTTPException(
                500,
                detail=f"knowledge_base.json exists but could not be read ({exc}). "
                       f"Refusing to overwrite it. Fix or restore the file, then retry.",
            )

    # ── 5–6. Replace matching chunks, then append this upload ────────────────
    merged, removed = merge_knowledge_base(existing, new_docs)
    if removed:
        replaced = {dedup_key(doc) for doc in new_docs if isinstance(doc, dict)}
        logger.info(f"♻️  Removed {removed} old chunks for keys: {replaced}")
    try:
        tmp_path = KNOWLEDGE_BASE_FILE.with_suffix(".json.tmp")
        tmp_path.write_text(_safe_dumps(merged), encoding="utf-8")          # write fully first
        if KNOWLEDGE_BASE_FILE.exists():
            shutil.copy2(KNOWLEDGE_BASE_FILE, KNOWLEDGE_BASE_FILE.with_suffix(".json.bak"))
        tmp_path.replace(KNOWLEDGE_BASE_FILE)                                # then swap in
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