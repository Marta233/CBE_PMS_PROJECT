"""
process_embeddings.py — retrieval dev script.

Loads from knowledge_base.json (built by POST /api/ingest), runs extraction,
and saves retrieved_context.json for offline LLM testing.

Usage (from Back_End/):
    python scripts/embedding/process_embeddings.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import (  # noqa: E402
    EMBEDDING_MODEL,
    FAISS_INDEX_PATH,
    KNOWLEDGE_BASE_FILE,
    RETRIEVED_CONTEXT_PATH,
)
from embedding.embedder import PMSVectorStore  # noqa: E402
from embedding.extractor import (  # noqa: E402
    QueryExtractor,
    _get_meta,
    _get_text,
    load_knowledge_base,
)
from langchain_core.documents import Document  # noqa: E402

DEFAULT_QUERY = """
Division: Digital Banking
Job Title: Banking Operation Officer
Department: Mobile & Internet Banking
Unit: Mobile Banking Business
Job Grade: 9
"""


def run(query: str = DEFAULT_QUERY, *, bsc_k: int = 10) -> dict:
    if not KNOWLEDGE_BASE_FILE.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KNOWLEDGE_BASE_FILE}")

    print("Starting retrieval pipeline...")
    print(f"   Knowledge base : {KNOWLEDGE_BASE_FILE}")
    print(f"   FAISS index    : {FAISS_INDEX_PATH}")

    print("\nLoading knowledge base...")
    bsc_docs, jd_docs, los_docs = load_knowledge_base(KNOWLEDGE_BASE_FILE)

    bsc_vectorstore = PMSVectorStore(
        embedding_model=EMBEDDING_MODEL,
        index_path=FAISS_INDEX_PATH,
    )
    if FAISS_INDEX_PATH.exists():
        print("\nLoading existing BSC FAISS index...")
        bsc_vectorstore.load_vectorstore()
    else:
        print("\nBuilding BSC FAISS index from knowledge base...")
        lc_bsc = [
            Document(page_content=d.page_content, metadata=d.metadata)
            for d in bsc_docs
        ]
        print(f"   BSC documents: {len(lc_bsc)}")
        bsc_vectorstore.create_vectorstore(lc_bsc)
        bsc_vectorstore.save_vectorstore()
        print("   BSC FAISS index saved")

    extractor = QueryExtractor(
        los_docs=los_docs,
        jd_docs=jd_docs,
        bsc_vectorstore=bsc_vectorstore,
    )

    print(f"\nQuery:\n{query}")
    result = extractor.extract(query, bsc_k=bsc_k)
    print(result.summary)

    if result.jd_doc:
        print("\nJD Document:")
        print(_get_text(result.jd_doc)[:500])
    else:
        print("\nJD Document: not found")

    print(f"\nBSC Documents (top-{bsc_k}):")
    for i, (doc, score) in enumerate(zip(result.bsc_docs, result.bsc_scores), 1):
        print(f"\n  [{i}] Score: {score:.4f}")
        print(f"       Meta : {_get_meta(doc)}")
        print(f"       Text : {_get_text(doc)[:120]}")

    print(f"\nLOS Documents ({len(result.los_docs)}):")
    for i, doc in enumerate(result.los_docs, 1):
        print(f"\n  [{i}] Meta : {_get_meta(doc)}")
        print(f"       Text : {_get_text(doc)[:120]}")

    jd_context = _get_text(result.jd_doc) if result.jd_doc else ""
    bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
    los_context = "\n\n".join(_get_text(d) for d in result.los_docs)

    print("\nContexts ready:")
    print(f"   JD  : {len(jd_context)} chars")
    print(f"   BSC : {len(bsc_context)} chars  ({len(result.bsc_docs)} docs)")
    print(f"   LOS : {len(los_context)} chars  ({len(result.los_docs)} docs)")

    context = {
        "query": query.strip(),
        "jd_context": jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
    }
    RETRIEVED_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RETRIEVED_CONTEXT_PATH.write_text(
        json.dumps(context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nContext saved -> {RETRIEVED_CONTEXT_PATH}")
    return context


if __name__ == "__main__":
    run()
