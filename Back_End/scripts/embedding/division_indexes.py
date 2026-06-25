"""Pre-built FAISS sub-indexes per division for faster BSC retrieval."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def division_slug(division: str) -> str:
    """Filesystem-safe slug from division name."""
    return re.sub(r"[^a-z0-9]+", "_", division.lower()).strip("_") or "unknown"


class DivisionIndexManager:
    """
    Maintains one FAISS index per division, sharing a single embedding model.
    Avoids full-corpus FAISS scans on every request.
    """

    def __init__(
        self,
        embeddings,
        index_dir: Path,
        *,
        allow_dangerous_deserialization: bool = True,
    ):
        self.embeddings = embeddings
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._allow_dangerous = allow_dangerous_deserialization
        self._stores: Dict[str, FAISS] = {}
        self._docs_by_division: Dict[str, List] = {}

    @property
    def divisions(self) -> list[str]:
        return list(self._stores.keys())

    def build_or_load(self, all_docs: List) -> None:
        """Partition documents by metadata.division and build/load sub-indexes."""
        by_division: Dict[str, List] = {}
        for doc in all_docs:
            meta = doc.metadata if hasattr(doc, "metadata") else {}
            div = (meta.get("division") or "").strip()
            if not div:
                continue
            by_division.setdefault(div, []).append(doc)

        for division, docs in by_division.items():
            self._docs_by_division[division] = docs
            slug = division_slug(division)
            path = self.index_dir / slug

            if (path / "index.faiss").exists():
                logger.info(f"  Loading division index '{division}' from {path.name}/")
                store = FAISS.load_local(
                    str(path),
                    self.embeddings,
                    allow_dangerous_deserialization=self._allow_dangerous,
                )
            else:
                logger.info(f"  Building division index '{division}' ({len(docs)} docs) ...")
                store = FAISS.from_documents(docs, self.embeddings)
                store.save_local(str(path))
                logger.info(f"  Saved division index → {path}")

            self._stores[division] = store

        logger.info(f"  Division sub-indexes ready: {len(self._stores)}")

    def get_store(self, division: Optional[str]) -> Optional[FAISS]:
        if not division:
            return None
        if division in self._stores:
            return self._stores[division]
        div_norm = division.lower().strip()
        for key, store in self._stores.items():
            if key.lower().strip() == div_norm:
                return store
        return None

    def get_division_docs(self, division: Optional[str]) -> List:
        if not division:
            return []
        if division in self._docs_by_division:
            return self._docs_by_division[division]
        div_norm = division.lower().strip()
        for key, docs in self._docs_by_division.items():
            if key.lower().strip() == div_norm:
                return docs
        return []

    def similarity_search_with_score(
        self,
        division: Optional[str],
        query: str,
        k: int,
        *,
        query_prefix: str = "",
    ) -> list:
        store = self.get_store(division)
        if store is None:
            return []
        q = f"{query_prefix}{query}" if query_prefix else query
        return store.similarity_search_with_score(q, k=k)
