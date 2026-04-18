"""
core/embedder.py
================
Singleton wrapper around sentence-transformers.

Responsibilities:
  - Load the model once at startup (warm-up).
  - Encode a list of texts into L2-normalised float32 numpy arrays.
  - Support batched encoding to avoid OOM on large contracts.

The model (all-MiniLM-L6-v2) produces 384-dimensional embeddings and
runs well on CPU (~30 ms per sentence on modern hardware).
"""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

from app.config import settings


class EmbeddingService:
    """
    Thread-safe singleton that wraps SentenceTransformer.

    Usage:
        embedder = EmbeddingService()
        vectors = embedder.encode(["clause 1", "clause 2"])
        # vectors.shape → (2, 384), dtype float32, L2-normalised
    """

    _instance: "EmbeddingService | None" = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    # ── Initialisation ───────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load the model from disk / HuggingFace hub.
        Called once during application startup.
        Subsequent calls are no-ops.
        """
        if self._loaded:
            return
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        self._model = SentenceTransformer(settings.embedding_model)
        # Quick sanity-check
        test = self._model.encode(["hello world"])
        assert test.shape[1] == settings.embedding_dimension, (
            f"Expected dimension {settings.embedding_dimension}, "
            f"got {test.shape[1]} — update EMBEDDING_DIMENSION in .env"
        )
        self._loaded = True
        logger.info(
            f"Embedding model ready  dim={settings.embedding_dimension}  "
            f"device={self._model.device}"
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode texts into L2-normalised float32 vectors.

        Args:
            texts: list of strings (can be empty)

        Returns:
            numpy array of shape (len(texts), embedding_dimension)
            dtype = float32, each row has unit L2 norm
        """
        if not texts:
            return np.empty((0, settings.embedding_dimension), dtype=np.float32)

        if not self._loaded:
            self.load()

        # Encode in batches to bound memory usage
        batch_size = settings.embedding_batch_size
        all_vectors: list[np.ndarray] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vecs = self._model.encode(
                batch,
                normalize_embeddings=True,   # L2-normalise → cosine sim = dot product
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            all_vectors.append(vecs.astype(np.float32))

        result = np.vstack(all_vectors) if len(all_vectors) > 1 else all_vectors[0]
        logger.debug(f"Encoded {len(texts)} texts → shape {result.shape}")
        return result

    def encode_single(self, text: str) -> np.ndarray:
        """Convenience method — encode one string, return 1-D array."""
        return self.encode([text])[0]


# Module-level singleton
embedder = EmbeddingService()
