# AI Contract Summarization System

> Intelligent contract analysis using Retrieval-Augmented Generation (RAG) with Spring Boot and FastAPI

## 📊 Overview

A production-ready web application that leverages Retrieval-Augmented Generation (RAG) and Natural Language Processing (NLP) to analyze and summarize legal contracts. The system combines a Spring Boot backend with a Python AI microservice to provide intelligent contract analysis, risk detection, and semantic search capabilities.

## 🚀 Features

- **Document Upload**: Support for PDF and DOCX files (up to 20MB)
- **Intelligent Analysis**: RAG-based summarization and risk detection
- **Semantic Search**: Vector similarity search across contract content
- **Risk Detection**: Automated identification of penalty clauses, termination risks, and liability issues
- **Map-Reduce Summarization**: Efficient handling of large documents through multi-level summarization
- **Fault Tolerance**: Graceful degradation when AI services are unavailable
- **Production-Ready**: Comprehensive logging, error handling, and monitoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Thymeleaf)                 │
└───────────────┬─────────────────────────────────────────┘
                │
       HTTP Requests/Responses
                │
┌───────────────▼────────────────────┐
│          Spring Boot Backend         │
│  ┌─────────────┐    ┌─────────────┐  │
│  │ Controllers │◄───┤    Services  │  │
│  └─────────────┘    │  ┌─────────┐  │  │
│                     │  │ AI      │◄──┘───┐
│  ┌─────────────┐    │  │ Client  │       │
│  │   Models    │◄───┘  └─────────┘       │
│  └─────────────┘    ┌─────────────────┐  │
│                     │ Repositories      │◄────┘
│  ┌─────────────┐    │  ┌─────────────┐  │
│  │   DTOs      │◄───┘  └─────────────┘  │
│  └─────────────┘       ┌─────────────┐  │
│                          │ Exceptions  │  │
│  ┌─────────────┐        └─────────────┘  │
│  │ Templates   │
│  └─────────────┘
└───────────────────────┬───────────────────────┘
                        │
               REST API Calls (HTTP)
                        │
┌───────────────────────▼────────────────────┐
│        Python AI Microservice                 │
│  ┌─────────────────────────────────────┐    │
│  │  FastAPI Application                │    │
│  │  ┌─────────────┐      ┌─────────┐   │    │
│  │  │  Routes     │─────►│  RAG     │───┘    │
│  │  └─────────────┘      │ Pipeline  │        │
└─────────────────────────────────────┘        │
```

### Core Components

**Backend (Spring Boot)**
- **Controllers**: Handle HTTP requests for uploads, analysis, and search (ContractController, AnalysisController, DashboardController)
- **Services**: Business logic orchestration (ContractService, AiIntegrationService, AnalysisService, ChunkingService, TextExtractionService, AiHealthService)
- **Models**: MongoDB entities (Contract, AnalysisResult, RiskReport, ContractChunk)
- **Repositories**: MongoDB data access (ContractRepository, AnalysisResultRepository)
- **DTOs**: Data transfer objects for API communication (UploadResponseDto, AnalysisResponseDto, SearchRequestDto)
- **Exception Handling**: GlobalExceptionHandler, custom exceptions
- **Configuration**: AppConfig (WebClient), application.yaml settings

**AI Microservice (FastAPI on port 5000)**
- **Routes**: REST endpoints for embedding, analysis, search, health checks, and delete operations
- **RAG Pipeline**: Orchestrates the complete analysis workflow
- **Embedder**: Sentence-transformers with all-MiniLM-L6-v2 model
- **Vector Store**: FAISS similarity search with per-contract indexes
- **Ollama Client**: LLM integration for summarization and risk analysis
- **Models**: Pydantic schemas for request/response validation

### Data Flow
1. User uploads PDF/DOCX contract via Spring Boot controller
2. Backend extracts text and splits into chunks (2500 chars with 100 overlap)
3. Chunks are sent to AI service for embedding into FAISS vector store
4. When analysis is requested, RAG pipeline performs:
   - Summary pass: Generic queries → FAISS search → LLM summarization
   - Risk pass: Risk-specific queries → FAISS search → LLM risk analysis
5. Results stored in MongoDB and returned to user

### API Endpoints

**Contract Management**
- `POST /upload` - Upload a contract file
- `GET /contracts` - List all contracts with status
- `GET /contracts/{id}` - View contract details and analysis status
- `POST /contracts/{id}/delete` - Delete a contract

**Analysis**
- `POST /analysis/{contractId}/run` - Trigger AI analysis
- `GET /analysis/{contractId}/results` - View analysis results
- `GET /analysis` - List all analysis results

**Semantic Search**
- `POST /analysis/search` - Semantic similarity search (JSON body)

**Health**
- `GET /api/ai/health` - AI service health check

**Direct API Access** (Python AI Service)
- `POST /api/ai/embed` - Embed contract chunks
- `POST /api/ai/analyze` - RAG summarization + risk analysis
- `POST /api/ai/search` - Semantic similarity search
- `DELETE /api/ai/contract/{id}` - Delete contract vectors
- `GET /api/ai/health` - Health check

## 📖 Quick Start

### Prerequisites

- Java 21+
- Maven 3.8+
- Python 3.11+
- Docker (optional, for MongoDB)
- Ollama (for local LLM)

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
./scripts/setup.sh
```

OR manual setup:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama serve &
ollama pull llama3
ollama pull all-MiniLM-L6-v2
uvicorn main:app --host 0.0.0.0 --port 5000
```

### Docker Deployment

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down
```

## 🔧 Configuration

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
```

### AI Service Configuration (`.env`)

```env
OLLAMA_MODEL=llama3
OLLAMA_TEMPERATURE=0.1
RAG_TOP_K=7
RAG_MIN_SCORE=0.30
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## 🧪 Testing

```bash
# Backend tests
mvn test

# API integration tests
pytest tests/
```

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [Getting Started](docs/GETTING_STARTED.md)

## 📈 Key Features

1. **RAG Pipeline**: Retrieval-Augmented Generation for context-aware analysis
2. **Map-Reduce Summarization**: Efficient large document processing
3. **Vector Similarity Search**: Semantic search using FAISS embeddings
4. **Fault Tolerance**: Graceful degradation when AI services unavailable
5. **Production-Ready**: Comprehensive logging, monitoring, and error handling

## 🔄 Development Workflow

1. Make changes to Java code in `backend/src/main/java/`
2. Make changes to Python code in `ai-service/app/`
3. Run tests: `mvn test` (Java) and `pytest tests/` (Python)
4. Build: `mvn clean package`
5. Deploy: `docker-compose up -d`

## 📄 License

See LICENSE file for details.