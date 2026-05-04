"""
api/routes.py
=============
FastAPI router defining all four endpoints expected by Spring Boot's
AiIntegrationService.

Routes:
    POST   /api/ai/embed                  → embed chunks into FAISS
    POST   /api/ai/analyze                → RAG summarization + risk
    POST   /api/ai/search                 → semantic similarity search
    DELETE /api/ai/contract/{contractId}  → delete contract vectors
    GET    /api/ai/health                 → health / readiness check
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Path
from loguru import logger

from app.core.rag_pipeline import rag_pipeline
from app.core.ollama_client import ollama_client
from app.core.vector_store import vector_store
from app.config import settings
from app.models.schemas import (
    EmbedRequest, EmbedResponse,
    AnalyzeRequest, AnalyzeResponse,
    SearchRequest, SearchResponse,
    DeleteResponse, HealthResponse,
)

router = APIRouter(prefix="/api/ai", tags=["AI"])

# Thread pool for running blocking (CPU/IO) calls from async endpoints
_executor = ThreadPoolExecutor(max_workers=4)


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/embed
# ════════════════════════════════════════════════════════════════════════════

@router.post(
    "/embed",
    response_model=EmbedResponse,
    summary="Embed contract chunks into FAISS",
    description=(
        "Accepts chunks from Spring Boot, generates sentence-transformer embeddings, "
        "stores them in the per-contract FAISS index, and returns one UUID per chunk."
    ),
)
async def embed_chunks(request: EmbedRequest) -> EmbedResponse:
    """
    Request body (from AiIntegrationService.sendChunksForEmbedding):
        {
          "contractId": "...",
          "chunks": [{ "index": 0, "text": "..." }, ...]
        }

    Response (consumed by AiIntegrationService):
        {
          "contractId": "...",
          "embeddingIds": ["uuid1", "uuid2", ...],
          "chunksEmbedded": 12
        }
    """
    logger.info(
        f"POST /embed  contractId={request.contractId}  "
        f"chunks={len(request.chunks)}"
    )
    if not request.chunks:
        raise HTTPException(status_code=400, detail="chunks list is empty")

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, lambda: rag_pipeline.embed(request)
        )
    except Exception as e:
        logger.exception(f"embed failed for {request.contractId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/analyze
# ════════════════════════════════════════════════════════════════════════════

@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="RAG-based contract analysis",
    description=(
        "Retrieves relevant chunks from FAISS using multiple queries, then runs "
        "two Ollama LLM passes: one for summarization, one for risk analysis. "
        "Falls back to raw chunkTexts if the FAISS index is missing."
    ),
)
async def analyze_contract(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Request body (from AiIntegrationService.analyze):
        {
          "contractId": "...",
          "chunkTexts": ["chunk 1 text", "chunk 2 text", ...]
        }

    Response:
        {
          "summary": "...",
          "riskScore": 4.2,
          "penaltyClauses": [...],
          "terminationRisks": [...],
          "liabilityIssues": [...],
          "otherFlags": [...],
          "chunksUsed": 7
        }
    """
    logger.info(
        f"POST /analyze  contractId={request.contractId}  "
        f"rawChunks={len(request.chunkTexts)}"
    )
    if not request.chunkTexts:
        raise HTTPException(status_code=400, detail="chunkTexts list is empty")

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, lambda: rag_pipeline.analyze(request)
        )
    except Exception as e:
        logger.exception(f"analyze failed for {request.contractId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/search
# ════════════════════════════════════════════════════════════════════════════

@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic similarity search",
    description=(
        "Encodes the user query and performs approximate nearest-neighbour "
        "search in FAISS. Scoped to one contract if contractId is provided."
    ),
)
async def semantic_search(request: SearchRequest) -> SearchResponse:
    """
    Request body (from AiIntegrationService.semanticSearch):
        {
          "contractId": "...",   ← optional
          "query": "...",
          "topK": 5
        }

    Response:
        {
          "results": [
            { "chunkIndex": 2, "text": "...", "score": 0.91, "contractId": "..." },
            ...
          ],
          "query": "...",
          "count": 5
        }
    """
    logger.info(
        f"POST /search  query='{request.query}'  "
        f"contractId={request.contractId}  topK={request.topK}"
    )

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, lambda: rag_pipeline.search(request)
        )
    except Exception as e:
        logger.exception(f"search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ════════════════════════════════════════════════════════════════════════════
#  DELETE /api/ai/contract/{contractId}
# ════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/contract/{contractId}",
    response_model=DeleteResponse,
    summary="Delete all FAISS vectors for a contract",
    description=(
        "Removes the contract's FAISS index from memory and disk. "
        "Called by Spring Boot when a contract is deleted from MongoDB."
    ),
)
async def delete_contract(
    contractId: str = Path(..., description="MongoDB contract ID"),
) -> DeleteResponse:
    """
    Called by AiIntegrationService.deleteContractVectors.

    Response:
        { "deleted": true, "contractId": "...", "vectorsRemoved": 12 }
    """
    logger.info(f"DELETE /contract/{contractId}")
    try:
        result = rag_pipeline.delete_contract(contractId)
    except Exception as e:
        logger.exception(f"delete failed for {contractId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ════════════════════════════════════════════════════════════════════════════
#  GET /api/ai/health
# ════════════════════════════════════════════════════════════════════════════

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
)
async def health() -> HealthResponse:
    """
    Returns status of all sub-systems:
      - Embedding model loaded
      - Ollama reachable + model available
      - Number of loaded FAISS indexes
    """
    ollama_ok = ollama_client.is_reachable()
    return HealthResponse(
        status="ok" if ollama_ok else "degraded",
        embeddingModel=settings.embedding_model,
        ollamaModel=settings.ollama_model,
        ollamaReachable=ollama_ok,
        totalIndexes=vector_store.total_indexes(),
    )
