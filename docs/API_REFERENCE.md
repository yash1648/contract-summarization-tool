# AI Contract System - API Reference

## 📡 HTTP API Endpoints

### Backend API (Spring Boot)

#### File Upload
```
POST /upload
Content-Type: multipart/form-data

Request:
  - file: Contract file (PDF/DOCX, max 20MB)

Response (200 OK):
{
  "contractId": "string",
  "fileName": "string",
  "fileType": "string",
  "fileSizeBytes": long,
  "totalChunks": int,
  "status": "UPLOADED|PROCESSING|COMPLETED|FAILED",
  "uploadedAt": "datetime",
  "message": "string"
}

Error Response (400/500):
{
  "error": "string",
  "message": "string"
}
```

#### Get Contracts
```
GET /contracts

Response (200 OK):
[
  {
    "id": "string",
    "fileName": "string",
    "fileType": "string",
    "fileSizeBytes": long,
    "status": "string",
    "uploadedAt": "datetime",
    "processedAt": "datetime"
  }
]
```

#### Get Contract Details
```
GET /contracts/{id}

Response (200 OK):
{
  "id": "string",
  "fileName": "string",
  "fileType": "string",
  "fileSizeBytes": long,
  "status": "string",
  "extractedText": "string",
  "totalChunks": int,
  "chunks": [...],
  "createdAt": "datetime",
  "updatedAt": "datetime"
}
```

#### Delete Contract
```
DELETE /contracts/{id}

Response (200 OK):
{
  "id": "string",
  "deleted": true,
  "vectorsRemoved": int
}
```

### Python AI Service API

The Python AI service exposes REST endpoints that the Spring Boot backend calls:

#### Embed Chunks
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
```

#### Analyze Contract (RAG)
```
POST /api/ai/analyze
Content-Type: application/json

Request:
{
  "contractId": "string",
  "chunkTexts": ["chunk1 text", "chunk2 text", ...]
}

Response (200 OK):
{
  "summary": "structured summary text",
  "riskScore": 4.2,
  "penaltyClauses": ["clause 1", "clause 2"],
  "terminationRisks": ["risk 1", "risk 2"],
  "liabilityIssues": ["issue 1", "issue 2"],
  "otherFlags": ["flag 1", "flag 2"],
  "chunksUsed": 7
}
```

#### Semantic Search
```
POST /api/ai/search
Content-Type: application/json

Request:
{
  "contractId": "string",  // optional
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
```

#### Delete Contract Vectors
```
DELETE /api/ai/contract/{id}

Response (200 OK):
{
  "deleted": true,
  "contractId": "string",
  "vectorsRemoved": 12
}
```

#### Health Check
```
GET /api/ai/health

Response (200 OK):
{
  "status": "ok|degraded",
  "embeddingModel": "all-MiniLM-L6-v2",
  "ollamaModel": "gemma3:4b",
  "ollamaReachable": true,
  "totalIndexes": 5
}
```

## 📋 Request/Response Examples

### Example: Upload and Analyze a Contract

**1. Upload Contract**
```bash
curl -X POST http://localhost:6969/upload \
  -F "file=@contract.pdf" \
  -F "name=my_contract"
```

**2. Analyze Contract**
```bash
curl -X POST http://localhost:6969/contracts/{id}/analyze
```

**3. Search Contract**
```bash
curl -X POST http://localhost:6969/search \
  -H "Content-Type: application/json" \
  -d '{"query": "termination clauses", "topK": 5}'
```

## ⚙️ Configuration Reference

### Backend Configuration (application.yaml)

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
    dir: /path/to/uploads
    allowed-types: application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document

  chunking:
    size: 2500      # characters per chunk
    overlap: 100    # characters of overlap between chunks

  ai:
    service:
      url: http://localhost:5000
      enabled: true
      timeout-seconds: 1200
      max-retries: 2
      retry-delay-ms: 1000

server:
  port: 6969
```

### AI Service Configuration (.env)

```env
HOST=0.0.0.0
PORT=5000
LOG_LEVEL=INFO

EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32

FAISS_INDEX_DIR=./data/faiss_indexes

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_MAX_TOKENS=1024
OLLAMA_TEMPERATURE=0.1

RAG_TOP_K=7
RAG_MIN_SCORE=0.30
```

## 🔑 API Key Endpoints Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/upload` | POST | No | Upload contract file |
| `/contracts` | GET | No | List all contracts |
| `/contracts/{id}` | GET | No | Get contract details |
| `/contracts/{id}` | DELETE | No | Delete contract |
| `/api/ai/embed` | POST | Yes | Embed chunks (internal) |
| `/api/ai/analyze` | POST | Yes | Analyze contract (internal) |
| `/api/ai/search` | POST | Yes | Search contracts (internal) |
| `/api/ai/health` | GET | No | Health check |

## ⚠️ Error Codes

- `400 Bad Request`: Invalid input, missing required fields
- `404 Not Found`: Contract not found
- `413 Payload Too Large`: File exceeds 20MB limit
- `500 Internal Server Error`: Backend or AI service errors
- `503 Service Unavailable`: AI service not reachable (graceful degradation)