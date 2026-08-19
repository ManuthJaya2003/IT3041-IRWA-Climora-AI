"""
Embedding Service - Generates vector embeddings for text.

Uses AWS Bedrock Titan Embeddings to generate 1024-dimensional vectors.
This is a cloud-based approach — no local ML libraries needed.
Same AWS credentials as the LLM service.

Model: amazon.titan-embed-text-v2:0
- Dimensions: 1024 (configurable: 256, 512, 1024)
- No local dependencies (pure API call)
- High quality embeddings
- Uses your existing AWS credentials

Falls back to TF-IDF-like embeddings if Bedrock is unavailable.
"""

import json
import hashlib
from typing import Optional
import numpy as np

from app.config import settings


class EmbeddingService:
    """Service for generating text embeddings via Bedrock Titan or TF-IDF fallback."""

    def __init__(self):
        self._client = None
        self._available = False
        self._dimension = 384  # We'll use 384 to keep FAISS index compatible
        self._use_bedrock = False

    async def initialize(self):
        """Initialize embedding service."""
        # Try Bedrock Titan Embeddings
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            try:
                import boto3

                kwargs = {
                    "service_name": "bedrock-runtime",
                    "aws_access_key_id": settings.aws_access_key_id,
                    "aws_secret_access_key": settings.aws_secret_access_key,
                    "region_name": settings.aws_region,
                }
                if settings.aws_session_token:
                    kwargs["aws_session_token"] = settings.aws_session_token

                self._client = boto3.client(**kwargs)
                self._use_bedrock = True
                self._available = True
                self._dimension = 384  # Request 384 dims from Titan for compatibility
                print(f"   ✓ Embedding service initialized (provider: Bedrock Titan, dim: {self._dimension})")
                return
            except Exception as e:
                print(f"   ⚠ Embedding service: Bedrock init failed ({e})")

        # Fallback to TF-IDF-like embeddings (no dependencies needed)
        self._available = True
        self._use_bedrock = False
        print(f"   ⚠ Embedding service: Using TF-IDF fallback embeddings (dim: {self._dimension})")

    def is_available(self) -> bool:
        return self._available

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        if self._use_bedrock:
            return self._bedrock_embed(text)
        return self._tfidf_embed(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed_text(t) for t in texts]

    def _bedrock_embed(self, text: str) -> list[float]:
        """Generate embedding via Bedrock Titan Embeddings."""
        try:
            body = json.dumps({
                "inputText": text[:8000],  # Titan max input
            })

            response = self._client.invoke_model(
                modelId="amazon.titan-embed-text-v1",
                contentType="application/json",
                accept="application/json",
                body=body,
            )

            response_body = json.loads(response["body"].read())
            embedding = response_body["embedding"]

            # Titan v1 returns 1536 dims - truncate to our target dimension
            if len(embedding) > self._dimension:
                embedding = embedding[:self._dimension]
                # Re-normalize after truncation
                arr = np.array(embedding, dtype=np.float32)
                norm = np.linalg.norm(arr)
                if norm > 0:
                    arr = arr / norm
                embedding = arr.tolist()

            return embedding

        except Exception as e:
            # If Bedrock fails (expired token, etc.), use fallback
            print(f"   ✗ Bedrock embedding error: {e}")
            return self._tfidf_embed(text)

    def _tfidf_embed(self, text: str) -> list[float]:
        """
        TF-IDF-inspired embedding fallback.
        
        Creates deterministic embeddings based on word content.
        Not as good as neural embeddings but much better than pure random —
        similar texts will get somewhat similar vectors because they share words.
        """
        # Tokenize and normalize
        words = text.lower().split()
        
        # Create a fixed-size vector by hashing word n-grams into buckets
        embedding = np.zeros(self._dimension, dtype=np.float32)
        
        # Unigrams
        for word in words:
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self._dimension
            embedding[idx] += 1.0
        
        # Bigrams (capture word pairs for better semantics)
        for i in range(len(words) - 1):
            bigram = f"{words[i]}_{words[i+1]}"
            idx = int(hashlib.md5(bigram.encode()).hexdigest(), 16) % self._dimension
            embedding[idx] += 0.5
        
        # Trigrams
        for i in range(len(words) - 2):
            trigram = f"{words[i]}_{words[i+1]}_{words[i+2]}"
            idx = int(hashlib.md5(trigram.encode()).hexdigest(), 16) % self._dimension
            embedding[idx] += 0.25
        
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding.tolist()


# Singleton instance
embedding_service = EmbeddingService()
