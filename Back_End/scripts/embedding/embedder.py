"""Embedding + FAISS Storage Module"""

import json
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class PMSVectorStore:

    def __init__(self, embedding_model: str, index_path: Path):

        self.embedding_model = embedding_model
        self.index_path = Path(index_path)

        logger.info(f"\n🤖 Loading embedding model: {embedding_model}")

        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model
        )

        self.vectorstore = None

    # =========================================================
    # LOAD DOCUMENTS
    # =========================================================

    def load_json_documents(self, json_path: Path) -> List[Document]:

        logger.info(f"\n📂 Loading documents: {json_path.name}")

        with open(json_path, "r", encoding="utf-8") as f:
            raw_docs = json.load(f)

        documents = []

        for item in raw_docs:
            documents.append(
                Document(
                    page_content=item["text"],
                    metadata=item["metadata"]
                )
            )

        logger.info(f"  ✅ Loaded {len(documents)} documents")
        return documents

    # =========================================================
    # CREATE VECTORSTORE
    # =========================================================

    def create_vectorstore(self, documents: List[Document]):

        logger.info(f"\n🧠 Creating embeddings for {len(documents)} documents...")

        self.vectorstore = FAISS.from_documents(
            documents,
            self.embeddings
        )

        logger.info("  ✅ FAISS index created")
        return self.vectorstore

    # =========================================================
    # SAVE / LOAD
    # =========================================================

    def save_vectorstore(self):

        if not self.vectorstore:
            raise ValueError("Vectorstore not initialized")

        logger.info("\n💾 Saving FAISS index...")

        self.vectorstore.save_local(str(self.index_path))

        logger.info(f"  ✅ Saved at: {self.index_path}")

    def load_vectorstore(self):

        logger.info("\n📂 Loading FAISS index...")

        self.vectorstore = FAISS.load_local(
            str(self.index_path),
            self.embeddings,
            allow_dangerous_deserialization=True
        )

        logger.info("  ✅ FAISS index loaded")
        return self.vectorstore

    # =========================================================
    # 🔥 SEARCH (MAIN IMPROVED LOGIC)
    # =========================================================

    def search(self, query: str, k: int = 5):

        if self.vectorstore is None:
            raise ValueError("Vectorstore not loaded")

        department = self.extract_department(query)

        logger.info(f"\n🔍 Detected department: {department}")

        # =========================================================
        # CASE 1: Department found → manual filtering
        # =========================================================
        if department:

            # get all stored documents
            all_docs = list(self.vectorstore.docstore._dict.values())

            # filter only matching department
            filtered_docs = [
                doc for doc in all_docs
                if doc.metadata.get("department") == department
            ]
            logger.info(f"📦 Filtered docs: {len(filtered_docs)}")
            if not filtered_docs:
                logger.warning("⚠️ No documents found for department")
                return []
            # rebuild temporary FAISS index ONLY for that department
            temp_vectorstore = FAISS.from_documents(
                filtered_docs,
                self.embeddings
            )

            results = temp_vectorstore.similarity_search(query, k=k)

            return results

        # =========================================================
        # CASE 2: fallback (no department detected)
        # =========================================================
        return self.vectorstore.similarity_search(query, k=k)

    def extract_department(self, query: str) -> Optional[str]:

        query = query.lower()

        department_map = {
            "online banking": "Online Banking ",
            "card": "Card",
            "digital service development": "Digital_service_devlopment",
            "digital banking reconciliation": "Digital Banking Reconciliation",
            "merchant and agent management": "Merchant and Agent Management ",
        }

        for key, value in department_map.items():
            if key in query:
                return value

        return None