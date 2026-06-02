# Getting Started Guide

## Quick Start

This guide will help you set up and run the AI Contract Summarization System locally.

## Prerequisites

- Java 21 or later
- Maven 3.8+
- Python 3.11+
- Docker (optional, for MongoDB)
- Ollama (for local LLM fallback) **or** NVIDIA API key (for cloud inference)

---

## Backend Setup

### 1. Install Dependencies
```bash
cd backend
mvn dependency:resolve
```

### 2. Configure Application
Edit `backend/src/main/resources/application.yaml` to configure:
- MongoDB connection (or use Docker)
- File upload directory
- AI service settings

### 3. Start MongoDB (Docker)
```bash
docker-compose up -d
```

Or start MongoDB manually with authentication.

### 4. Build the Project
```bash
mvn clean package
```

### 5. Run the Application
```bash
mvn spring-boot:run
```

The backend will start on `http://localhost:6969`

---

## Python AI Service Setup

### 1. Create Virtual Environment
```bash
cd ai-service
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure AI Service
Create a `.env` file in `ai-service/` with the following:

```env
# LLM — Primary (NVIDIA NIM cloud inference)
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=meta/llama-3.3-70b-instruct

# LLM — Fallback (local Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Embedding
EMBEDDING_MODEL=all-MiniLM-L6-v2

# RAG
RAG_TOP_K=7
RAG_MIN_SCORE=0.20
```

At least one LLM provider must be configured:
- **NVIDIA NIM** (recommended): Set `NVIDIA_API_KEY` for zero-setup cloud inference
- **Ollama** (offline fallback): Install Ollama and pull a model

### 4. Install Ollama (for local LLM fallback)
Follow instructions at https://ollama.ai/download, then:
```bash
ollama pull llama3
```

### 5. Start the AI Service
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The AI service will be available at `http://localhost:5000`

---

## Testing

### Backend Tests
```bash
mvn test
```

### Python Tests
```bash
cd ai-service && pytest tests/
```

### Verify Setup

**Health Check (Backend):**
```bash
curl http://localhost:6969/health
```

**Health Check (AI Service):**
```bash
curl http://localhost:6969/api/health
```

**Upload a Sample:**
```bash
curl -X POST http://localhost:6969/contracts/upload \
  -F "file=@contract_sample/real_estate_contract.docx"
```

---

## Project Structure

```
ai-contract-system/
├── backend/                    # Spring Boot application
│   ├── src/main/java/com/grim/backend/
│   │   ├── config/             # WebClient configuration
│   │   ├── controller/         # REST controllers
│   │   ├── service/            # Business services
│   │   ├── model/              # MongoDB entities
│   │   ├── dto/                # Data transfer objects
│   │   ├── repository/         # MongoDB repositories
│   │   ├── exception/          # Custom exceptions
│   │   └── BackendApplication.java
│   ├── src/main/resources/
│   │   ├── application.yaml    # Main config
│   │   └── templates/          # Thymeleaf pages
│   └── pom.xml
├── ai-service/                 # Python AI service
│   ├── app/
│   │   ├── api/routes.py       # FastAPI routes
│   │   ├── core/               # RAG pipeline, LLM clients, embedder, vector store, prompts
│   │   ├── models/schemas.py   # Pydantic models
│   │   └── config.py           # Configuration (pydantic-settings)
│   ├── main.py                 # FastAPI entry point
│   ├── tests/                  # Python tests
│   └── requirements.txt
├── docs/                       # Documentation
├── contract_sample/            # Sample contracts
├── docker-compose.yml          # MongoDB only
└── .opencode/                  # OpenCode CLI config + graphify plugin
```

---

## Docker Deployment

### Start MongoDB
```bash
docker-compose up -d
```

This starts MongoDB 6.0 on port 27017 with the default credentials.

### Stop Services
```bash
docker-compose down
```

Note: The backend and AI service run natively (not in Docker).

---

## Configuration

### File Upload Settings
- Maximum file size: 20MB
- Supported formats: PDF, DOCX
- Upload directory: `./uploads` (relative to project root)
- Magic-byte validation prevents extension spoofing

### Chunking Settings
- Chunk size: 2500 characters (configurable)
- Overlap: 100 characters (configurable)
- Configure in `application.yaml`

### LLM Provider Settings

**NVIDIA NIM (Primary):**
```env
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_TIMEOUT=60
```

**Ollama (Fallback):**
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
OLLAMA_MAX_TOKENS=1024
OLLAMA_TEMPERATURE=0.1
```

### RAG Settings
```env
RAG_TOP_K=7          # Number of chunks to retrieve
RAG_MIN_SCORE=0.20   # Minimum similarity threshold
```

---

## Quick API Reference

### Upload & Analyze
```bash
# Upload
curl -X POST http://localhost:6969/contracts/upload \
  -F "file=@contract.pdf"

# View contract (get the ID from the redirect URL)
curl http://localhost:6969/contracts/{id}

# Analysis auto-triggers on upload; check status:
curl http://localhost:6969/api/contracts/{id}/status
```

### Search
```bash
curl -X POST http://localhost:6969/analysis/search \
  -H "Content-Type: application/json" \
  -d '{"contractId": "...", "query": "termination clauses", "topK": 5}'
```

---

## Troubleshooting

### "Connection refused" on AI endpoints
- Ensure the Python service is running: `uvicorn main:app --host 0.0.0.0 --port 5000`
- Check `.env` is properly configured
- Verify port 5000 is not in use: `lsof -ti:5000`

### "No LLM provider reachable"
- Either set `NVIDIA_API_KEY` in `.env` or start Ollama: `ollama serve`
- Verify model is pulled: `ollama list`
- Check `NVIDIA_BASE_URL` if using a custom endpoint

### "Model not found" from Ollama
```bash
ollama pull llama3
```

### MongoDB Connection Failed
- Check Docker: `docker ps`
- Verify connection string in `application.yaml`
- Ensure MongoDB is running on port 27017

### File Upload Failures
- Check file size (max 20MB)
- Verify file format is PDF or DOCX
- Ensure upload directory exists: `./uploads/`
- Check magic-byte validation isn't rejecting a valid file

### Empty Analysis Results
- Enable AI service: Set `app.ai.service.enabled=true` in `application.yaml`
- Check Python logs for errors
- Verify LLM provider is reachable
- Try a contract with sufficient text content

### Health Check Endpoints
```bash
# Backend status
curl http://localhost:6969/api/health

# AI service detailed status (from Python)
curl http://localhost:5000/api/ai/health
```

### Logs
- Backend logs: Spring Boot console output (level controlled by `application.yaml`)
- Python logs: `LOG_LEVEL=DEBUG` in `.env` for verbose output
- Health endpoint shows real-time AI service connectivity
