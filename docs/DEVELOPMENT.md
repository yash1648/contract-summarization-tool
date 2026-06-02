# Development Guide

## Development Environment Setup

### IDE Configuration

#### IntelliJ IDEA
1. Import the `backend/` directory as a Maven project
2. Ensure Java 21 SDK is configured
3. Install Python plugin for AI service development
4. Configure remote interpreter for Python virtual environment in `ai-service/`

#### VS Code
1. Open the project root folder
2. Install Java Extension Pack
3. Install Python extension
4. Configure Java home and Python interpreter

### Environment Variables

The AI service uses a `.env` file in `ai-service/`. Reference `app/config.py` for all available variables:

```env
# Server
HOST=0.0.0.0
PORT=5000
LOG_LEVEL=DEBUG

# Primary LLM (NVIDIA NIM)
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=meta/llama-3.3-70b-instruct

# Fallback LLM (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Embedding
EMBEDDING_MODEL=all-MiniLM-L6-v2

# RAG
RAG_TOP_K=7
RAG_MIN_SCORE=0.20
```

---

## Build and Test

### Maven Commands (Backend)

```bash
# Clean build
mvn clean package -DskipTests

# Compile only
mvn compile

# Run all tests
mvn test

# Run specific test class
mvn test -Dtest=BackendApplicationTests

# Run backend
mvn spring-boot:run
```

### Python Testing (AI Service)

```bash
# Run all tests
cd ai-service && pytest tests/

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=app tests/
```

---

## Code Structure

### Backend (Java 21, Spring Boot)

```
backend/
└── src/
    ├── main/
    │   ├── java/com/grim/backend/
    │   │   ├── config/              # AppConfig (WebClient beans)
    │   │   │   └── AppConfig.java
    │   │   ├── controller/          # REST controllers
    │   │   │   ├── ContractController.java    # /contracts/*
    │   │   │   ├── AnalysisController.java    # /analysis/*
    │   │   │   ├── DashboardController.java   # /dashboard, /api/health
    │   │   │   └── HealthController.java      # /health
    │   │   ├── service/             # Business logic
    │   │   │   ├── ContractService.java       # Upload pipeline orchestrator
    │   │   │   ├── AnalysisService.java       # Analysis + search orchestrator
    │   │   │   ├── AiIntegrationService.java  # HTTP bridge to Python
    │   │   │   ├── AiHealthService.java       # Cached health checks
    │   │   │   ├── TextExtractionService.java # PDF/DOCX text extraction
    │   │   │   └── ChunkingService.java       # Text chunking
    │   │   ├── model/               # MongoDB entities
    │   │   │   ├── Contract.java
    │   │   │   ├── ContractChunk.java
    │   │   │   ├── AnalysisResult.java
    │   │   │   └── RiskReport.java
    │   │   ├── dto/                 # Data transfer objects
    │   │   │   ├── UploadResponseDto.java
    │   │   │   ├── AnalysisResponseDto.java
    │   │   │   └── SearchRequestDto.java
    │   │   ├── repository/          # MongoDB data access
    │   │   │   ├── ContractRepository.java
    │   │   │   └── AnalysisResultRepository.java
    │   │   ├── exception/           # Custom exceptions + handler
    │   │   │   ├── ContractNotFoundException.java
    │   │   │   ├── FileProcessingException.java
    │   │   │   └── GlobalExceptionHandler.java
    │   │   └── BackendApplication.java
    │   └── resources/
    │       ├── application.yaml     # Main config
    │       └── templates/           # Thymeleaf pages
    │           ├── index.html       # Dashboard
    │           ├── upload.html      # Upload form
    │           ├── contracts.html   # Contract list
    │           ├── contract-detail.html  # Contract detail
    │           ├── analysis.html    # Analysis result
    │           ├── analysis-list.html    # All analyses
    │           ├── search.html      # Search page
    │           ├── layout.html      # Base layout
    │           └── error.html       # Error page
    └── test/
        └── java/com/grim/backend/
            └── BackendApplicationTests.java
```

### AI Service (Python 3.11+, FastAPI)

```
ai-service/
├── main.py                         # FastAPI entry point (background startup)
├── app/
│   ├── __init__.py
│   ├── config.py                   # Pydantic settings (pydantic-settings)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # 6 REST endpoints under /api/ai
│   ├── core/
│   │   ├── __init__.py
│   │   ├── rag_pipeline.py         # RAG orchestrator (map-reduce, TTLCache)
│   │   ├── llm_client.py           # Unified LLM client with failover
│   │   ├── nvidia_nim_client.py    # NVIDIA NIM provider
│   │   ├── ollama_client.py        # Ollama provider
│   │   ├── embedder.py             # Sentence-transformer singleton
│   │   ├── vector_store.py         # FAISS per-contract indexes
│   │   └── prompts.py              # Prompt templates + parsers
│   └── models/
│       ├── __init__.py
│       └── schemas.py              # Pydantic request/response models
├── tests/
│   ├── __init__.py
│   ├── test_api.py                 # API integration tests
│   └── test_chunking.py            # VectorStore unit tests
├── requirements.txt
└── .env                            # Local config (not committed)
```

---

## Running the Application

### Development Mode

**Backend:**
```bash
cd backend
mvn spring-boot:run
```

**AI Service:**
```bash
cd ai-service
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The `--reload` flag enables auto-restart on code changes.

### Production Mode

**Backend:**
```bash
cd backend
java -jar target/ai-assistant-backend-0.0.1-SNAPSHOT.jar
```

**AI Service:**
```bash
cd ai-service
uvicorn main:app --host 0.0.0.0 --port 5000
```

### Database
```bash
# Start MongoDB
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Debugging

### Backend Debugging

**IntelliJ IDEA:**
1. Open the project
2. Click on the run/debug configuration
3. Set breakpoints
4. Click the debug icon

**VS Code:**
1. Open the project
2. Go to Run and Debug
3. Create a new Java configuration
4. Set breakpoints and start debugging

### AI Service Debugging

```bash
# With verbose logging
LOG_LEVEL=DEBUG uvicorn main:app --host 0.0.0.0 --port 5000 --reload --log-level debug

# Using pdb
python -m pdb main.py
```

### Common Issues

**Issue: MongoDB Connection Failed**
```bash
# Check if MongoDB is running
docker ps | grep mongo

# Start MongoDB
docker-compose up -d database
```

**Issue: LLM Provider Unreachable**
```bash
# Check NVIDIA API key is set
echo $NVIDIA_API_KEY

# Or check Ollama
ollama list
ollama serve
```

**Issue: Port Already in Use**
```bash
# Find process using port
lsof -ti:6969 | xargs kill -9
lsof -ti:5000 | xargs kill -9
```

**Issue: Embedding Model Not Found**
- The model (`all-MiniLM-L6-v2`) is auto-downloaded on first run via HuggingFace
- Ensure internet connectivity for first-time download
- ~80MB download, cached locally afterwards

---

## Key Implementation Details

### LLM Failover Flow
```
LLMClient.ask()
  └─ NVIDIA NIM reachable + key present?
       ├─ Yes → Use NVIDIA (returns response)
       └─ No  → Ollama reachable + model loaded?
                 ├─ Yes → Use Ollama (returns response)
                 └─ No  → Raise exception (no LLM available)
```

### Upload Pipeline
```
handleUpload()
  └─ validateFile()        → MIME type + size check
  └─ validateFileContent() → Magic-byte signature check
  └─ saveFileToDisk()      → UUID-prefixed, sanitized filename
  └─ extractText()         → PDFBox / Apache POI
  └─ chunk()               → Configurable size/overlap
  └─ sendChunksForEmbedding() → POST /api/ai/embed
  └─ Persist to MongoDB
  └─ Submit async analysis → Thread pool executor
```

### Analysis Flow
```
analyzeContract()
  └─ Fetch contract + chunks from MongoDB
  └─ Delete any prior analysis result
  └─ Set status → ANALYZING
  └─ POST /api/ai/analyze → RAG pipeline:
       ├─ Multi-query FAISS retrieval
       ├─ Parallel chunk summarization (map)
       ├─ Single combined LLM call (reduce)
       └─ Risk JSON extraction
  └─ Save AnalysisResult to MongoDB
  └─ Set status → COMPLETED (or FAILED)
```

### Search Flow
```
search()
  └─ AiIntegrationService.semanticSearch() → POST /api/ai/search
       ├─ Success → Use AI FAISS results
       └─ Fail    → localTextSearch() term matching
  └─ If chunks found + AI available:
       └─ askQuestion() → POST /api/ai/ask → answer synthesis
  └─ Return { query, answer, results[], count }
```

---

## Performance Considerations

### JVM Tuning
```bash
export JAVA_OPTS="-Xms512m -Xmx2g -XX:+UseG1GC"
mvn spring-boot:run
```

### Python Performance
- Embedder encodes in batches (default batch size: 32)
- RAG runs parallel chunk summarization via ThreadPoolExecutor
- Embedding model loads once (singleton) — ~5-20s on first call
- Background startup avoids blocking HTTP server

### Database Optimization
- MongoDB indexes on `contractId`, `status`, `analyzedAt`
- FAISS indexes stored natively (not pickled) for safe persistence
- Health checks cached for 30s to reduce load

---

## Version Control

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/contract-analysis

# Stage changes
git add backend/src/main/java/com/grim/backend/service/ContractService.java

# Commit with message
git commit -m "feat: add contract analysis service"

# Push to remote
git push origin feature/contract-analysis
```

### Code Review Checklist
- [ ] Code follows project conventions (package: `com.grim.backend`)
- [ ] Tests are included for new features
- [ ] Documentation is updated
- [ ] No sensitive information in commits (API keys, passwords)
- [ ] Performance impact considered (especially LLM calls)
- [ ] Error handling implemented (graceful degradation)

---

## Best Practices

### Java Development
1. Use Lombok annotations to reduce boilerplate
2. Follow Spring Boot conventions
3. Implement proper exception handling with global handler
4. Use repository pattern for data access
5. Add comprehensive logging (SLF4J + Logback)
6. Validate file content with magic bytes

### Python Development
1. Use Pydantic for data validation (schemas.py)
2. Implement proper error handling with HTTPException
3. Use async/await for I/O operations
4. Add type hints to all functions
5. Write comprehensive tests with mocks
6. Use loguru for structured logging

### API Design
1. Use consistent naming conventions
2. Implement proper error responses
3. Add comprehensive documentation
4. Use appropriate HTTP status codes
5. Implement graceful degradation for AI failures
