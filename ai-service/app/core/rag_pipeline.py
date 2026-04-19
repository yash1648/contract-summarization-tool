"""
core/rag_pipeline.py
====================
Optimised RAG pipeline — single retrieval + single LLM call.

Performance strategy:
  1. ONE batch of FAISS queries (not separate summary + risk queries)
  2. ONE Ollama call (combined prompt produces summary + risk JSON)
  3. Minimal context: only top-k most relevant chunks
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


# ── Single combined retrieval query set ──────────────────────────────────────
# Merged and reduced to minimise FAISS round-trips.
_ANALYSIS_QUERIES = [
    "parties obligations payment terms penalties",
    "termination liability indemnification risks",
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

        # Step 1: Encode
        vectors = embedder.encode(texts)

        # Step 2: Store in FAISS
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
    #  ANALYZE — SINGLE LLM CALL
    # ══════════════════════════════════════════════════════════

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        Map-Reduce Summarization + RAG Risk Analysis:
          - Summarize all chunks in parallel
          - Multi-level merge of summaries -> Final Summary
          - RAG retrieval -> Risk Analysis JSON
        """
        logger.info(
            f"[analyze] contractId={request.contractId}  "
            f"rawChunks={len(request.chunkTexts)}"
        )

        has_index = self._has_faiss_index(request.contractId)

        # ── Map-Reduce Summarization (Parallel) ──
        logger.info("[analyze] Starting parallel chunk summarization")
        
        from concurrent.futures import ThreadPoolExecutor
        
        # Step 3: Summarize each chunk (parallel)
        with ThreadPoolExecutor(max_workers=4) as executor:
            chunk_summaries = list(executor.map(ollama_client.generate_chunk_summary, request.chunkTexts))
            
        logger.info(f"[analyze] Generated {len(chunk_summaries)} chunk summaries. Merging...")
        
        # Step 4 & 5: Merge summaries and Final summary
        final_summary = self._map_reduce_summaries(chunk_summaries)

        # ── Risk Analysis (RAG) ──
        # Single retrieval pass for risk
        context_chunks = self._retrieve_context(
            contract_id=request.contractId,
            queries=_ANALYSIS_QUERIES,
            fallback_texts=request.chunkTexts,
            has_index=has_index,
        )

        # Single LLM call for risk
        risk_result = ollama_client.generate_risk_analysis(context_chunks)

        chunks_used = len(request.chunkTexts)

        logger.info(
            f"[analyze] done  contractId={request.contractId}  "
            f"riskScore={risk_result['riskScore']}  chunksUsed={chunks_used}"
        )

        return AnalyzeResponse(
            summary=final_summary,
            riskScore=risk_result["riskScore"],
            penaltyClauses=risk_result["penaltyClauses"],
            terminationRisks=risk_result["terminationRisks"],
            liabilityIssues=risk_result["liabilityIssues"],
            otherFlags=risk_result["otherFlags"],
            chunksUsed=chunks_used,
        )

    def _map_reduce_summaries(self, summaries: list[str]) -> str:
        """
        Multi-level summarization for large PDFs.
        Merges chunks in groups of 5 until we have <= 5 summaries, then generates the final.
        """
        if not summaries:
            return "No text available to summarize."
            
        if len(summaries) <= 5:
            return ollama_client.generate_final_summary(summaries)
            
        # Chunk into groups of 5
        merged_groups = []
        for i in range(0, len(summaries), 5):
            group = summaries[i:i+5]
            if len(group) == 1:
                merged_groups.append(group[0])
            else:
                merged_groups.append(ollama_client.merge_summaries(group))
                
        # Recursive call for multi-level summarization
        return self._map_reduce_summaries(merged_groups)

    # ══════════════════════════════════════════════════════════
    #  SEARCH
    # ══════════════════════════════════════════════════════════

    def search(self, request: SearchRequest) -> SearchResponse:
        """
        Encode the user's query and retrieve the top-k most similar chunks.
        """
        logger.info(
            f"[search] query='{request.query}'  "
            f"contractId={request.contractId}  topK={request.topK}"
        )

        query_vec = embedder.encode_single(request.query)

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
        Retrieve the most relevant chunks for analysis.

        Strategy:
          - If FAISS index exists: encode each query and search; deduplicate.
          - Fallback: use raw chunkTexts (evenly sampled).

        Returns:
            Deduplicated chunk texts, capped at rag_top_k * 2.
        """
        if not has_index:
            logger.debug(
                f"[context] No FAISS index for {contract_id}, "
                f"using {len(fallback_texts)} raw chunks as fallback"
            )
            return self._sample_chunks(fallback_texts, settings.rag_top_k)

        # Batch-encode all queries at once (faster than one-by-one)
        query_vecs = embedder.encode(queries)

        seen_texts: set[str] = set()
        collected: list[str] = []

        for query_vec in query_vecs:
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
