"""
process_embeddings.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from .config import (
    BSC_DOCUMENTS,
    LOS_DOCUMENTS,
    JD_DOCUMENTS,
    FAISS_INDEX_PATH,
    EMBEDDING_MODEL,
)

from .embedder import PMSVectorStore
from .extractor import QueryExtractor, _get_meta, _get_text
from langchain_core.documents import Document

print("🚀 Starting pipeline...")

# =========================================================
# BUILD BSC-ONLY FAISS VECTORSTORE
# =========================================================



bsc_vectorstore = PMSVectorStore(
    embedding_model=EMBEDDING_MODEL,
    index_path=FAISS_INDEX_PATH,
)

if FAISS_INDEX_PATH.exists():
    print("\n📂 Loading existing BSC FAISS index...")
    bsc_vectorstore.load_vectorstore()
else:
    print("\n🧠 Building BSC FAISS index...")
    bsc_lc_docs = []
    for doc in BSC_DOCUMENTS:
        if isinstance(doc, dict):
            bsc_lc_docs.append(
                Document(page_content=doc["text"], metadata=doc.get("metadata", {}))
            )
        else:
            bsc_lc_docs.append(doc)
    print(f"   BSC documents: {len(bsc_lc_docs)}")
    bsc_vectorstore.create_vectorstore(bsc_lc_docs)
    bsc_vectorstore.save_vectorstore()
    print("   ✅ BSC FAISS index saved")

# =========================================================
# INIT EXTRACTOR
# =========================================================

extractor = QueryExtractor(
    los_docs=list(LOS_DOCUMENTS),
    jd_docs=list(JD_DOCUMENTS),
    bsc_vectorstore=bsc_vectorstore,
)

# =========================================================
# RUN EXTRACTION
# =========================================================

query = """
Division: Digital Banking
Job Title:Digital Banking Officer
Department:Mobile Money
Unit:Mobile Money Business
Job Grade:13
"""

BSC_K = 5

print(f"\n🔍 Query:\n{query}")

result = extractor.extract(query, bsc_k=BSC_K)
print(result.summary)
# =========================================================
# INSPECT RESULTS
# =========================================================

if result.jd_doc:
    print("\n📄 JD Document:")
    print(_get_text(result.jd_doc))
else:
    print("\n📄 JD Document: not found")

print(f"\n📦 BSC Documents (top-{BSC_K} — query: unit + job title):")
for i, doc in enumerate(result.bsc_docs, 1):
    print(f"\n  [{i}] {_get_meta(doc)}")
    print(f"       {_get_text(doc)}")

print(f"\n📦 LOS Documents ({len(result.los_docs)}):")
for i, doc in enumerate(result.los_docs, 1):
    print(f"\n  [{i}] {_get_meta(doc)}")
    print(f"       {_get_text(doc)}")

# =========================================================
# SEPARATE CONTEXTS
# =========================================================

jd_context  = _get_text(result.jd_doc) if result.jd_doc else ""
bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
los_context = "\n\n".join(_get_text(d) for d in result.los_docs)

print("\n✅ Contexts ready:")
print(f"   JD  context : {len(jd_context)} characters")
print(f"   BSC context : {len(bsc_context)} characters  ({len(result.bsc_docs)} docs)")
print(f"   LOS context : {len(los_context)} characters  ({len(result.los_docs)} docs)")


import json
from pathlib import Path

# After your existing context extraction at the bottom of process_embeddings.py
retrieved_context = {
    "query": query,
    "jd_context": jd_context,
    "bsc_context": bsc_context,
    "los_context": los_context,
}

save_path = Path(__file__).resolve().parent.parent.parent / "Data" / "processed" / "retrieved_context.json"
save_path.parent.mkdir(parents=True, exist_ok=True)

with open(save_path, "w", encoding="utf-8") as f:
    json.dump(retrieved_context, f, ensure_ascii=False, indent=2)

print(f"\n✅ Context saved to: {save_path}")