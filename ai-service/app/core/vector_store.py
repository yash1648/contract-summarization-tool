"""
core/vector_store.py
====================
Per-contract FAISS index management.
"""

from __future__ import annotations

import pickle
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from loguru import logger

from app.config import settings


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class ChunkMeta:
    embedding_id: str
    chunk_index: int
    text: str
    contract_id: str


@dataclass
class ContractIndex:
    contract_id: str
    index: faiss.IndexFlatIP = field(default=None)
    metadata: list[ChunkMeta] = field(default_factory=list)

    def __post_init__(self):
        # 🔥 FIX: removed accidental ":1" bug + ensure correct init
        if self.index is None:
            self.index = faiss.IndexFlatIP(settings.embedding_dimension)

    @property
    def size(self) -> int:
        return self.index.ntotal


# ── Vector Store ─────────────────────────────────────────────────────────────

class VectorStore:

    def __init__(self):
        self._indexes: dict[str, ContractIndex] = {}
        self._lock = threading.Lock()
        self._index_dir: Path = settings.faiss_index_dir
        self._load_all_from_disk()

    # ── Write ────────────────────────────────────────────────────────────────

    def add_vectors(
            self,
            contract_id: str,
            chunk_indexes: list[int],
            texts: list[str],
            vectors: np.ndarray,
    ) -> list[str]:

        assert vectors.dtype == np.float32, "Vectors must be float32"
        assert vectors.shape[0] == len(texts) == len(chunk_indexes), \
            "Mismatch between vectors, texts, and chunk_indexes lengths"

        # 🔥 CRITICAL FIX: enforce dimension consistency
        if vectors.shape[1] != settings.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {settings.embedding_dimension}, "
                f"got {vectors.shape[1]}"
            )

        embedding_ids: list[str] = []

        with self._lock:
            if contract_id not in self._indexes:
                self._indexes[contract_id] = ContractIndex(contract_id=contract_id)

            contract_idx = self._indexes[contract_id]

            for ci, text, vec in zip(chunk_indexes, texts, vectors):
                eid = str(uuid.uuid4())
                embedding_ids.append(eid)

                vec = vec.astype(np.float32).reshape(1, -1)

                # Optional but recommended for cosine similarity
                # faiss.normalize_L2(vec)

                contract_idx.index.add(vec)

                contract_idx.metadata.append(ChunkMeta(
                    embedding_id=eid,
                    chunk_index=ci,
                    text=text,
                    contract_id=contract_id,
                ))

            logger.info(
                f"VectorStore: added {len(embedding_ids)} vectors to contract={contract_id} "
                f"(total={contract_idx.size})"
            )

            self._persist(contract_id)

        return embedding_ids

    # ── Read ─────────────────────────────────────────────────────────────────

    def search(
            self,
            query_vector: np.ndarray,
            top_k: int,
            contract_id: Optional[str] = None,
            min_score: float = 0.0,
    ) -> list[dict]:

        # 🔥 ensure correct dtype + shape
        query_vector = query_vector.astype(np.float32)

        if query_vector.shape[0] != settings.embedding_dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {settings.embedding_dimension}, "
                f"got {query_vector.shape[0]}"
            )

        query_vector = query_vector.reshape(1, -1)

        # Optional normalization
        # faiss.normalize_L2(query_vector)

        results: list[dict] = []

        with self._lock:
            targets = (
                [self._indexes[contract_id]]
                if contract_id and contract_id in self._indexes
                else list(self._indexes.values())
            )

            for ci in targets:
                if ci.size == 0:
                    continue

                actual_k = min(top_k, ci.size)
                scores, idxs = ci.index.search(query_vector, actual_k)

                for score, faiss_idx in zip(scores[0], idxs[0]):
                    if faiss_idx == -1:
                        continue
                    if float(score) < min_score:
                        continue

                    meta = ci.metadata[faiss_idx]

                    results.append({
                        "chunkIndex":  meta.chunk_index,
                        "text":        meta.text,
                        "score":       float(score),
                        "contractId":  meta.contract_id,
                        "embeddingId": meta.embedding_id,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ── Delete ───────────────────────────────────────────────────────────────

    def delete_contract(self, contract_id: str) -> int:
        with self._lock:
            if contract_id not in self._indexes:
                logger.warning(f"VectorStore: no index found for contract={contract_id}")
                return 0

            removed = self._indexes[contract_id].size
            del self._indexes[contract_id]
            self._delete_from_disk(contract_id)

            logger.info(f"VectorStore: deleted {removed} vectors for contract={contract_id}")
            return removed

    # ── Diagnostics ──────────────────────────────────────────────────────────

    def list_contracts(self) -> list[dict]:
        with self._lock:
            return [
                {"contractId": cid, "vectorCount": ci.size}
                for cid, ci in self._indexes.items()
            ]

    def total_indexes(self) -> int:
        with self._lock:
            return len(self._indexes)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _persist(self, contract_id: str) -> None:
        path = self._index_path(contract_id)
        try:
            data = {
                "index_bytes": faiss.serialize_index(self._indexes[contract_id].index),
                "metadata":    self._indexes[contract_id].metadata,
                "contract_id": contract_id,
            }
            with open(path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.debug(f"VectorStore: persisted index → {path}")

        except Exception as e:
            logger.error(f"VectorStore: failed to persist {contract_id}: {e}")

    def _load_all_from_disk(self) -> None:
        loaded = 0
        for path in self._index_dir.glob("*.faiss"):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)

                index = faiss.deserialize_index(data["index_bytes"])

                ci = ContractIndex(
                    contract_id=data["contract_id"],
                    index=index,
                    metadata=data["metadata"],
                )

                self._indexes[data["contract_id"]] = ci
                loaded += 1

                logger.debug(f"VectorStore: loaded {ci.size} vectors from {path.name}")

            except Exception as e:
                logger.warning(f"VectorStore: could not load {path}: {e}")

        logger.info(f"VectorStore: restored {loaded} contract index(es) from disk")

    def _delete_from_disk(self, contract_id: str) -> None:
        path = self._index_path(contract_id)
        if path.exists():
            path.unlink()
            logger.debug(f"VectorStore: removed {path}")

    def _index_path(self, contract_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in contract_id)
        return self._index_dir / f"{safe}.faiss"


# Singleton
vector_store = VectorStore()