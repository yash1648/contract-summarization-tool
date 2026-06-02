"""
models/schemas.py
=================
Pydantic request / response schemas.

These MUST exactly match the JSON shapes expected by Spring Boot's
AiIntegrationService — any field name change here will break integration.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ── Shared sub-types ─────────────────────────────────────────────────────────

class ChunkItem(BaseModel):
    """A single chunk as sent by Spring Boot in the embed request."""
    index: int
    text: str


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/embed
# ════════════════════════════════════════════════════════════════════════════

class EmbedRequest(BaseModel):
    contractId: str
    chunks: list[ChunkItem]


class EmbedResponse(BaseModel):
    """One UUID per chunk, in the same order as the request."""
    embeddingIds: list[str]
    contractId: str
    chunksEmbedded: int


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/analyze
# ════════════════════════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    contractId: str
    chunkTexts: list[str]


class AnalyzeResponse(BaseModel):
    summary: str
    riskScore: float = Field(ge=0.0, le=10.0)
    penaltyClauses: list[str] = []
    terminationRisks: list[str] = []
    liabilityIssues: list[str] = []
    otherFlags: list[str] = []
    chunksUsed: int


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/ask  —  Q&A: synthesize answer from chunks
# ════════════════════════════════════════════════════════════════════════════

class AskRequest(BaseModel):
    contractId: Optional[str] = None
    query: str
    chunks: list[str] = Field(..., description="Top-K relevant chunk texts as context")


class AskResponse(BaseModel):
    answer: str
    chunksUsed: int


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/search
# ════════════════════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    contractId: Optional[str] = None   # None = search across all contracts
    query: str
    topK: int = Field(5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunkIndex: int
    text: str
    score: float
    contractId: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    query: str
    count: int


# ════════════════════════════════════════════════════════════════════════════
#  DELETE /api/ai/contract/{contractId}
# ════════════════════════════════════════════════════════════════════════════

class DeleteResponse(BaseModel):
    deleted: bool
    contractId: str
    vectorsRemoved: int


# ════════════════════════════════════════════════════════════════════════════
#  GET /api/ai/health
# ════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str
    embeddingModel: str
    ollamaModel: str
    ollamaReachable: bool
    totalIndexes: int


# ════════════════════════════════════════════════════════════════════════════
#  POST /api/ai/extract — Extraction-first pipeline schemas
# ════════════════════════════════════════════════════════════════════════════

class ChunkExtractionData(BaseModel):
    """Structured fields extracted from a single chunk."""
    parties: list[str] = []
    obligations: list[str] = []
    payment_terms: list[str] = []
    dates: list[str] = []
    penalties: list[str] = []
    termination: list[str] = []
    other: list[str] = []


class ChunkExtractionResult(BaseModel):
    """Extraction result for a single chunk."""
    chunk_id: int
    data: ChunkExtractionData


class ExtractRequest(BaseModel):
    contractId: str
    chunkTexts: list[str]


class ExtractResponse(BaseModel):
    contractId: str
    chunks: list[ChunkExtractionResult]
    totalChunks: int
    processingTimeMs: int
