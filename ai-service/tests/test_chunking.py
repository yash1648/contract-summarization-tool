"""
tests/test_chunking.py
======================
Unit tests for the VectorStore and EmbeddingService core logic.
(No LLM or network required.)
"""
import numpy as np
import pytest
from unittest.mock import patch
from app.core.vector_store import VectorStore


def make_store(tmp_path):
    """Create a fresh VectorStore backed by a temp directory."""
    with patch("app.core.vector_store.settings") as s:
        s.faiss_index_dir = tmp_path
        s.embedding_dimension = 4   # tiny dim for tests
        store = VectorStore.__new__(VectorStore)
        store._indexes = {}
        store._lock = __import__("threading").Lock()
        store._index_dir = tmp_path
        return store


def random_vecs(n, dim=4):
    v = np.random.randn(n, dim).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


class TestVectorStore:

    def test_add_and_search(self, tmp_path):
        store = make_store(tmp_path)
        vecs = random_vecs(5)
        ids = store.add_vectors("c1", list(range(5)),
                                [f"chunk {i}" for i in range(5)], vecs)
        assert len(ids) == 5
        results = store.search(vecs[0], top_k=3, contract_id="c1")
        assert len(results) <= 3
        assert results[0]["score"] >= results[-1]["score"]  # sorted desc

    def test_delete_contract(self, tmp_path):
        store = make_store(tmp_path)
        vecs = random_vecs(3)
        store.add_vectors("c2", [0, 1, 2], ["a", "b", "c"], vecs)
        removed = store.delete_contract("c2")
        assert removed == 3
        assert "c2" not in store._indexes

    def test_delete_nonexistent(self, tmp_path):
        store = make_store(tmp_path)
        removed = store.delete_contract("does-not-exist")
        assert removed == 0

    def test_search_respects_top_k(self, tmp_path):
        store = make_store(tmp_path)
        vecs = random_vecs(10)
        store.add_vectors("c3", list(range(10)),
                           [f"t{i}" for i in range(10)], vecs)
        results = store.search(vecs[0], top_k=3, contract_id="c3")
        assert len(results) <= 3

    def test_cross_contract_search(self, tmp_path):
        store = make_store(tmp_path)
        v1 = random_vecs(3)
        v2 = random_vecs(3)
        store.add_vectors("cA", [0,1,2], ["a0","a1","a2"], v1)
        store.add_vectors("cB", [0,1,2], ["b0","b1","b2"], v2)
        # No contractId → searches both
        results = store.search(v1[0], top_k=5)
        contract_ids = {r["contractId"] for r in results}
        assert len(contract_ids) >= 1   # at least one contract found
