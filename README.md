# AI Contract Summarization System

## Overview

A production-ready web application that leverages Retrieval-Augmented Generation (RAG) and Natural Language Processing (NLP) to analyze and summarize legal contracts. The system combines a Spring Boot backend with a Python AI microservice to provide intelligent contract analysis, risk detection, and semantic search capabilities.

## Features

- **Document Upload**: Support for PDF and DOCX files (up to 20MB) with magic-byte validation
- **Intelligent Analysis**: RAG-based summarization and risk detection
- **Semantic Search**: Vector similarity search across contract content with AI-answered results
- **Risk Detection**: Automated identification of penalty clauses, termination risks, and liability issues
- **Map-Reduce Summarization**: Efficient handling of large documents through multi-level summarization
- **Dual LLM Provider**: NVIDIA NIM (primary) + Ollama (fallback) with automatic failover
- **Fault Tolerance**: Graceful degradation when AI services are unavailable
- **Production-Ready**: Comprehensive logging, error handling, health monitoring, and polling

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Thymeleaf Frontend                         │
└──────┬──────────────────────────────────────────────────────┘
       │
       HTTP Requests/Responses
       │
┌──────▼──────────────────────────────────────────────────────┐
│              Spring Boot Backend (com.grim.backend)          │
│  ┌──────────────┐  ┌──────────────────────────────────┐     │
│  │ Controllers  │  │           Services               │     │
│  │  ┌─────────┐ │  │  ┌─────────────────────────┐     │     │
│  │  │Contract │ │  │  │ ContractService         │     │     │
│  │  ├─────────┤ │  │  ├─────────────────────────┤     │     │
│  │  │Analysis │ │  │  │ AnalysisService         │     │     │
│  │  ├─────────┤ │  │  ├─────────────────────────┤     │     │
│  │  │Dashboard│ │  │  │ AiIntegrationService    │─────┼──┐  │
│  │  ├─────────┤ │  │  ├─────────────────────────┤     │  │  │
│  │  │Health   │ │  │  │ AiHealthService         │     │  │  │
│  │  └─────────┘ │  │  ├─────────────────────────┤     │  │  │
│  │              │  │  │ TextExtractionService    │     │  │  │
│  │  ┌─────────┐ │  │  ├─────────────────────────┤     │  │  │
│  │  │Models   │◄─┘  │  │ ChunkingService         │     │  │  │
│  │  ├─────────┤│     │  └─────────────────────────┘     │  │  │
│  │  │DTOs     ││     └──────────────────────────────────┘  │  │
│  │  └─────────┘│                                            │  │
│  │  ┌─────────┐│  ┌──────────────────────────────┐          │  │
│  │  │Repo     │◄──│ MongoDB (contracts + results)│          │  │
│  │  └─────────┘│  └──────────────────────────────┘          │  │
│  │  ┌─────────┐│                                            │  │
│  │  │Exception││                                            │  │
│  │  └─────────┘│                                            │  │
│  └─────────────┘                                            │  │
└─────────────────────────────────────────────────────────────┘  │
                           │                                      │
                  REST API Calls (HTTP)                           │
                           │                                      │
┌──────────────────────────▼──────────────────────────────────────┘
│                 Python AI Microservice                              │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  FastAPI Application (AI Contract Summarizer)           │       │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │       │
│  │  │ Routes   │─►│  RagPipeline │─►│  LLMClient       │  │       │
│  │  │ POST     │  │  ┌─────────┐ │  │  ┌─────────────┐ │  │       │
│  │  │  /embed  │  │  │TTLCache │ │  │  │NVIDIA NIM   │ │  │       │
│  │  │  /analyze│  │  └─────────┘ │  │  │  (primary)  │ │  │       │
│  │  │  /extract│  │              │  │  ├─────────────┤ │  │       │
│  │  │  /search │  │  ┌─────────┐ │  │  │Ollama       │ │  │       │
│  │  │  /ask    │  │  │VectorSt.│ │  │  │  (fallback) │ │  │       │
│  │  │  /health │  │  │ (FAISS) │ │  │  └─────────────┘ │  │       │
│  │  │ DELETE   │  │  └─────────┘ │  └──────────────────┘  │       │
│  │  │  /contract│  │  ┌─────────┐│  ┌──────────────────┐  │       │
│  │  └──────────┘  │  │Embedder ││  │  EmbeddingService │  │       │
│  │                │  │(Prompts)││  │  (MiniLM-L6-v2)   │  │       │
│  │                │  └─────────┘│  └──────────────────┘  │       │
│  │                └──────────────┘                       │       │
│  └─────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────┘
```

### Core Components

**Backend (Spring Boot) — `com.grim.backend`**
- **Controllers**: Handle HTTP requests — `ContractController`, `AnalysisController`, `DashboardController`, `HealthController`
- **Services**: Business logic — `ContractService`, `AnalysisService`, `AiIntegrationService`, `AiHealthService`, `TextExtractionService`, `ChunkingService`
- **Models**: JPA entities for MongoDB — `Contract`, `ContractChunk`, `AnalysisResult`, `RiskReport`
- **Repositories**: MongoDB data access — `ContractRepository`, `AnalysisResultRepository`
- **DTOs**: Data transfer objects — `UploadResponseDto`, `AnalysisResponseDto`, `SearchRequestDto`
- **Exception Handling**: `ContractNotFoundException`, `FileProcessingException`, `GlobalExceptionHandler`

**AI Microservice (FastAPI)**
- **Routes**: REST endpoints for embedding, analysis, search, extract, ask, delete, health
- **RAG Pipeline**: Map-reduce summarization with `TTLCache` support
- **LLMClient**: Unified client with NVIDIA NIM primary + Ollama fallback + provider health tracking
- **Embedder**: Sentence-transformer embeddings (`all-MiniLM-L6-v2`)
- **Vector Store**: FAISS per-contract indexes with JSON metadata
- **Prompts**: Shared prompt templates and response parsers

## Quick Start

### Prerequisites

- Java 21+
- Maven 3.8+
- Python 3.11+
- Docker (optional, for MongoDB)
- Ollama (for local LLM fallback) **or** NVIDIA API key (for cloud inference)

### Backend Setup

```bash
cd backend
mvn clean package
mvn spring-boot:run
```

The backend will start on `http://localhost:6969`

### Python AI Service Setup

```bash
cd ai-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env as needed (add NVIDIA_API_KEY for cloud LLM, or rely on Ollama)

# Download embedding model (auto-downloaded on first run)
# For LLM, either set NVIDIA_API_KEY or run Ollama:
ollama pull gemma3:4b

# Start the AI service
uvicorn main:app --host 0.0.0.0 --port 5000
```

### Docker Deployment

```bash
# Start all services (MongoDB only — backend & AI run natively)
docker-compose up -d

# Stop all services
docker-compose down
```

## Configuration

### Backend Configuration (`application.yaml`)

```yaml
spring:
  application:
    name: ai-assistant-backend
  mongodb:
    uri: mongodb://admin:password@localhost:27017/ai_assistant_db?authSource=admin

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
```

### AI Service Configuration (`.env`)

```env
# LLM — set at least one:
NVIDIA_API_KEY=nvapi-...         # Primary LLM provider
OLLAMA_BASE_URL=http://localhost:11434  # Fallback
OLLAMA_MODEL=gemma3:4b

# Embedding
EMBEDDING_MODEL=all-MiniLM-L6-v2

# RAG
RAG_TOP_K=7
RAG_MIN_SCORE=0.30
```

## API Usage

### Upload a Contract

```bash
curl -X POST http://localhost:6969/contracts/upload \
  -F "file=@contract.pdf"
```

### Analyze a Contract

```bash
# Upload first to get contract ID, then:
curl -X POST http://localhost:6969/analysis/{id}/run
```

### Search Contracts

```bash
curl -X POST http://localhost:6969/analysis/search \
  -H "Content-Type: application/json" \
  -d '{"contractId": "...", "query": "termination clauses", "topK": 5}'
```

## Testing

```bash
# Backend tests
mvn test

# API integration tests
cd ai-service && pytest tests/
```

## Project Structure

```
ai-contract-system/
├── backend/                    # Spring Boot application (Java 21)
│   ├── src/
│   │   ├── main/java/com/grim/backend/
│   │   │   ├── config/           # AppConfig (WebClient beans)
│   │   │   ├── controller/       # ContractController, AnalysisController, etc.
│   │   │   ├── service/          # ContractService, AiIntegrationService, etc.
│   │   │   ├── model/            # Contract, AnalysisResult, RiskReport, ContractChunk
│   │   │   ├── dto/              # UploadResponseDto, AnalysisResponseDto, SearchRequestDto
│   │   │   ├── repository/       # ContractRepository, AnalysisResultRepository
│   │   │   ├── exception/        # Custom exceptions + GlobalExceptionHandler
│   │   │   └── BackendApplication.java
│   │   ├── main/resources/
│   │   │   ├── application.yaml
│   │   │   └── templates/        # Thymeleaf pages (index, upload, contracts, analysis, search)
│   │   └── test/
│   └── pom.xml
├── ai-service/                 # Python AI microservice (FastAPI)
│   ├── app/
│   │   ├── api/routes.py        # REST API endpoints
│   │   ├── core/
│   │   │   ├── rag_pipeline.py  # RAG orchestration (map-reduce, caching)
│   │   │   ├── llm_client.py    # Unified LLM client (NVIDIA → Ollama failover)
│   │   │   ├── nvidia_nim_client.py  # NVIDIA NIM provider
│   │   │   ├── ollama_client.py      # Ollama provider
│   │   │   ├── embedder.py      # Sentence-transformer embeddings
│   │   │   ├── vector_store.py  # FAISS per-contract indexes
│   │   │   └── prompts.py       # Prompt templates + response parsers
│   │   ├── models/schemas.py    # Pydantic request/response models
│   │   └── config.py            # Pydantic settings
│   ├── main.py                  # FastAPI entry point
│   ├── tests/
│   │   ├── test_api.py
│   │   └── test_chunking.py
│   └── requirements.txt
├── docs/                       # Project documentation
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   ├── GETTING_STARTED.md
│   ├── DEVELOPMENT.md
│   ├── SRS.md
│   └── Diagrams/
├── contract_sample/            # Sample contracts for testing
├── graphify-out/               # Knowledge graph (graphify)
├── uploads/                    # Runtime: uploaded contract files
├── mongo-data/                 # Runtime: MongoDB data volume
├── docker-compose.yml          # MongoDB container
├── .opencode/                  # OpenCode CLI config + plugins
└── AGENTS.md                   # AI assistant instructions (graphify)
```

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [Getting Started](docs/GETTING_STARTED.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [SRS](docs/SRS.md)

## Key Technical Details

1. **Dual LLM Provider**: NVIDIA NIM (cloud, primary) → Ollama (local, fallback) — automatic failover
2. **Map-Reduce Summarization**: Parallel chunk summarization → single combined summary + risk JSON
3. **Vector Similarity Search**: FAISS per-contract indexes with semantic search and AI answer synthesis
4. **TTL Caching**: RAG results cached with `TTLCache` to avoid redundant LLM calls
5. **Magic-Byte Validation**: Prevents spoofed file extensions by validating PDF/DOCX signatures
6. **Async Analysis**: Upload auto-triggers analysis on a dedicated thread pool
7. **Health Polling**: Frontend polls `/api/analysis/updates` for toast notifications on completion
8. **Fault Tolerance**: Graceful degradation when AI services unavailable (local text search fallback)
