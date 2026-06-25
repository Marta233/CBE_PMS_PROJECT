# scripts/api/routers/index.py
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..config import KNOWLEDGE_BASE_FILE, FAISS_INDEX_PATH, EMBEDDING_MODEL
from embedding.embedder import PMSVectorStore
from langchain_core.documents import Document
import shutil, json

logger = logging.getLogger(__name__)
router = APIRouter()

class RebuildResult(BaseModel):
    message: str
    vectors: int

@router.post("/rebuild-index", response_model=RebuildResult)
def rebuild_index():
    if not KNOWLEDGE_BASE_FILE.exists():
        raise HTTPException(404, detail="Knowledge base not found.")
    with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
        kb = json.load(f)
    bsc_docs = [doc for doc in kb if doc.get("metadata", {}).get("source") == "BSC"]
    if not bsc_docs:
        return RebuildResult(message="No BSC documents found.", vectors=0)
    lc = [Document(page_content=d["text"], metadata=d.get("metadata", {})) for d in bsc_docs]
    if FAISS_INDEX_PATH.exists():
        shutil.rmtree(FAISS_INDEX_PATH, ignore_errors=True)
    store = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=FAISS_INDEX_PATH)
    store.create_vectorstore(lc)
    store.save_vectorstore()
    return RebuildResult(message=f"FAISS rebuilt with {len(lc)} BSC documents.", vectors=len(lc))