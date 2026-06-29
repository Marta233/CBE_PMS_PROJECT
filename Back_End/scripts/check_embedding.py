"""Quick check: build FAISS index if missing, then run a smoke-test search."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import EMBEDDING_MODEL, FAISS_INDEX_PATH, KNOWLEDGE_BASE_FILE
from langchain_core.documents import Document
from embedding.embedder import PMSVectorStore


def _load_bsc_from_knowledge_base() -> list[dict]:
    if not KNOWLEDGE_BASE_FILE.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KNOWLEDGE_BASE_FILE}")
    with open(KNOWLEDGE_BASE_FILE, encoding="utf-8") as f:
        kb = json.load(f)
    return [doc for doc in kb if doc.get("metadata", {}).get("source") == "BSC"]


def main():
    print("=== Embedding status check ===")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Index path: {FAISS_INDEX_PATH}")
    print(f"Index exists: {FAISS_INDEX_PATH.exists()}")

    bsc_raw = _load_bsc_from_knowledge_base()
    print(f"BSC docs: {len(bsc_raw)}")
    if not bsc_raw:
        raise SystemExit("No BSC documents in knowledge base.")

    vs = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=FAISS_INDEX_PATH)
    if FAISS_INDEX_PATH.exists():
        vs.load_vectorstore()
        print("Loaded existing index.")
    else:
        print("Building new index...")
        docs = [
            Document(page_content=d["text"], metadata=d.get("metadata", {}))
            for d in bsc_raw
        ]
        vs.create_vectorstore(docs)
        vs.save_vectorstore()
        print("Index built and saved.")

    query = "Merchant and Agent Reconciliation Non-Interest Income CBE-Birr Merchants"
    results = vs.search(query, k=3)
    print(f"\nSmoke test query: {query}")
    print(f"Results: {len(results)}")
    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        text = doc.page_content[:120].replace("\n", " ")
        dept = meta.get("department", "?")
        print(f"  [{i}] dept={dept} | {text}...")

    print("\n=== Embedding check PASSED ===")


if __name__ == "__main__":
    main()
