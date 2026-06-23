"""
api/routers/ingest.py
POST /api/ingest — receives a file + doc_type, calls the matching pipeline,
appends documents to the JSON store, returns chunk count.

BSC: embeds into FAISS via PMSVectorStore only when no index exists yet.
     If the index is already on disk, embedding is skipped entirely.
"""
import json
import logging
import math
import sys
import gc
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..core.config import ACCEPTED_TYPES, DOC_FILES, UPLOAD_DIR

logger = logging.getLogger(__name__)
router = APIRouter()
DocType = Literal["BSC", "JD", "LOS"]

# ── Resolve pipeline root ─────────────────────────────────────────────────────
_SCRIPTS_ROOT = Path(__file__).resolve().parents[3]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

PROJECT_ROOT  = Path(__file__).resolve().parents[5]
DATA_ROOT     = PROJECT_ROOT / "Back_End" / "Data"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

DOCUMENTS_DIR = DATA_ROOT / "documents"
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

KNOWLEDGE_BASE_FILE = (
    Path(__file__).resolve().parents[4]
    / "Data" / "documents" / "knowledge_base.json"
)
KNOWLEDGE_BASE_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── BSC vectorstore path ──────────────────────────────────────────────────────
_FAISS_INDEX_PATH = DATA_ROOT / "vectorstore" / "bsc_faiss_index"
_EMBEDDING_MODEL  = "BAAI/bge-small-en-v1.5"


# ── JSON encoder that handles pandas/numpy types ──────────────────────────────
class _SafeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        try:
            import numpy as np
            if isinstance(obj, np.integer):   return int(obj)
            if isinstance(obj, np.floating):  return None if math.isnan(float(obj)) else float(obj)
            if isinstance(obj, np.ndarray):   return obj.tolist()
        except ImportError:
            pass
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp): return obj.isoformat()
        except ImportError:
            pass
        return str(obj)

    def iterencode(self, obj: Any, _one_shot: bool = False):
        obj = _sanitise(obj)
        return super().iterencode(obj, _one_shot)


def _sanitise(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):  return {k: _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [_sanitise(v) for v in obj]
    return obj


def _safe_dumps(data: Any) -> str:
    return json.dumps(data, cls=_SafeEncoder, indent=2, ensure_ascii=False)


# ── Pipeline dispatch ─────────────────────────────────────────────────────────
def _run_pipeline(doc_type: str, file_path: Path) -> list:
    if doc_type == "BSC":
        from bsc import run   # type: ignore
        return run(file_path)
    elif doc_type == "JD":
        from jd import run    # type: ignore
        return run(file_path)
    elif doc_type == "LOS":
        from los import run   # type: ignore
        return run(file_path)
    raise ValueError(f"Unknown doc_type: {doc_type}")


# ── BSC embedding ─────────────────────────────────────────────────────────────
def _to_lc_docs(raw_docs: list):
    from langchain_core.documents import Document
    return [
        Document(page_content=d["text"], metadata=d.get("metadata", {}))
        for d in raw_docs if isinstance(d, dict)
    ]


def _embed_bsc_if_needed(new_docs: list, existing_docs: list) -> tuple[bool, str]:
    """
    Embed BSC documents into FAISS — but ONLY if the index does not exist yet.

    Returns (was_embedded: bool, message: str)
    """
    # ── GUARD: index already on disk → skip entirely ──────────────────────────
    if _FAISS_INDEX_PATH.exists():
        logger.info(f"⏭️  BSC FAISS index already exists at {_FAISS_INDEX_PATH} — skipping embedding.")
        return False, "FAISS index already exists — skipped"

    # ── Fresh build ───────────────────────────────────────────────────────────
    try:
        from embedding.embedder import PMSVectorStore  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Cannot find PMSVectorStore. Make sure the 'embedding' package is on sys.path."
        ) from exc

    all_lc = _to_lc_docs(existing_docs + new_docs)
    if not all_lc:
        logger.warning("⚠️  No documents to embed — skipping FAISS creation.")
        return False, "No documents to embed"

    logger.info(f"🧠 Building BSC FAISS index from {len(all_lc)} documents…")
    _FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    store = PMSVectorStore(embedding_model=_EMBEDDING_MODEL, index_path=_FAISS_INDEX_PATH)
    store.create_vectorstore(all_lc)
    store.save_vectorstore()

    logger.info(f"✅ BSC FAISS index created → {_FAISS_INDEX_PATH}")
    return True, f"FAISS index built from {len(all_lc)} documents"


# ── Response model ────────────────────────────────────────────────────────────
class IngestResult(BaseModel):
    filename:            str
    doc_type:            str
    chunks:              int
    status:              str
    detail:              str  = ""
    vectorstore_updated: bool = False


_EXT_TO_MIME = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls":  "application/vnd.ms-excel",
    ".csv":  "text/csv",
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    ".txt":  "text/plain",
}


@router.post("/ingest", response_model=IngestResult, tags=["ingestion"])
async def ingest_file(
    file:     UploadFile = File(...),
    doc_type: DocType    = Form(...),
):
    # ── Validate extension ────────────────────────────────────────────────────
    suffix         = Path(file.filename or "").suffix.lower()
    effective_mime = _EXT_TO_MIME.get(suffix, file.content_type or "")
    if effective_mime not in ACCEPTED_TYPES[doc_type]:
        allowed = [e for e, m in _EXT_TO_MIME.items() if m in ACCEPTED_TYPES[doc_type]]
        raise HTTPException(415, detail=f"'{suffix}' not accepted for {doc_type}. Use: {', '.join(allowed)}")

    # ── Save temp file ────────────────────────────────────────────────────────
    temp_path = UPLOAD_DIR / f"{doc_type}_{uuid.uuid4().hex}{suffix}"
    try:
        temp_path.write_bytes(await file.read())
    except Exception as exc:
        raise HTTPException(500, detail=f"Could not save upload: {exc}")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        new_docs = _run_pipeline(doc_type, temp_path)
    except Exception as exc:
        logger.error(f"Pipeline error [{doc_type}]: {exc}", exc_info=True)
        raise HTTPException(422, detail=f"Pipeline failed: {exc}")
    finally:
        try:
            gc.collect()
            time.sleep(0.5)
            temp_path.unlink(missing_ok=True)
        except PermissionError as e:
            logger.warning(f"Could not delete temp file {temp_path}: {e}")

    if not new_docs:
        raise HTTPException(422, detail="Pipeline produced 0 documents. Check file format.")

    # ── Load existing knowledge base ──────────────────────────────────────────
    existing: list = []

    if KNOWLEDGE_BASE_FILE.exists():
        try:
            existing = json.loads(
                KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning(
                f"Could not read existing knowledge base: {exc}"
            )
            existing = []

    # ── Determine uploaded sources ────────────────────────────────────────────
    # ── Build unique document keys ─────────────────────────────────────────────
    new_doc_keys = {
        (
            doc.get("metadata", {}).get("source"),
            doc.get("metadata", {}).get("division"),
        )
        for doc in new_docs
        if isinstance(doc, dict)
    }

    logger.info(f"Incoming document keys: {new_doc_keys}")

    new_sources = {key[0] for key in new_doc_keys}

    # ── Remove old docs with same source ──────────────────────────────────────
    filtered_existing = [
    doc
    for doc in existing
    if (
        doc.get("metadata", {}).get("source"),
        doc.get("metadata", {}).get("division"),
    ) not in new_doc_keys
]

    removed_count = len(existing) - len(filtered_existing)

    if removed_count:
        logger.info(
            f"♻️ Removed {removed_count} existing chunks "
            f"for sources: {list(new_sources)}"
        )

    # ── Merge updated KB ──────────────────────────────────────────────────────
    merged = filtered_existing + new_docs

    # ── Save knowledge base ───────────────────────────────────────────────────
    try:
        KNOWLEDGE_BASE_FILE.write_text(
            _safe_dumps(merged),
            encoding="utf-8"
        )
    except Exception as exc:
        logger.error(
            f"JSON serialisation failed: {exc}",
            exc_info=True
        )
        raise HTTPException(
            500,
            detail=f"Could not serialise documents: {exc}"
        )

    logger.info(
        f"✅ Knowledge base updated: "
        f"removed={removed_count}, "
        f"added={len(new_docs)}, "
        f"total={len(merged)}"
    )

    # ── BSC only: embed into FAISS if index not yet built ────────────────────
    vectorstore_updated = False
    embed_note = ""

    if doc_type == "BSC":
        try:
            import shutil
            from embedding.embedder import PMSVectorStore
            from langchain_core.documents import Document

            logger.info("🧠 Rebuilding BSC vector store...")

            # Remove old index completely
            if _FAISS_INDEX_PATH.exists():
                logger.info(f"🗑 Removing existing index: {_FAISS_INDEX_PATH}")
                shutil.rmtree(_FAISS_INDEX_PATH, ignore_errors=True)

            # Only BSC documents go into FAISS
            bsc_docs = [
                Document(
                    page_content=doc["text"],
                    metadata=doc.get("metadata", {})
                )
                for doc in merged
                if (
                    isinstance(doc, dict)
                    and doc.get("metadata", {}).get("source") == "BSC"
                )
            ]

            logger.info(
                f"📄 Found {len(bsc_docs)} BSC documents for embedding"
            )

            if bsc_docs:
                store = PMSVectorStore(
                    embedding_model=_EMBEDDING_MODEL,
                    index_path=_FAISS_INDEX_PATH
                )

                store.create_vectorstore(bsc_docs)
                store.save_vectorstore()

                vectorstore_updated = True
                embed_note = (
                    f"FAISS rebuilt successfully with "
                    f"{len(bsc_docs)} BSC chunks"
                )
                # BSC chunks from knowledge base
                bsc_chunk_count = len(bsc_docs)

                # FAISS stored documents
                faiss_chunk_count = store.vectorstore.index.ntotal
                logger.info(
                f"Knowledge Base BSC Chunks: {bsc_chunk_count}, "
                f"FAISS Chunks: {faiss_chunk_count}"
)
                logger.info(embed_note)
            else:
                embed_note = "No BSC documents found for embedding"

        except Exception as exc:
            logger.error(
                f"⚠️ BSC embedding failed: {exc}",
                exc_info=True
            )
            embed_note = f"embedding failed: {exc}"
    # ── Build detail string ───────────────────────────────────────────────────
    detail = (
    f"Removed {removed_count} old chunks, "
    f"added {len(new_docs)} new chunks "
    f"({len(merged)} total for {doc_type})"
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