"""
core/rag_pipeline.py
====================
Retrieval-Augmented Generation (RAG) pipeline.

This is the brain of the AI service.  It wires together:
  1. EmbeddingService  — encodes chunks and queries into vectors
  2. VectorStore       — persists and retrieves vectors via FAISS
  3. OllamaClient      — runs LLM inference (summary + risk analysis)

Pipeline for /api/ai/embed:
  chunks → encode() → add_vectors() → [embeddingIds]

Pipeline for /api/ai/analyze:
  chunkTexts  ─────────────────────────────────┐
                                                ▼
  SUMMARY query → encode → FAISS search → top-k chunks → LLM summary
  RISK    query → encode → FAISS search → top-k chunks → LLM risk JSON
                                                │
                                                ▼
                                    AnalyzeResponse

Pipeline for /api/ai/search:
  user query → encode → FAISS search → [SearchResultItem, ...]
"""
from __future__ import annotations

from loguru import logger

from app.config import settings
from app.core.embedder import embedder
from app.core.vector_store import vector_store
from app.core.ollama_client import ollama_client
from app.models.schemas import (
    EmbedRequest, EmbedResponse,
    AnalyzeRequest, AnalyzeResponse,
    SearchRequest, SearchResponse, SearchResultItem,
    DeleteResponse,
)


# ── Retrieval queries used to gather context ──────────────────────────────────
# These generic queries pull the most relevant sections for each analysis task.
_SUMMARY_QUERIES = [
    "parties involved obligations payment terms",
    "contract duration renewal termination conditions",
    "key deliverables deadlines milestones",
]

_RISK_QUERIES = [
    "penalty clause fine breach violation",
    "termination early exit notice period auto-renewal",
    "liability indemnification unlimited damages",
    "intellectual property assignment confidentiality",
    "dispute resolution jurisdiction governing law",
]


class RagPipeline:
    """
    Stateless pipeline; depends only on the three singleton services.
    All methods are synchronous — FastAPI runs them in a thread pool.
    """

    # ══════════════════════════════════════════════════════════
    #  EMBED
    # ══════════════════════════════════════════════════════════

    def embed(self, request: EmbedRequest) -> EmbedResponse:
        """
        Encode all chunks for a contract and store them in FAISS.

        Steps:
          1. Extract text from each ChunkItem
          2. Batch-encode with sentence-transformer
          3. Store in VectorStore (returns one UUID per chunk)
          4. Return EmbedResponse with the UUIDs

        The order of embeddingIds matches the order of chunks in the request.
        """
        logger.info(
            f"[embed] contractId={request.contractId}  "
            f"numChunks={len(request.chunks)}"
        )

        if not request.chunks:
            return EmbedResponse(
                contractId=request.contractId,
                embeddingIds=[],
                chunksEmbedded=0,
            )

        texts         = [c.text for c in request.chunks]
        chunk_indexes = [c.index for c in request.chunks]

        # ── Step 1: Encode ────────────────────────────────────
        vectors = embedder.encode(texts)   # shape (N, 384), float32, L2-normed

        # ── Step 2: Store in FAISS ────────────────────────────
        embedding_ids = vector_store.add_vectors(
            contract_id=request.contractId,
            chunk_indexes=chunk_indexes,
            texts=texts,
            vectors=vectors,
        )

        logger.info(
            f"[embed] done  contractId={request.contractId}  "
            f"embedded={len(embedding_ids)}"
        )
        return EmbedResponse(
            contractId=request.contractId,
            embeddingIds=embedding_ids,
            chunksEmbedded=len(embedding_ids),
        )

    # ══════════════════════════════════════════════════════════
    #  ANALYZE
    # ══════════════════════════════════════════════════════════

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        Full RAG analysis: retrieve relevant chunks, then run two LLM passes.

        Pass 1 — Summary:
          Query FAISS with generic summary queries, assemble top-k context,
          ask Ollama to produce a structured human-readable summary.

        Pass 2 — Risk:
          Query FAISS with risk-oriented queries, ask Ollama to return
          a JSON risk report with penalty/termination/liability lists and a score.

        If the FAISS index for this contract is empty (e.g. embed was skipped),
        we fall back to using the raw chunkTexts provided in the request directly.
        This ensures analysis always works even if embedding was bypassed.
        """
        logger.info(
            f"[analyze] contractId={request.contractId}  "
            f"rawChunks={len(request.chunkTexts)}"
        )

        has_index = self._has_faiss_index(request.contractId)

        # ── Pass 1: Summary ───────────────────────────────────
        summary_chunks = self._retrieve_context(
            contract_id=request.contractId,
            queries=_SUMMARY_QUERIES,
            fallback_texts=request.chunkTexts,
            has_index=has_index,
        )
        summary = ollama_client.generate_summary(summary_chunks)

        # ── Pass 2: Risk ──────────────────────────────────────
        risk_chunks = self._retrieve_context(
            contract_id=request.contractId,
            queries=_RISK_QUERIES,
            fallback_texts=request.chunkTexts,
            has_index=has_index,
        )
        risk_data = ollama_client.generate_risk_analysis(risk_chunks)

        chunks_used = len(set(summary_chunks) | set(risk_chunks))

        logger.info(
            f"[analyze] done  contractId={request.contractId}  "
            f"riskScore={risk_data['riskScore']}  chunksUsed={chunks_used}"
        )

        return AnalyzeResponse(
            summary=summary,
            riskScore=risk_data["riskScore"],
            penaltyClauses=risk_data["penaltyClauses"],
            terminationRisks=risk_data["terminationRisks"],
            liabilityIssues=risk_data["liabilityIssues"],
            otherFlags=risk_data["otherFlags"],
            chunksUsed=chunks_used,
        )

    # ══════════════════════════════════════════════════════════
    #  SEARCH
    # ══════════════════════════════════════════════════════════

    def search(self, request: SearchRequest) -> SearchResponse:
        """
        Encode the user's query and retrieve the top-k most similar chunks.

        If contractId is provided, search is scoped to that contract's index.
        Otherwise all indexes are searched (cross-contract mode).
        """
        logger.info(
            f"[search] query='{request.query}'  "
            f"contractId={request.contractId}  topK={request.topK}"
        )

        # Encode the query
        query_vec = embedder.encode_single(request.query)

        # Search FAISS
        raw_results = vector_store.search(
            query_vector=query_vec,
            top_k=request.topK,
            contract_id=request.contractId,
            min_score=settings.rag_min_score,
        )

        results = [
            SearchResultItem(
                chunkIndex=r["chunkIndex"],
                text=r["text"],
                score=r["score"],
                contractId=r.get("contractId"),
            )
            for r in raw_results
        ]

        logger.info(f"[search] returned {len(results)} results")
        return SearchResponse(
            results=results,
            query=request.query,
            count=len(results),
        )

    # ══════════════════════════════════════════════════════════
    #  DELETE
    # ══════════════════════════════════════════════════════════

    def delete_contract(self, contract_id: str) -> DeleteResponse:
        """Remove all FAISS vectors for a contract."""
        logger.info(f"[delete] contractId={contract_id}")
        removed = vector_store.delete_contract(contract_id)
        return DeleteResponse(
            deleted=True,
            contractId=contract_id,
            vectorsRemoved=removed,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _has_faiss_index(self, contract_id: str) -> bool:
        """Check if a FAISS index exists for this contract."""
        contracts = vector_store.list_contracts()
        return any(c["contractId"] == contract_id for c in contracts)

    def _retrieve_context(
        self,
        contract_id: str,
        queries: list[str],
        fallback_texts: list[str],
        has_index: bool,
    ) -> list[str]:
        """
        Retrieve the most relevant chunks for a set of queries.

        Strategy:
          - If FAISS index exists: encode each query and search; deduplicate results.
          - Fallback: use raw chunkTexts from the request (e.g. when embed was skipped).

        Returns:
            Deduplicated list of chunk texts, limited to settings.rag_top_k.
        """
        if not has_index:
            logger.debug(
                f"[context] No FAISS index for {contract_id}, "
                f"using {len(fallback_texts)} raw chunks as fallback"
            )
            # Use the most central chunks (take evenly distributed sample)
            return self._sample_chunks(fallback_texts, settings.rag_top_k)

        # Run each query and collect unique results
        seen_texts: set[str] = set()
        collected: list[str] = []

        for query in queries:
            query_vec = embedder.encode_single(query)
            results = vector_store.search(
                query_vector=query_vec,
                top_k=settings.rag_top_k,
                contract_id=contract_id,
                min_score=settings.rag_min_score,
            )
            for r in results:
                text = r["text"]
                if text not in seen_texts:
                    seen_texts.add(text)
                    collected.append(text)

        # Cap total context to avoid overflowing LLM context window
        max_context = settings.rag_top_k * 2
        logger.debug(
            f"[context] Retrieved {len(collected)} unique chunks "
            f"(cap={max_context})"
        )
        return collected[:max_context]

    @staticmethod
    def _sample_chunks(chunks: list[str], n: int) -> list[str]:
        """Return up to n evenly distributed chunks from the list."""
        if len(chunks) <= n:
            return chunks
        step = len(chunks) / n
        return [chunks[int(i * step)] for i in range(n)]


# Module-level singleton
rag_pipeline = RagPipeline()
