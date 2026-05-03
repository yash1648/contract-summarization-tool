"""
core/rag_pipeline.py
====================
Extraction-first RAG pipeline optimized for low-resource machines.

Key optimizations:
1. Sentence-level embedding (not full chunk embedding)
2. Cosine similarity filtering to reduce context
3. Structured extraction (not summarization)
4. Lightweight model (TinyLlama/Phi-2) for extraction
5. Hash-based caching to avoid re-processing
6. Parallel processing of chunks
7. Model stays loaded in memory (singleton pattern)

Performance targets:
- 2-4x faster than map-reduce summarization
- 50-80% reduction in token usage
- Deterministic, structured JSON output
"""
from __future__ import annotations

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np
from loguru import logger

from app.config import settings
from app.core.embedder import embedder
from app.core.vector_store import vector_store
from app.core.ollama_client import ollama_client
from app.models.schemas import (
    EmbedRequest,
    EmbedResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    DeleteResponse,
    ExtractRequest,
    ExtractResponse,
    ChunkExtractionResult,
    ChunkExtractionData,
)

# ── Query embeddings for sentence filtering ──────────────────────────────────
_FILTER_QUERY_EMBEDDINGS: Optional[np.ndarray] = None
_FILTER_QUERIES_INITIALIZED = False


def _get_filter_query_embeddings() -> np.ndarray:
    """
    Cache and return embeddings for filter queries (loaded lazily on first use).
    This ensures embedder is loaded before we try to encode the queries.
    """
    global _FILTER_QUERY_EMBEDDINGS, _FILTER_QUERIES_INITIALIZED

    if _FILTER_QUERY_EMBEDDINGS is None and not _FILTER_QUERIES_INITIALIZED:
        _FILTER_QUERIES_INITIALIZED = True
        queries = settings.filter_queries
        if queries:
            logger.info(f"Encoding {len(queries)} filter queries")
            _FILTER_QUERY_EMBEDDINGS = embedder.encode(queries)
            logger.debug(f"Filter query embeddings shape: {_FILTER_QUERY_EMBEDDINGS.shape}")
        else:
            logger.warning("No filter queries configured, sentence filtering will be skipped")
            _FILTER_QUERY_EMBEDDINGS = np.array([], dtype=np.float32)

    return _FILTER_QUERY_EMBEDDINGS


# ── Sentence splitting ────────────────────────────────────────────────────────

_SENTENCE_SPLITTER = re.compile(r'(?<=[.!?])\s+')


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, filtering out noise (headers, footers)."""
    if not text or not text.strip():
        return []

    sentences = _SENTENCE_SPLITTER.split(text)

    # Filter out noise patterns
    filtered = []
    noise_patterns = [
        r'^page\s+\d+',
        r'^figure\s+\d+',
        r'^table\s+\d+',
        r'^\s*[\d]+\s*$',  # Standalone numbers
        r'^exhibit\s+[a-z]',
        r'^appendix\s+[a-z]',
    ]
    noise_re = re.compile('|'.join(noise_patterns), re.IGNORECASE)

    for s in sentences:
        s = s.strip()
        if len(s) < 10:  # Skip very short fragments
            continue
        if noise_re.match(s):
            continue
        filtered.append(s)

    return filtered


# ── Sentence filtering via cosine similarity ──────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors (both L2-normalized)."""
    return float(np.dot(a, b))


def filter_sentences_by_relevance(
    sentences: list[str],
    threshold: float = None,
    max_sentences: int = None,
) -> list[str]:
    """
    Filter sentences using cosine similarity against filter query embeddings.

    Args:
        sentences: List of sentence strings
        threshold: Minimum similarity score (default from settings)
        max_sentences: Maximum sentences to return (default from settings)

    Returns:
        Filtered list of sentences sorted by relevance
    """
    if not sentences:
        return []

    threshold = threshold or settings.similarity_threshold
    max_sentences = max_sentences or settings.max_sentences_per_chunk

    # Get query embeddings (lazy loaded)
    query_embeddings = _get_filter_query_embeddings()

    # If no query embeddings configured, return first N sentences as fallback
    if query_embeddings is None or len(query_embeddings) == 0:
        logger.debug("No filter queries configured, returning first sentences as fallback")
        return sentences[:max_sentences]

    # Encode all sentences
    sentence_embeddings = embedder.encode(sentences)

    # Compute max similarity to any query for each sentence
    # sentence_embeddings: (n, dim), query_embeddings: (m, dim)
    # similarities: (n, m) → max over m
    similarities = np.dot(sentence_embeddings, query_embeddings.T)
    max_similarities = similarities.max(axis=1)

    # Filter by threshold
    filtered_indices = np.where(max_similarities >= threshold)[0]

    if len(filtered_indices) == 0:
        # Fallback: if nothing passes threshold, take top sentences by any similarity
        top_k = min(max_sentences, len(sentences))
        top_indices = np.argsort(max_similarities)[-top_k:]
        filtered_indices = top_indices

    # Sort by similarity descending, take top max_sentences
    sorted_indices = filtered_indices[np.argsort(max_similarities[filtered_indices])[::-1]]
    selected = sorted_indices[:max_sentences]

    # Return in original order
    return [sentences[i] for i in sorted(selected)]


def reconstruct_mini_chunk(sentences: list[str]) -> str:
    """Reconstruct a mini-chunk from filtered sentences."""
    return ' '.join(sentences)


# ── Hash-based caching ────────────────────────────────────────────────────────

_CHUNK_CACHE: dict[str, dict] = {}


def get_chunk_cache_key(text: str) -> str:
    """Generate a cache key for a chunk based on its content hash."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def get_cached_result(text: str) -> Optional[dict]:
    """Get cached extraction result for a chunk."""
    key = get_chunk_cache_key(text)
    return _CHUNK_CACHE.get(key)


def cache_result(text: str, result: dict) -> None:
    """Cache extraction result for a chunk."""
    key = get_chunk_cache_key(text)
    _CHUNK_CACHE[key] = result
    logger.debug(f"Cached result for chunk key={key}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

class RagPipeline:
    """
    Stateless pipeline with extraction-first approach.
    Depends only on the three singleton services (embedder, vector_store, ollama_client).
    All methods are synchronous — FastAPI runs them in a thread pool.
    """

    # ══════════════════════════════════════════════════════════
    # EMBED (unchanged - still needed for semantic search)
    # ══════════════════════════════════════════════════════════

    def embed(self, request: EmbedRequest) -> EmbedResponse:
        """
        Encode all chunks for a contract and store them in FAISS.
        (Unchanged from original - needed for semantic search functionality)
        """
        logger.info(
            f"[embed] contractId={request.contractId} "
            f"numChunks={len(request.chunks)}"
        )

        if not request.chunks:
            return EmbedResponse(
                contractId=request.contractId,
                embeddingIds=[],
                chunksEmbedded=0,
            )

        texts = [c.text for c in request.chunks]
        chunk_indexes = [c.index for c in request.chunks]

        vectors = embedder.encode(texts)

        embedding_ids = vector_store.add_vectors(
            contract_id=request.contractId,
            chunk_indexes=chunk_indexes,
            texts=texts,
            vectors=vectors,
        )

        logger.info(
            f"[embed] done contractId={request.contractId} "
            f"embedded={len(embedding_ids)}"
        )
        return EmbedResponse(
            contractId=request.contractId,
            embeddingIds=embedding_ids,
            chunksEmbedded=len(embedding_ids),
        )

    # ══════════════════════════════════════════════════════════
    # EXTRACT — Extraction-first pipeline (new)
    # ══════════════════════════════════════════════════════════

    def extract(self, request: ExtractRequest) -> ExtractResponse:
        """
        Extraction-first analysis pipeline:

        1. Split each chunk into sentences
        2. Generate embeddings for each sentence
        3. Filter sentences by cosine similarity to query embeddings
        4. Reconstruct mini-chunks
        5. Extract structured data using lightweight model
        6. Return per-chunk JSON results

        This replaces the map-reduce summarization approach with:
        - Sentence-level filtering (reduces context by ~70%)
        - Structured extraction (no free-text summarization)
        - Lightweight model (TinyLlama instead of llama3)
        """
        start_time = time.time()
        contract_id = request.contractId
        chunk_texts = request.chunkTexts

        logger.info(
            f"[extract] contractId={contract_id} "
            f"numChunks={len(chunk_texts)}"
        )

        # Process chunks in parallel
        results: list[ChunkExtractionResult] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._extract_single_chunk, text, idx): idx
                for idx, text in enumerate(chunk_texts)
            }
            for future in futures:
                idx = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"[extract] Chunk {idx} failed: {e}")
                    # Return empty extraction on failure
                    results.append(ChunkExtractionResult(
                        chunk_id=idx,
                        data=ChunkExtractionData()
                    ))

        # Sort by chunk_id to maintain order
        results.sort(key=lambda x: x.chunk_id)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"[extract] done contractId={contract_id} "
            f"processed={len(results)} time={elapsed_ms}ms"
        )

        return ExtractResponse(
            contractId=contract_id,
            chunks=results,
            totalChunks=len(results),
            processingTimeMs=elapsed_ms,
        )

    def _extract_single_chunk(self, text: str, chunk_id: int) -> ChunkExtractionResult:
        """
        Process a single chunk through the extraction pipeline:
        1. Check cache
        2. Split into sentences
        3. Filter by relevance
        4. Reconstruct mini-chunk
        5. Extract structured data
        6. Cache and return
        """
        # Check cache first
        cached = get_cached_result(text)
        if cached:
            logger.debug(f"[extract] Cache hit for chunk {chunk_id}")
            return ChunkExtractionResult(chunk_id=chunk_id, data=ChunkExtractionData(**cached))

        # Step 1: Split into sentences
        sentences = split_into_sentences(text)
        if not sentences:
            logger.warning(f"[extract] No sentences extracted from chunk {chunk_id}")
            return ChunkExtractionResult(
                chunk_id=chunk_id,
                data=ChunkExtractionData()
            )

        # Step 2: Filter sentences by relevance
        filtered_sentences = filter_sentences_by_relevance(sentences)

        # Step 3: Reconstruct mini-chunk
        mini_chunk = reconstruct_mini_chunk(filtered_sentences)

        # Step 4: Extract structured data
        extraction = ollama_client.extract_structured(mini_chunk)

        # Step 5: Cache result
        cache_result(text, extraction)

        return ChunkExtractionResult(
            chunk_id=chunk_id,
            data=ChunkExtractionData(**extraction)
        )

    # ══════════════════════════════════════════════════════════
    # ANALYZE — Legacy map-reduce (kept for backward compatibility)
    # ══════════════════════════════════════════════════════════

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        Legacy map-reduce summarization + RAG risk analysis.
        Kept for backward compatibility with existing Java integration.
        Prefer using /api/ai/extract for new implementations.
        """
        logger.info(
            f"[analyze] contractId={request.contractId} "
            f"rawChunks={len(request.chunkTexts)}"
        )

        has_index = self._has_faiss_index(request.contractId)

        # Map-Reduce Summarization (Parallel)
        logger.info("[analyze] Starting parallel chunk summarization")

        with ThreadPoolExecutor(max_workers=4) as executor:
            chunk_summaries = list(executor.map(
                ollama_client.generate_chunk_summary,
                request.chunkTexts
            ))

        logger.info(f"[analyze] Generated {len(chunk_summaries)} chunk summaries. Merging...")

        final_summary = self._map_reduce_summaries(chunk_summaries)

        # Risk Analysis (RAG)
        context_chunks = self._retrieve_context(
            contract_id=request.contractId,
            queries=_ANALYSIS_QUERIES,
            fallback_texts=request.chunkTexts,
            has_index=has_index,
        )

        risk_result = ollama_client.generate_risk_analysis(context_chunks)

        chunks_used = len(request.chunkTexts)

        logger.info(
            f"[analyze] done contractId={request.contractId} "
            f"riskScore={risk_result['riskScore']} chunksUsed={chunks_used}"
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
        """Multi-level summarization for large PDFs."""
        if not summaries:
            return "No text available to summarize."

        if len(summaries) <= 5:
            return ollama_client.generate_final_summary(summaries)

        merged_groups = []
        for i in range(0, len(summaries), 5):
            group = summaries[i:i+5]
            if len(group) == 1:
                merged_groups.append(group[0])
            else:
                merged_groups.append(ollama_client.merge_summaries(group))

        return self._map_reduce_summaries(merged_groups)

    # ══════════════════════════════════════════════════════════
    # SEARCH (unchanged)
    # ══════════════════════════════════════════════════════════

    def search(self, request: SearchRequest) -> SearchResponse:
        """Encode the user's query and retrieve the top-k most similar chunks."""
        logger.info(
            f"[search] query='{request.query}' "
            f"contractId={request.contractId} topK={request.topK}"
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
    # DELETE (unchanged)
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
        """Retrieve the most relevant chunks for analysis."""
        if not has_index:
            logger.debug(
                f"[context] No FAISS index for {contract_id}, "
                f"using {len(fallback_texts)} raw chunks as fallback"
            )
            return self._sample_chunks(fallback_texts, settings.rag_top_k)

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


# ── Module-level singleton ────────────────────────────────────────────────────

rag_pipeline = RagPipeline()

# ── Legacy query constants ────────────────────────────────────────────────────

_ANALYSIS_QUERIES = [
    "parties obligations payment terms penalties",
    "termination liability indemnification risks",
]