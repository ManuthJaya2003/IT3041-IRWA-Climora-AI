"""
Vector Store Service (FAISS - Local).
Used by the Information Retrieval Agent for semantic search over climate documents.

FAISS (Facebook AI Similarity Search) runs entirely locally — no cloud, no API keys.
Index and document metadata are persisted to disk in the ./vector_data directory.

How it works:
1. Documents are embedded into 384-dimensional vectors (using sentence-transformers or similar)
2. FAISS indexes these vectors for fast similarity search
3. When a query comes in, it's embedded and FAISS finds the most similar stored documents
4. Document metadata (source, content, topic) is stored alongside in a JSON file
"""

import os
import json
import faiss
import numpy as np
from typing import Optional
from datetime import datetime

from app.config import settings


class VectorStoreService:
    """Service for local vector similarity search using FAISS."""

    def __init__(self):
        self._index = None
        self._documents: list[dict] = []  # Metadata store
        self._available = False
        self._dimension = 384  # Default embedding dimension (sentence-transformers/all-MiniLM-L6-v2)
        self._data_dir = ""

    async def initialize(self):
        """Initialize FAISS index — load from disk or create new."""
        try:
            # Data directory for persisting index
            self._data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "vector_data",
            )
            os.makedirs(self._data_dir, exist_ok=True)

            index_path = os.path.join(self._data_dir, "climate_index.faiss")
            metadata_path = os.path.join(self._data_dir, "documents.json")

            # Try to load existing index
            if os.path.exists(index_path) and os.path.exists(metadata_path):
                self._index = faiss.read_index(index_path)
                with open(metadata_path, "r", encoding="utf-8") as f:
                    self._documents = json.load(f)
                self._dimension = self._index.d
            else:
                # Create a new empty index (Inner Product for cosine after normalization)
                self._index = faiss.IndexFlatIP(self._dimension)

            self._available = True
            print(f"   ✓ FAISS vector store initialized (documents: {self._index.ntotal}, dim: {self._dimension})")

        except Exception as e:
            self._available = False
            print(f"   ⚠ FAISS: Init failed ({e})")

    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available

    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: Optional[list[list[float]]] = None,
    ) -> dict:
        """
        Add documents to the vector store.

        Args:
            documents: List of text content.
            metadatas: List of metadata dicts for each document.
            ids: List of unique IDs for each document.
            embeddings: Pre-computed embeddings (if None, uses simple TF-IDF-like fallback).

        Returns:
            Result dict with count of added documents.
        """
        if not self._available:
            return {"error": "Vector store not available", "added": 0}

        try:
            if embeddings is None:
                # Generate simple embeddings as fallback
                # In production, the IR agent would provide embeddings from Bedrock/sentence-transformers
                embeddings = [self._simple_embed(doc) for doc in documents]

            # Convert to numpy array and normalize for cosine similarity
            vectors = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(vectors)

            # Add to FAISS index
            self._index.add(vectors)

            # Store metadata
            for i, doc_id in enumerate(ids):
                self._documents.append({
                    "id": doc_id,
                    "content": documents[i],
                    "metadata": metadatas[i],
                    "added_at": datetime.utcnow().isoformat(),
                })

            # Persist to disk
            await self._save_to_disk()

            return {"added": len(documents), "total": self._index.ntotal}

        except Exception as e:
            return {"error": str(e), "added": 0}

    async def query_similar(
        self,
        query_text: str,
        top_k: int = 5,
        query_embedding: Optional[list[float]] = None,
    ) -> list[dict]:
        """
        Query for similar documents.

        Args:
            query_text: The search query in natural language.
            top_k: Number of results to return.
            query_embedding: Pre-computed query embedding (if None, uses simple fallback).

        Returns:
            List of matching documents with scores and metadata.
        """
        if not self._available or self._index.ntotal == 0:
            return []

        try:
            if query_embedding is None:
                query_embedding = self._simple_embed(query_text)

            # Normalize query vector
            query_vector = np.array([query_embedding], dtype=np.float32)
            faiss.normalize_L2(query_vector)

            # Search
            k = min(top_k, self._index.ntotal)
            scores, indices = self._index.search(query_vector, k)

            # Build results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx == -1:
                    continue  # No result
                doc = self._documents[idx]
                results.append({
                    "id": doc["id"],
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "score": float(scores[0][i]),  # Cosine similarity (0-1)
                    "source_name": doc["metadata"].get("source", "Unknown"),
                    "url": doc["metadata"].get("url"),
                    "snippet": doc["content"][:300],
                })

            return results

        except Exception as e:
            print(f"   ✗ FAISS query error: {e}")
            return []

    async def delete_documents(self, ids: list[str]) -> dict:
        """
        Delete documents by ID.
        Note: FAISS IndexFlatIP doesn't support deletion natively,
        so we rebuild the index without the deleted docs.
        """
        if not self._available:
            return {"error": "Vector store not available"}

        try:
            # Find indices to keep
            keep_indices = [
                i for i, doc in enumerate(self._documents) if doc["id"] not in ids
            ]

            if len(keep_indices) == len(self._documents):
                return {"deleted": 0, "message": "No matching documents found"}

            # Rebuild index with remaining documents
            remaining_docs = [self._documents[i] for i in keep_indices]

            # Get vectors for remaining docs (re-embed)
            remaining_embeddings = [
                self._simple_embed(doc["content"]) for doc in remaining_docs
            ]

            # Create new index
            self._index = faiss.IndexFlatIP(self._dimension)
            if remaining_embeddings:
                vectors = np.array(remaining_embeddings, dtype=np.float32)
                faiss.normalize_L2(vectors)
                self._index.add(vectors)

            deleted_count = len(self._documents) - len(remaining_docs)
            self._documents = remaining_docs

            await self._save_to_disk()

            return {"deleted": deleted_count}

        except Exception as e:
            return {"error": str(e)}

    async def get_collection_stats(self) -> dict:
        """Get stats about the vector store."""
        if not self._available:
            return {"available": False}

        return {
            "available": True,
            "engine": "FAISS (local)",
            "document_count": self._index.ntotal,
            "dimension": self._dimension,
            "data_directory": self._data_dir,
        }

    async def reset(self) -> dict:
        """Delete all documents. Use with caution."""
        if not self._available:
            return {"error": "Vector store not available"}

        self._index = faiss.IndexFlatIP(self._dimension)
        self._documents = []
        await self._save_to_disk()
        return {"reset": True, "document_count": 0}

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _simple_embed(self, text: str) -> list[float]:
        """
        Simple fallback embedding using character/word hashing.
        
        This is a DEVELOPMENT PLACEHOLDER. In production, the IR agent should
        provide proper embeddings from:
        - sentence-transformers (e.g., all-MiniLM-L6-v2 → 384 dims)
        - AWS Bedrock Titan Embeddings (amazon.titan-embed-text-v1 → 1536 dims)
        
        This simple version uses random projection of word hashes to create
        a fixed-size vector. It provides basic functionality for testing the
        pipeline but won't give meaningful semantic results.
        """
        # Deterministic hash-based embedding for development
        np.random.seed(hash(text.lower().strip()) % (2**32))
        embedding = np.random.randn(self._dimension).astype(np.float32)
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding.tolist()

    async def _save_to_disk(self):
        """Persist index and metadata to disk."""
        index_path = os.path.join(self._data_dir, "climate_index.faiss")
        metadata_path = os.path.join(self._data_dir, "documents.json")

        faiss.write_index(self._index, index_path)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self._documents, f, indent=2, ensure_ascii=False)


# Singleton instance
vector_store_service = VectorStoreService()
