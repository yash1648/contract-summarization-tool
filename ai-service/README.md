# AI Contract Summarization Service

Python microservice providing the full RAG AI pipeline for the Spring Boot backend.

```
Stack:  FastAPI + sentence-transformers + FAISS + Ollama (llama3)
Port:   5000
```

---

## Architecture

```
Spring Boot (port 8080)
        │
        │  HTTP/JSON  (4 endpoints)
        ▼
FastAPI AI Service (port 5000)
        │
        ├── EmbeddingService  ←  sentence-transformers/all-MiniLM-L6-v2
        ├── VectorStore       ←  FAISS IndexFlatIP (per-contract, persisted to disk)
        ├── OllamaClient      ←  Ollama llama3 (2 LLM passes per analysis)
        └── RagPipeline       ←  orchestrates the above three
```

### RAG Flow for `/api/ai/analyze`

```
chunkTexts (from Spring Boot)
        │
        ├─ SUMMARY pass:  encode 3 generic queries → FAISS top-k → LLM summary
        └─ RISK    pass:  encode 5 risk queries    → FAISS top-k → LLM risk JSON
                                                              │
                                                              ▼
                                              { summary, riskScore, clauses… }
```

---

## Quickstart

### Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python     | ≥ 3.11  | |
| Ollama     | latest  | https://ollama.com/download |
| llama3 model | — | `ollama pull llama3` |

### Setup & Run

```bash
# 1. Clone / navigate to this directory
cd ai-service/

# 2. One-shot setup (creates venv, installs deps, pulls llama3, starts server)
chmod +x scripts/setup.sh
./scripts/setup.sh

# OR manually:
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ollama serve &                     # if not already running
ollama pull llama3
uvicorn main:app --port 5000 --reload
```

### Enable in Spring Boot

Edit `application.properties`:

```properties
app.ai.service.url=http://localhost:5000
app.ai.service.enabled=true
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ai/embed` | Embed contract chunks into FAISS |
| `POST` | `/api/ai/analyze` | RAG summarization + risk analysis |
| `POST` | `/api/ai/search` | Semantic similarity search |
| `DELETE` | `/api/ai/contract/{id}` | Delete contract vectors |
| `GET` | `/api/ai/health` | Health check |

Interactive docs: **http://localhost:5000/docs**

### POST `/api/ai/embed`

```json
// Request
{
  "contractId": "mongo-id-abc",
  "chunks": [
    { "index": 0, "text": "This Agreement is entered into by..." },
    { "index": 1, "text": "Payment of USD 5000 shall be made..." }
  ]
}

// Response
{
  "contractId": "mongo-id-abc",
  "embeddingIds": ["550e8400-...", "6ba7b810-..."],
  "chunksEmbedded": 2
}
```

### POST `/api/ai/analyze`

```json
// Request
{
  "contractId": "mongo-id-abc",
  "chunkTexts": ["full chunk text 1", "full chunk text 2", ...]
}

// Response
{
  "summary": "1. Parties: Acme Corp and Beta Ltd\n2. Purpose: ...",
  "riskScore": 4.2,
  "penaltyClauses": ["10% penalty on late delivery"],
  "terminationRisks": ["Immediate termination without cause"],
  "liabilityIssues": ["Unlimited liability clause"],
  "otherFlags": [],
  "chunksUsed": 7
}
```

### POST `/api/ai/search`

```json
// Request
{ "contractId": "mongo-id-abc", "query": "payment terms", "topK": 5 }

// Response
{
  "results": [
    { "chunkIndex": 1, "text": "Payment of...", "score": 0.91, "contractId": "..." }
  ],
  "query": "payment terms",
  "count": 1
}
```

---

## Configuration

Edit `.env`:

```env
OLLAMA_MODEL=llama3          # or mistral, phi3, gemma2 etc.
OLLAMA_TEMPERATURE=0.1       # low = more deterministic
RAG_TOP_K=7                  # chunks retrieved per query
RAG_MIN_SCORE=0.30           # minimum similarity threshold
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

---

## Project Structure

```
ai-service/
├── main.py                     # FastAPI app entry point
├── requirements.txt
├── .env                        # configuration
├── app/
│   ├── config.py               # Pydantic settings
│   ├── api/
│   │   └── routes.py           # All 4+1 API endpoints
│   ├── core/
│   │   ├── embedder.py         # sentence-transformers singleton
│   │   ├── vector_store.py     # FAISS index management
│   │   ├── ollama_client.py    # Ollama LLM client + prompts
│   │   └── rag_pipeline.py     # Full RAG orchestration
│   └── models/
│       └── schemas.py          # Pydantic request/response models
├── tests/
│   ├── test_api.py             # API endpoint tests
│   └── test_chunking.py        # VectorStore unit tests
├── scripts/
│   └── setup.sh                # One-shot setup script
└── data/
    └── faiss_indexes/          # Persisted FAISS indexes (auto-created)
```

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Tests mock the embedder and Ollama client — no GPU or running LLM required.

---

## Changing the LLM Model

```bash
# Use mistral instead of llama3
ollama pull mistral
```

Then update `.env`:
```env
OLLAMA_MODEL=mistral
```

Other good options: `phi3`, `gemma2`, `qwen2`, `deepseek-r1`
