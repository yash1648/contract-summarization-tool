# AI Contract System - Architecture Documentation

## System Architecture Overview

The AI Contract Summarization System is a **modular monolithic web application** with an integrated AI pipeline. It combines a Spring Boot backend with a Python AI microservice to provide intelligent contract analysis using Retrieval-Augmented Generation (RAG).

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Frontend (Thymeleaf)                          │
│  index | upload | contracts | contract-detail | analysis | search   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                   HTTP Requests/Responses
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                    Spring Boot Backend (com.grim.backend)              │
│                                                                       │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐  │
│  │     Controllers      │  │             Services                  │  │
│  │  ┌────────────────┐  │  │  ┌──────────────────────────────┐    │  │
│  │  │ContractController│ │  │  │ ContractService            │    │  │
│  │  │  /contracts/*   │  │  │  │  upload → extract → chunk  │    │  │
│  │  ├────────────────┤  │  │  │  → embed → persist          │    │  │
│  │  │AnalysisController│ │  │  ├──────────────────────────────┤    │  │
│  │  │  /analysis/*    │  │  │  │ AnalysisService             │    │  │
│  │  ├────────────────┤  │  │  │  analyze + search + ask      │    │  │
│  │  │DashboardController│ │  │  ├──────────────────────────────┤    │  │
│  │  │  /dashboard     │  │  │  │ AiIntegrationService        │────┼──┐│
│  │  ├────────────────┤  │  │  │  HTTP bridge to Python      │    │  ││
│  │  │HealthController  │  │  │  ├──────────────────────────────┤    │  ││
│  │  │  /health        │  │  │  │ AiHealthService             │    │  ││
│  │  └────────────────┘  │  │  │  cached health checks       │    │  ││
│  │                      │  │  ├──────────────────────────────┤    │  ││
│  │  ┌────────────────┐  │  │  │ TextExtractionService        │    │  ││
│  │  │   Models        │  │  │  │ PDFBox + POI text extraction│    │  ││
│  │  │  Contract      │◄─┘  │  ├──────────────────────────────┤    │  ││
│  │  │  ContractChunk │     │  │ ChunkingService              │    │  ││
│  │  │  AnalysisResult│     │  │  configurable size/overlap   │    │  ││
│  │  │  RiskReport    │     │  └──────────────────────────────┘    │  ││
│  │  └────────────────┘     │                                       │  ││
│  │  ┌────────────────┐     │  ┌──────────────────────────────┐     │  ││
│  │  │ Repositories    │     │  │     MongoDB                  │     │  ││
│  │  │  ContractRepo │◄─────┤  │  contracts + analysisResults │     │  ││
│  │  │  AnalysisRepo │     │  └──────────────────────────────┘     │  ││
│  │  └────────────────┘     │                                       │  ││
│  │  ┌────────────────┐     │                                       │  ││
│  │  │  DTOs          │     │                                       │  ││
│  │  │  Exception     │     │                                       │  ││
│  │  └────────────────┘     │                                       │  ││
│  └─────────────────────────┘                                       │  ││
└────────────────────────────────────────────────────────────────────┘  │
                                  │                                      │
                         REST API Calls (HTTP)                           │
                                  │                                      │
┌─────────────────────────────────▼──────────────────────────────────────┘
│                       Python AI Microservice                               │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │                     FastAPI Application                            │     │
│  │                                                                   │     │
│  │  ┌──────────────┐     ┌───────────────────────────┐               │     │
│  │  │   Routes      │     │      RagPipeline           │               │     │
│  │  │  POST /embed  │────►│  ┌─────────────────────┐  │               │     │
│  │  │  POST /analyze│     │  │  TTLCache            │  │               │     │
│  │  │  POST /extract│     │  │  (result caching)    │  │               │     │
│  │  │  POST /search │     │  ├─────────────────────┤  │               │     │
│  │  │  POST /ask    │     │  │  Map-Reduce           │  │               │     │
│  │  │  DELETE /contr│     │  │  Summarization        │  │               │     │
│  │  │  GET  /health │     │  ├─────────────────────┤  │               │     │
│  │  └──────────────┘     │  │  Embed/Extract/Analyze│  │               │     │
│  │                       │  └─────────────────────┘  │               │     │
│  │                       └──────────┬────────────────┘               │     │
│  │                                  │                                  │     │
│  │                       ┌──────────▼────────────────┐                 │     │
│  │                       │         LLMClient          │                 │     │
│  │                       │  ┌────────────────────┐   │                 │     │
│  │                       │  │  NVIDIA NIM Client   │   │  (primary)     │     │
│  │                       │  ├────────────────────┤   │                 │     │
│  │                       │  │  Ollama Client      │   │  (fallback)    │     │
│  │                       │  └────────────────────┘   │                 │     │
│  │                       │  _ProviderState tracking   │                 │     │
│  │                       └──────────────────────────┘                 │     │
│  │                       ┌──────────────────────────┐                 │     │
│  │                       │    EmbeddingService       │                 │     │
│  │                       │  (sentence-transformers)  │                 │     │
│  │                       │  all-MiniLM-L6-v2 (384d) │                 │     │
│  │                       └──────────────────────────┘                 │     │
│  │                       ┌──────────────────────────┐                 │     │
│  │                       │     VectorStore (FAISS)   │                 │     │
│  │                       │  Per-contract indexes     │                 │     │
│  │                       │  Native format + JSON md  │                 │     │
│  │                       └──────────────────────────┘                 │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Spring Boot Backend (Java 21)

**Package**: `com.grim.backend`

| Layer | Files | Responsibility |
|---|---|---|
| **Entry Point** | `BackendApplication.java` | Spring Boot main class |
| **Configuration** | `AppConfig.java` | WebClient beans for AI service HTTP calls |
| | `application.yaml` | MongoDB, upload, chunking, AI service settings |
| **Controllers** | `ContractController.java` | Upload form, list/detail/delete contracts, auto-trigger async analysis |
| | `AnalysisController.java` | Trigger analysis, view results, search, polling endpoint |
| | `DashboardController.java` | Dashboard stats, health JSON endpoint, contract status polling |
| | `HealthController.java` | Simple health check + Chrome DevTools protocol handler |
| **Services** | `ContractService.java` | Upload pipeline: validate (magic bytes) → save → extract → chunk → embed → persist |
| | `AnalysisService.java` | Orchestrate analysis: call AI → save results → local text search fallback |
| | `AiIntegrationService.java` | HTTP bridge: embed / analyze / search / ask / delete Python endpoints |
| | `AiHealthService.java` | Cached AI health checks (30s TTL) + startup check |
| | `TextExtractionService.java` | PDF (Apache PDFBox) and DOCX (Apache POI) text extraction |
| | `ChunkingService.java` | Configurable text splitting (2500 chars, 100 overlap) |
| **Models** | `Contract.java` | Main entity with processing status (10-state enum) |
| | `ContractChunk.java` | Individual text chunk with embedding state |
| | `AnalysisResult.java` | AI analysis result with risk level (LOW/MEDIUM/HIGH) |
| | `RiskReport.java` | Structured risk breakdown: penalties, termination, liability |
| **DTOs** | `UploadResponseDto`, `AnalysisResponseDto`, `SearchRequestDto` | API shapes |
| **Repositories** | `ContractRepository`, `AnalysisResultRepository` | MongoDB data access with custom queries |
| **Exceptions** | `ContractNotFoundException`, `FileProcessingException`, `GlobalExceptionHandler` | Error handling |

#### Contract Processing States

```
UPLOADED → EXTRACTING → CHUNKING → PENDING_AI → ANALYZING → COMPLETED
                                                              ↘ FAILED
```

### 2. Python AI Microservice (FastAPI)

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app factory with background startup (embedder loads async) |
| `app/config.py` | Pydantic settings — all env vars centralized |
| `app/models/schemas.py` | Pydantic models: `AskRequest/Response`, `EmbedRequest/Response`, `AnalyzeRequest/Response`, `ExtractRequest/Response`, `SearchRequest/Response`, `DeleteResponse`, `HealthResponse` |
| `app/api/routes.py` | 6 REST endpoints under `/api/ai/` |
| **Core** | |
| `app/core/rag_pipeline.py` | RAG orchestrator — embed, analyze (map-reduce), search, extract, ask, delete — with `TTLCache` |
| `app/core/llm_client.py` | Unified LLM client — NVIDIA NIM (primary) → Ollama (fallback) with `_ProviderState` health tracking |
| `app/core/nvidia_nim_client.py` | NVIDIA NIM provider using OpenAI SDK |
| `app/core/ollama_client.py` | Ollama provider |
| `app/core/embedder.py` | Thread-safe singleton `EmbeddingService` wrapping `sentence-transformers` |
| `app/core/vector_store.py` | Per-contract FAISS indexes with native persistence + JSON metadata |
| `app/core/prompts.py` | Shared prompt templates + response parsers for summarization, extraction, risk JSON |

#### LLM Failover Strategy

```
LLMClient.ask()
  → NVIDIA NIM (check reachable + API key present)
      → Success: return response
      → Failure: log warning, fall through
  → Ollama (check reachable + model loaded)
      → Success: return response
      → Failure: log error, raise exception
```

## Data Flow

### Upload & Processing Flow

1. **Upload**: User uploads PDF/DOCX via `ContractController.handleUpload()`
2. **Validation**: MIME type check + magic-byte signature validation (prevents extension spoofing)
3. **Save**: File saved to `./uploads/` with UUID prefix
4. **Extract**: `TextExtractionService` extracts raw text (PDFBox/POI)
5. **Chunk**: `ChunkingService` splits text into chunks (default: 2500 chars, 100 char overlap)
6. **Embed**: Chunks sent to Python `POST /api/ai/embed` — `EmbeddingService` generates 384-dim vectors → stored in per-contract FAISS index
7. **Persist**: Contract metadata (with chunk embedding IDs) saved to MongoDB
8. **Auto-Analyze**: Analysis auto-triggered on a dedicated 2-thread executor pool

### Analysis Flow

1. **Trigger**: User or auto-trigger calls `POST /analysis/{id}/run`
2. **Chunk Retrieval**: Contract chunks fetched from MongoDB
3. **RAG**: Python `POST /api/ai/analyze` — `RagPipeline` retrieves relevant chunks from FAISS (multi-query), runs map-reduce summarization
4. **LLM Processing**: Single LLM call for combined summary + risk JSON extraction
5. **Result Storage**: `AnalysisResult` persisted to MongoDB with risk level classification
6. **Frontend Polling**: Frontend polls `GET /api/analysis/updates` every 5s for toast notifications

### Search Flow

1. **Query**: User submits search via `POST /analysis/search`
2. **AI Search**: `AiIntegrationService.semanticSearch()` → Python `POST /api/ai/search` → FAISS similarity search
3. **Fallback**: If AI is unavailable, `AnalysisService.localTextSearch()` does term-frequency matching on raw chunks
4. **Answer Synthesis**: If results found + AI available, `POST /api/ai/ask` synthesises a natural-language answer
5. **Response**: Returns `{ query, answer, results[], count }`

## Communication Protocol

### HTTP API Between Services

- **Base URL**: `http://localhost:5000` (configurable via `app.ai.service.url`)
- **Timeouts**: 1200 seconds (20 minutes) for analysis; 5s for health checks
- **Retry Strategy**: Up to 2 retries with 1-second delay (configurable)
- **Error Handling**: `AiServiceException` with simplified error messages
- **Graceful Degradation**: All endpoints return stub responses when `app.ai.service.enabled=false`

### AI Service Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/ai/embed` | POST | Generate embeddings + store in FAISS |
| `/api/ai/analyze` | POST | Full RAG summarization + risk analysis |
| `/api/ai/extract` | POST | Extraction-first pipeline (low-resource) |
| `/api/ai/search` | POST | Semantic similarity search |
| `/api/ai/ask` | POST | Q&A answer synthesis from chunks |
| `/api/ai/contract/{id}` | DELETE | Remove FAISS vectors |
| `/api/ai/health` | GET | Service health check |

## Key Architecture Decisions

1. **Dual LLM Provider**: NVIDIA NIM for zero-setup cloud inference, Ollama fallback for air-gapped/offline use — automatic failover with no config changes
2. **Background Startup**: Python service starts in <1s; embedding model loads asynchronously (5-20s) — avoids blocking the HTTP server
3. **TTL Caching**: RAG pipeline uses `TTLCache` to avoid redundant LLM calls for repeated queries
4. **Extraction Pipeline**: New extraction-first endpoint (`/api/ai/extract`) for low-resource machines — splits, filters by cosine similarity, extracts structured JSON per chunk
5. **Magic-Byte Validation**: Prevents file extension spoofing attacks by checking PDF/DOCX file signatures
6. **Health Caching**: `AiHealthService` caches health status for 30s to avoid hammering the Python service

## Infrastructure Dependencies

- **MongoDB 6.0**: Document database (Docker Compose)
- **FAISS**: Vector similarity search per contract
- **sentence-transformers**: Embedding model (`all-MiniLM-L6-v2`)
- **NVIDIA NIM**: Cloud LLM inference (optional, primary)
- **Ollama**: Local LLM inference (optional, fallback)
- **Apache PDFBox + POI**: Document text extraction
