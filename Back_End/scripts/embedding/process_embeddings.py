"""
process_embeddings.py  —  Enhanced retrieval entry point

Key change vs original
----------------------
Data comes from knowledge_base.json (already ingested via the API).
No pipelines are re-run. This makes startup ~10x faster.

Usage
-----
    cd data_ingestion
    python -m embedding.process_embeddings
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from .embedder   import PMSVectorStore
from .extractor  import (
    QueryExtractor, ExtractionResult,
    load_knowledge_base,
    _get_text, _get_meta,
)
from langchain_core.documents import Document

# =========================================================
# PATHS  — adjust to match your project layout
# =========================================================
PROJECT_ROOT       = Path(__file__).resolve().parents[3]
KNOWLEDGE_BASE_FILE = PROJECT_ROOT / "Back_End" / "Data" / "documents" / "knowledge_base.json"
FAISS_INDEX_PATH   = PROJECT_ROOT / "Back_End" / "Data" / "vectorstore" / "bsc_faiss_index"
EMBEDDING_MODEL    = "BAAI/bge-small-en-v1.5"

print("🚀 Starting retrieval pipeline...")
print(f"   Knowledge base : {KNOWLEDGE_BASE_FILE}")
print(f"   FAISS index    : {FAISS_INDEX_PATH}")

# =========================================================
# STEP 1: LOAD FROM KNOWLEDGE BASE (no pipeline re-run)
# =========================================================
print("\n📂 Loading knowledge base...")
bsc_docs, jd_docs, los_docs = load_knowledge_base(KNOWLEDGE_BASE_FILE)

# =========================================================
# STEP 2: BSC VECTORSTORE
# =========================================================
bsc_vectorstore = PMSVectorStore(
    embedding_model=EMBEDDING_MODEL,
    index_path=FAISS_INDEX_PATH,
)

if FAISS_INDEX_PATH.exists():
    print("\n📂 Loading existing BSC FAISS index...")
    bsc_vectorstore.load_vectorstore()
else:
    print("\n🧠 Building BSC FAISS index from knowledge base...")
    lc_bsc = [
        Document(page_content=d.page_content, metadata=d.metadata)
        for d in bsc_docs
    ]
    print(f"   BSC documents: {len(lc_bsc)}")
    bsc_vectorstore.create_vectorstore(lc_bsc)
    bsc_vectorstore.save_vectorstore()
    print("   ✅ BSC FAISS index saved")

# =========================================================
# STEP 3: INIT EXTRACTOR
# =========================================================
extractor = QueryExtractor(
    los_docs       = los_docs,
    jd_docs        = jd_docs,
    bsc_vectorstore= bsc_vectorstore,
)

# =========================================================
# STEP 4: RUN EXTRACTION
# =========================================================
BSC_K = 10

query = """
Division: Digital Banking
Job Title: Banking Operation Officer
Department:Mobile &Internet Banking
Unit:Mobile Banking Business
Job Grade: 9
"""

print(f"\n🔍 Query:\n{query}")
result = extractor.extract(query, bsc_k=BSC_K)
print(result.summary)

# =========================================================
# STEP 5: INSPECT RESULTS
# =========================================================
if result.jd_doc:
    print("\n📄 JD Document:")
    print(_get_text(result.jd_doc)[:500])
else:
    print("\n📄 JD Document: not found")

print(f"\n📦 BSC Documents (top-{BSC_K}):")
for i, (doc, score) in enumerate(zip(result.bsc_docs, result.bsc_scores), 1):
    print(f"\n  [{i}] Score: {score:.4f}")
    print(f"       Meta : {_get_meta(doc)}")
    print(f"       Text : {_get_text(doc)[:120]}")

print(f"\n📦 LOS Documents ({len(result.los_docs)}):")
for i, doc in enumerate(result.los_docs, 1):
    print(f"\n  [{i}] Meta : {_get_meta(doc)}")
    print(f"       Text : {_get_text(doc)[:120]}")

# =========================================================
# STEP 6: BUILD CONTEXTS
# =========================================================
jd_context  = _get_text(result.jd_doc) if result.jd_doc else ""
bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
los_context = "\n\n".join(_get_text(d) for d in result.los_docs)

print("\n✅ Contexts ready:")
print(f"   JD  : {len(jd_context)} chars")
print(f"   BSC : {len(bsc_context)} chars  ({len(result.bsc_docs)} docs)")
print(f"   LOS : {len(los_context)} chars  ({len(result.los_docs)} docs)")

# =========================================================
# STEP 7: SAVE RETRIEVED CONTEXT
# =========================================================
save_path = KNOWLEDGE_BASE_FILE.parent / "retrieved_context.json"
save_path.write_text(
    json.dumps({
        "query":       query,
        "jd_context":  jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
    }, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"\n✅ Context saved → {save_path}")
