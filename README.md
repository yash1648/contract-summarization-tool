# AI Contract Summarization System

[![Java CI](https://github.com/yourorg/ai-contract-system/actions/workflows/java.yml/badge.svg)](https://github.com/yourorg/ai-contract-system/actions/workflows/java.yml)
[![Python CI](https://github.com/yourorg/ai-contract-system/actions/workflows/python.yml/badge.svg)](https://github.com/yourorg/ai-contract-system/actions/workflows/python.yml)

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
│  └─────────────────────────────────────┘        │
└──────────────────────────────────────────────┘
```

### Core Components

**Backend (Spring Boot)**
- **Controllers**: Handle HTTP requests for uploads, analysis, and search
- **Services**: Business logic orchestration (ContractService, AiIntegrationService, etc.)
- **Models**: JPA entities for MongoDB (Contract, AnalysisResult, RiskReport)
- **Repositories**: MongoDB data access (ContractRepository, AnalysisResultRepository)
- **DTOs**: Data transfer objects for API communication
- **Exception Handling**: Custom exceptions and global error handling

**AI Microservice (FastAPI)**
- **Routes**: REST endpoints for embedding, analysis, search, and health checks
- **RAG Pipeline**: Retrieval-Augmented Generation processing
- **Embedder**: Sentence-transformer embeddings (all-MiniLM-L6-v2)
- **Vector Store**: FAISS similarity search
- **Ollama Client**: LLM integration for summarization and risk analysis

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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env as needed

# Download required models
ollama pull gemma3:4b
ollama pull all-MiniLM-L6-v2

# Start the AI service
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
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
RAG_TOP_K=7
RAG_MIN_SCORE=0.30
```

## 📝 API Usage

### Upload a Contract

```bash
curl -X POST http://localhost:6969/upload \
  -F "file=@contract.pdf" \
  -F "name=my_contract"
```

### Analyze a Contract

```bash
# First, upload to get contract ID
# Then analyze
curl -X POST http://localhost:6969/contracts/{id}/analyze
```

### Search Contracts

```bash
curl -X POST http://localhost:6969/search \
  -H "Content-Type: application/json" \
  -d '{"query": "termination clauses", "topK": 5}'
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

## 👥 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 🆘 Support

For issues and questions, please refer to the detailed documentation in the `docs/` directory.