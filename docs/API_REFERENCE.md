# AI Contract System - API Reference

## Backend API (Spring Boot — port 6969)

### Dashboard

#### Home / Dashboard
```
GET /
  → Redirects to /dashboard

GET /dashboard
  Response (200 OK): Thymeleaf HTML page with:
    - totalContracts, completedContracts, pendingContracts, failedContracts
    - highRiskContracts
    - recentContracts (last 5)
    - recentAnalyses (last 5)
    - aiStatus (live AI health, cached 30s)
```

### Contract Upload & Management

#### Upload a Contract
```
POST /contracts/upload
Content-Type: multipart/form-data

Request:
  - file: Contract file (PDF/DOCX, max 20MB)

Response: Redirect to /contracts/{id} on success

Notes:
  - Validates file type + magic bytes (PDF/DOCX signatures)
  - Auto-triggers async analysis on a background thread pool
```

#### List Contracts
```
GET /contracts

Response (200 OK): Thymeleaf HTML page
  Backing endpoint returns: List of Contract objects
  - id, fileName, fileType, fileSize, status, uploadedAt, etc.
```

#### Contract Detail
```
GET /contracts/{id}

Response (200 OK): Thymeleaf HTML page
  - Full contract details with chunk list and embedding status
```

#### Delete Contract
```
POST /contracts/{id}/delete

Response: Redirect to /contracts
  - Removes from MongoDB + deletes FAISS vectors + removes file from disk
```

### Analysis

#### Trigger Analysis
```
POST /analysis/{contractId}/run

Response: Redirect to /analysis/{contractId}/results

Notes:
  - Runs full RAG pipeline: FAISS retrieval → LLM summarization → risk extraction
  - Overwrites any previous analysis result
  - Contract status transitions: PENDING_AI → ANALYZING → COMPLETED / FAILED
```

#### View Analysis Results
```
GET /analysis/{contractId}/results

Response (200 OK): Thymeleaf HTML page
  - Summary, risk score, risk level badge, penalty clauses,
    termination risks, liability issues, other flags
```

#### List All Analyses
```
GET /analysis

Response (200 OK): Thymeleaf HTML page
  - All analysis results sorted by analyzedAt descending
```

#### Semantic Search
```
POST /analysis/search
Content-Type: application/json

Request:
{
  "contractId": "string",     // optional — null = search all
  "query": "termination clauses",
  "topK": 5
}

Response (200 OK):
{
  "query": "termination clauses",
  "answer": "AI-synthesised answer...",    // null if AI disabled
  "results": [
    {
      "chunkIndex": 2,
      "text": "chunk text...",
      "score": 0.91,
      "contractId": "..."
    }
  ],
  "count": 5
}

Notes:
  - Uses FAISS semantic search (AI) with local term-matching fallback
  - Answer synthesised via POST /api/ai/ask when AI is available
```

#### Analysis Polling (Frontend Toasts)
```
GET /api/analysis/updates

Response (200 OK):
[
  {
    "contractId": "...",
    "fileName": "...",
    "status": "COMPLETED|FAILED",
    "processedAt": "2026-06-02T12:00:00"
  }
]

Notes:
  - Returns contracts that completed/failed in the last 60 seconds
  - Called by frontend every 5s for toast notifications
```

### Contract Status Polling

#### Contract Status
```
GET /api/contracts/{id}/status

Response (200 OK):
{
  "id": "...",
  "status": "UPLOADED|EXTRACTING|CHUNKING|PENDING_AI|ANALYZING|COMPLETED|FAILED",
  "analysisResultId": "..." | null,
  "fileName": "..."
}
```

### Health

#### Simple Health Check
```
GET /health

Response (200 OK): "OK"
```

#### JSON Health Endpoint
```
GET /api/health

Response (200 OK):
{
  "springBoot": "UP",
  "aiService": "UP|DOWN",
  "ollamaReachable": true,
  "ollamaModel": "gemma3:4b",
  "embeddingModel": "all-MiniLM-L6-v2",
  "totalFaissIndexes": 5,
  "errorMessage": null | "error string"
}
```

### Frontend Pages

| Route | Page | Description |
|---|---|---|
| `/` | Redirect | → `/dashboard` |
| `/dashboard` | `index.html` | Main dashboard with stats + AI status |
| `/contracts` | `contracts.html` | Contract list |
| `/contracts/upload` | `upload.html` | Upload form |
| `/contracts/{id}` | `contract-detail.html` | Contract detail + chunks |
| `/analysis` | `analysis-list.html` | All analysis results |
| `/analysis/{id}/results` | `analysis.html` | Single analysis result |
| `/search` | `search.html` | Search page |

---

## Python AI Service API (FastAPI — port 5000)

Base URL: `http://localhost:5000/api/ai`

### Embed Chunks
```
POST /api/ai/embed
Content-Type: application/json

Request:
{
  "contractId": "string",
  "chunks": [
    {"index": 0, "text": "chunk text"}
  ]
}

Response (200 OK):
{
  "contractId": "string",
  "embeddingIds": ["uuid1", "uuid2", ...],
  "chunksEmbedded": 5
}

Errors: 400 if chunks empty, 500 on processing error
```

### Analyze Contract (RAG)
```
POST /api/ai/analyze
Content-Type: application/json

Request:
{
  "contractId": "string",
  "chunkTexts": ["chunk 1 text", "chunk 2 text", ...]
}

Response (200 OK):
{
  "summary": "structured summary text...",
  "riskScore": 4.2,
  "penaltyClauses": ["clause 1", "clause 2"],
  "terminationRisks": ["risk 1", "risk 2"],
  "liabilityIssues": ["issue 1", "issue 2"],
  "otherFlags": ["flag 1", "flag 2"],
  "chunksUsed": 7
}

Errors: 400 if chunkTexts empty, 500 on processing error

Notes:
  - Retrieves relevant chunks from FAISS using multi-query strategy
  - Runs map-reduce summarization: parallel summarization → single combined output
  - Single LLM call for both summary + risk JSON extraction
  - Falls back to raw chunkTexts if FAISS index is missing
```

### Extract Contract (Extraction-First Pipeline)
```
POST /api/ai/extract
Content-Type: application/json

Request:
{
  "contractId": "string",
  "chunkTexts": ["chunk 1 text", "chunk 2 text", ...]
}

Response (200 OK):
{
  "contractId": "string",
  "chunks": [
    {
      "chunk_id": 0,
      "data": {
        "parties": ["Party A", "Party B"],
        "obligations": ["obligation 1"],
        "payment_terms": ["net 30"],
        "dates": ["2026-01-01"],
        "penalties": ["late fee 5%"],
        "termination": ["30 day notice"]
      }
    }
  ],
  "totalChunks": 12,
  "processingTimeMs": 1234
}

Notes:
  - Lightweight extraction pipeline for low-resource machines
  - Splits chunks into sentences → filters by cosine similarity → extracts structured JSON
  - Per-chunk structured data for Java to merge client-side
```

### Semantic Search
```
POST /api/ai/search
Content-Type: application/json

Request:
{
  "contractId": "string",   // optional
  "query": "search query",
  "topK": 5
}

Response (200 OK):
{
  "results": [
    {
      "chunkIndex": 2,
      "text": "chunk text",
      "score": 0.91,
      "contractId": "string"
    }
  ],
  "query": "search query",
  "count": 3
}

Notes:
  - Encodes query and performs FAISS approximate nearest-neighbour search
  - Scoped to one contract if contractId provided; searches all otherwise
```

### Q&A — Ask a Question
```
POST /api/ai/ask
Content-Type: application/json

Request:
{
  "contractId": "string",   // optional
  "query": "What are the payment terms?",
  "chunks": ["chunk text 1", "chunk text 2", ...]
}

Response (200 OK):
{
  "answer": "The payment terms require...",
  "chunksUsed": 5
}

Errors: 400 if chunks empty
```

### Delete Contract Vectors
```
DELETE /api/ai/contract/{contractId}

Response (200 OK):
{
  "deleted": true,
  "contractId": "string",
  "vectorsRemoved": 12
}
```

### Health Check
```
GET /api/ai/health

Response (200 OK):
{
  "status": "ok|degraded|starting",
  "embeddingModel": "all-MiniLM-L6-v2",
  "ollamaModel": "gemma3:4b",
  "ollamaReachable": true,
  "totalIndexes": 5
}

Notes:
  - status = "starting" during first 5-20s (embedding model loading in background)
  - status = "degraded" when LLM not reachable but embedder is loaded
```

---

## Complete Endpoint Reference

### Backend (port 6969)

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/` | No | Redirect to /dashboard |
| GET | `/dashboard` | No | Dashboard page with stats |
| GET | `/contracts` | No | List all contracts |
| GET | `/contracts/upload` | No | Upload form |
| POST | `/contracts/upload` | No | Upload contract file |
| GET | `/contracts/{id}` | No | Contract detail |
| POST | `/contracts/{id}/delete` | No | Delete contract |
| POST | `/analysis/{contractId}/run` | No | Trigger analysis |
| GET | `/analysis/{contractId}/results` | No | Analysis results |
| GET | `/analysis` | No | All analysis results |
| POST | `/analysis/search` | No | Semantic search |
| GET | `/api/analysis/updates` | No | Polling for toasts |
| GET | `/api/contracts/{id}/status` | No | Contract processing status |
| GET | `/search` | No | Search page |
| GET | `/health` | No | Simple health check |
| GET | `/api/health` | No | JSON health status |

### Python AI Service (port 5000)

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/ai/embed` | Embed chunks in FAISS |
| POST | `/api/ai/analyze` | RAG summarization + risk |
| POST | `/api/ai/extract` | Extraction-first pipeline |
| POST | `/api/ai/search` | Semantic search |
| POST | `/api/ai/ask` | Q&A from chunk texts |
| DELETE | `/api/ai/contract/{id}` | Delete vectors |
| GET | `/api/ai/health` | Health check |
| GET | `/` | Service info + docs link |

## Error Codes

| Code | Meaning |
|------|---------|
| `400 Bad Request` | Invalid input, empty chunks, missing file |
| `404 Not Found` | Contract or analysis not found |
| `413 Payload Too Large` | File exceeds 20MB limit |
| `500 Internal Server Error` | Backend or AI service processing error |
| `503 Service Unavailable` | AI service not reachable (graceful degradation) |

## Contract Processing Status Values

| Status | Meaning |
|--------|---------|
| `UPLOADED` | File uploaded, not yet processed |
| `EXTRACTING` | Text extraction in progress |
| `CHUNKING` | Text splitting into chunks |
| `PENDING_AI` | Awaiting AI embedding/analysis |
| `ANALYZING` | RAG analysis in progress |
| `COMPLETED` | All processing done |
| `FAILED` | Processing failed |

## Configuration Reference

### Backend (`application.yaml`)
```yaml
spring:
  application:
    name: ai-assistant-backend
  mongodb:
    uri: mongodb://admin:password@localhost:27017/ai_assistant_db?authSource=admin
  servlet:
    multipart:
      max-file-size: 20MB
      max-request-size: 20MB

app:
  upload:
    dir: ./uploads
    allowed-types: application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document
  chunking:
    size: 2500
    overlap: 100
  ai:
    service:
      url: http://localhost:5000
      enabled: true
      timeout-seconds: 1200
      max-retries: 2
      retry-delay-ms: 1000
      health-timeout-seconds: 5

server:
  port: 6969
```

### AI Service (`.env`)
```env
HOST=0.0.0.0
PORT=5000
LOG_LEVEL=INFO

EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32

FAISS_INDEX_DIR=./data/faiss_indexes

# LLM — Primary
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=meta/llama3-70b-instruct
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# LLM — Fallback
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_MAX_TOKENS=1024
OLLAMA_TEMPERATURE=0.1

# RAG
RAG_TOP_K=7
RAG_MIN_SCORE=0.30
```
