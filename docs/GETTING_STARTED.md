# Getting Started Guide

## 🚀 Quick Start

This guide will help you set up and run the AI Contract Summarization System locally.

## 📋 Prerequisites

- Java 21 or later
- Maven 3.8+
- Python 3.11+
- Docker (optional, for MongoDB)
- Ollama (for local LLM)

## 🏗️ Backend Setup

### 1. Install Dependencies
```bash
cd backend
mvn dependency:resolve
```

### 2. Configure Application
Copy the example configuration:
```bash
cp src/main/resources/application.yaml.example src/main/resources/application.yaml
```

Edit `application.yaml` to configure:
- MongoDB connection (or use Docker)
- File upload directory
- AI service settings

### 3. Start MongoDB (Docker)
```bash
docker-compose up -d
```

Or start MongoDB manually:
```bash
mongod --auth --port 27017
```

### 4. Build the Project
```bash
mvn clean package
```

### 5. Run the Application
```bash
mvn spring-boot:run
```

The backend will start on `http://localhost:6969`

## 🤖 Python AI Service Setup

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
Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` to configure:
- Ollama connection settings
- Embedding model (default: `all-MiniLM-L6-v2`)
- RAG parameters

### 4. Install Ollama
Follow instructions at https://ollama.ai/download

### 5. Download Required Models
```bash
ollama pull gemma3:4b
ollama pull all-MiniLM-L6-v2
```

### 6. Start the AI Service
```bash
uvicorn main:app --host 0.0.0.0 --port 5000
```

The AI service will be available at `http://localhost:5000`

## 🧪 Testing

### Backend Tests
```bash
mvn test
```

### API Tests
```bash
pytest tests/
```

### Test API Endpoints

**Health Check:**
```bash
curl http://localhost:6969/api/ai/health
```

**Upload Test File:**
```bash
curl -X POST http://localhost:6969/upload \
  -F "file=@test-document.pdf" \
  -F "name=test"
```

## 📁 Project Structure

```
ai-contract-system/
├── backend/                    # Spring Boot application
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/          # Java source code
│   │   │   └── resources/     # Configuration & templates
│   │   └── test/              # Unit tests
│   └── mvnw                   # Maven wrapper
├── ai-service/                # Python AI service
│   ├── app/
│   │   ├── core/              # Core services (embedder, vector_store, ollama_client)
│   │   ├── api/               # FastAPI routes
│   │   └── models/            # Pydantic schemas
│   ├── tests/                 # Python tests
│   └── .env                   # Environment variables
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   └── GETTING_STARTED.md
└── docker-compose.yml         # Docker services
```

## 🐳 Docker Deployment

### Start All Services
```bash
docker-compose up -d
```

This will start:
- MongoDB database
- Backend application (port 6969)
- AI service (port 5000)

### Stop Services
```bash
docker-compose down
```

## 🔧 Configuration

### File Upload Settings
- Maximum file size: 20MB
- Supported formats: PDF, DOCX, DOC
- Upload directory: `./uploads` (relative to backend root)

### Chunking Settings
- Chunk size: 2500 characters
- Overlap: 100 characters
- Adjust in `application.yaml`

### AI Service Settings
- Embedding model: `all-MiniLM-L6-v2`
- LLM model: `gemma3:4b` (via Ollama)
- Timeout: 1200 seconds (20 minutes)
- Max retries: 2

## 🚨 Troubleshooting

### AI Service Not Reachable
- Ensure Ollama is running: `ollama serve`
- Check model is downloaded: `ollama list`
- Verify port 5000 is available

### MongoDB Connection Failed
- Check Docker: `docker ps`
- Verify connection string in `application.yaml`
- Ensure MongoDB is running on port 27017

### File Upload Failures
- Check file size (max 20MB)
- Verify file format is PDF or DOCX
- Ensure upload directory exists and is writable

### Empty Analysis Results
- Enable AI service: Set `app.ai.service.enabled=true`
- Check Python logs for errors
- Verify Ollama model is loaded

## 📊 Monitoring

### Health Endpoint
```bash
curl http://localhost:6969/api/ai/health
```

Returns status of:
- Embedding model availability
- Ollama connectivity
- FAISS index count

### Logs
Backend logs provide detailed information:
- Upload progress
- Chunking operations
- AI service communication
- Error details