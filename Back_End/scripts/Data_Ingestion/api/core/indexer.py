"""
api/core/indexer.py
Builds a FAISS flat-L2 index from all saved document JSON files.
Requires: pip install sentence-transformers faiss-cpu
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)


def _load_all_documents(doc_files: Dict[str, Path]) -> List[Dict[str, Any]]:
    all_docs = []
    for doc_type, path in doc_files.items():
        if not path.exists():
            logger.info(f"  (skip) {doc_type}: not found")
            continue
        with open(path, encoding="utf-8") as f:
            docs = json.load(f)
        logger.info(f"  ✓ {doc_type}: {len(docs)} documents")
        all_docs.extend(docs)
    return all_docs


def build_index(
    doc_files:  Dict[str, Path],
    index_path: Path,
    meta_path:  Path,
    model_name: str = "all-MiniLM-L6-v2",
) -> Tuple[int, str]:
    docs = _load_all_documents(doc_files)
    if not docs:
        return 0, "No documents found. Upload files first."

    try:
        from sentence_transformers import SentenceTransformer
        model      = SentenceTransformer(model_name)
        embeddings = model.encode([d["text"] for d in docs], show_progress_bar=False, convert_to_numpy=True)
    except ImportError:
        return 0, "sentence-transformers not installed. Run: pip install sentence-transformers"

    try:
        import faiss, numpy as np
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings.astype(np.float32))
        faiss.write_index(index, str(index_path))
    except ImportError:
        return 0, "faiss-cpu not installed. Run: pip install faiss-cpu"

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"index": i, "metadata": d.get("metadata", {}), "text_preview": d["text"][:120]}
             for i, d in enumerate(docs)],
            f, indent=2, ensure_ascii=False,
        )

    total = index.ntotal
    return total, f"Index rebuilt: {total} vectors from {len(docs)} documents."
