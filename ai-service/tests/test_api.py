"""
tests/test_api.py
=================
Integration tests for all API endpoints.

Uses pytest + httpx (async ASGI test client).
Mocks OllamaClient and EmbeddingService so tests run without GPU or Ollama.

Run with:
    pytest tests/ -v
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Synchronous test client (no async needed for TestClient)."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_embedder():
    """Replace the real embedder with one that returns deterministic vectors."""
    with patch("app.core.rag_pipeline.embedder") as mock:
        # encode() returns shape (N, 384) float32 random-but-normalised vectors
        def fake_encode(texts):
            n = len(texts)
            vecs = np.random.randn(n, 384).astype(np.float32)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            return vecs / norms

        mock.encode.side_effect = fake_encode
        mock.encode_single.side_effect = lambda t: fake_encode([t])[0]
        yield mock


@pytest.fixture(autouse=True)
def mock_ollama():
    """Replace the real Ollama client to avoid needing a running LLM."""
    with patch("app.core.rag_pipeline.ollama_client") as mock:
        mock.generate_summary.return_value = (
            "1. Parties: Acme Corp and Beta Ltd\n"
            "2. Purpose: Software licensing\n"
            "3. Payment: Monthly USD 5000\n"
        )
        mock.generate_risk_analysis.return_value = {
            "riskScore": 4.5,
            "penaltyClauses": ["10% penalty on late delivery"],
            "terminationRisks": ["Immediate termination without cause"],
            "liabilityIssues": ["Unlimited liability clause"],
            "otherFlags": [],
        }
        mock.is_reachable.return_value = True
        yield mock


CONTRACT_ID = "test-contract-abc123"

SAMPLE_CHUNKS = [
    {"index": 0, "text": "This Agreement is entered into by Acme Corp and Beta Ltd."},
    {"index": 1, "text": "Payment of USD 5000 shall be made monthly by the 5th."},
    {"index": 2, "text": "Either party may terminate with 30 days written notice."},
    {"index": 3, "text": "In case of breach, a penalty of 10% of contract value applies."},
    {"index": 4, "text": "This agreement is governed by the laws of New York."},
]


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/embed
# ════════════════════════════════════════════════════════════════════════════

class TestEmbed:

    def test_embed_returns_one_uuid_per_chunk(self, client):
        resp = client.post("/api/ai/embed", json={
            "contractId": CONTRACT_ID,
            "chunks": SAMPLE_CHUNKS,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["contractId"] == CONTRACT_ID
        assert data["chunksEmbedded"] == len(SAMPLE_CHUNKS)
        assert len(data["embeddingIds"]) == len(SAMPLE_CHUNKS)
        # Each ID should be a UUID string
        for eid in data["embeddingIds"]:
            assert len(eid) == 36, f"Expected UUID, got: {eid}"

    def test_embed_empty_chunks_returns_400(self, client):
        resp = client.post("/api/ai/embed", json={
            "contractId": CONTRACT_ID,
            "chunks": [],
        })
        assert resp.status_code == 400

    def test_embed_single_chunk(self, client):
        resp = client.post("/api/ai/embed", json={
            "contractId": "single-chunk-contract",
            "chunks": [{"index": 0, "text": "Single clause text."}],
        })
        assert resp.status_code == 200
        assert resp.json()["chunksEmbedded"] == 1


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/analyze
# ════════════════════════════════════════════════════════════════════════════

class TestAnalyze:

    def test_analyze_returns_summary_and_risk(self, client):
        resp = client.post("/api/ai/analyze", json={
            "contractId": CONTRACT_ID,
            "chunkTexts": [c["text"] for c in SAMPLE_CHUNKS],
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "summary" in data and len(data["summary"]) > 0
        assert 0.0 <= data["riskScore"] <= 10.0
        assert isinstance(data["penaltyClauses"], list)
        assert isinstance(data["terminationRisks"], list)
        assert isinstance(data["liabilityIssues"], list)
        assert isinstance(data["otherFlags"], list)
        assert data["chunksUsed"] >= 0

    def test_analyze_empty_chunks_returns_400(self, client):
        resp = client.post("/api/ai/analyze", json={
            "contractId": CONTRACT_ID,
            "chunkTexts": [],
        })
        assert resp.status_code == 400

    def test_risk_score_bounds(self, client):
        resp = client.post("/api/ai/analyze", json={
            "contractId": CONTRACT_ID,
            "chunkTexts": [c["text"] for c in SAMPLE_CHUNKS],
        })
        score = resp.json()["riskScore"]
        assert 0.0 <= score <= 10.0, f"riskScore out of bounds: {score}"


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/search
# ════════════════════════════════════════════════════════════════════════════

class TestSearch:

    def test_search_returns_results_list(self, client):
        # First embed so we have something to search
        client.post("/api/ai/embed", json={
            "contractId": CONTRACT_ID,
            "chunks": SAMPLE_CHUNKS,
        })
        resp = client.post("/api/ai/search", json={
            "contractId": CONTRACT_ID,
            "query": "payment terms monthly",
            "topK": 3,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert data["query"] == "payment terms monthly"
        assert data["count"] == len(data["results"])

    def test_search_result_fields(self, client):
        client.post("/api/ai/embed", json={
            "contractId": CONTRACT_ID,
            "chunks": SAMPLE_CHUNKS,
        })
        resp = client.post("/api/ai/search", json={
            "contractId": CONTRACT_ID,
            "query": "termination notice",
            "topK": 2,
        })
        for item in resp.json()["results"]:
            assert "chunkIndex" in item
            assert "text" in item
            assert "score" in item
            assert isinstance(item["score"], float)

    def test_search_without_contract_id(self, client):
        resp = client.post("/api/ai/search", json={
            "query": "penalty clause",
            "topK": 5,
        })
        assert resp.status_code == 200

    def test_search_top_k_respected(self, client):
        client.post("/api/ai/embed", json={
            "contractId": CONTRACT_ID,
            "chunks": SAMPLE_CHUNKS,
        })
        resp = client.post("/api/ai/search", json={
            "contractId": CONTRACT_ID,
            "query": "contract agreement",
            "topK": 2,
        })
        assert len(resp.json()["results"]) <= 2


# ════════════════════════════════════════════════════════════════════════════
#  DELETE /api/ai/contract/{contractId}
# ════════════════════════════════════════════════════════════════════════════

class TestDelete:

    def test_delete_contract_returns_true(self, client):
        # Embed first so there's something to delete
        client.post("/api/ai/embed", json={
            "contractId": "delete-me-contract",
            "chunks": SAMPLE_CHUNKS,
        })
        resp = client.delete("/api/ai/contract/delete-me-contract")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["deleted"] is True
        assert data["contractId"] == "delete-me-contract"
        assert isinstance(data["vectorsRemoved"], int)

    def test_delete_nonexistent_contract(self, client):
        """Deleting a contract that was never embedded should still return 200."""
        resp = client.delete("/api/ai/contract/nonexistent-id-xyz")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert resp.json()["vectorsRemoved"] == 0


# ════════════════════════════════════════════════════════════════════════════
#  GET /api/ai/health
# ════════════════════════════════════════════════════════════════════════════

class TestHealth:

    def test_health_returns_ok(self, client):
        with patch("app.api.routes.ollama_client") as m:
            m.is_reachable.return_value = True
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "embeddingModel" in data
        assert "ollamaModel" in data
        assert isinstance(data["ollamaReachable"], bool)
        assert isinstance(data["totalIndexes"], int)
