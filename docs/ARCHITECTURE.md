# AI Contract System - Architecture Documentation

## 🏗️ System Architecture Overview

The AI Contract Summarization System is a **modular monolithic web application** with an integrated AI pipeline. It combines a Spring Boot backend with a Python AI microservice to provide intelligent contract analysis using Retrieval-Augmented Generation (RAG).

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Thymeleaf)                 │
└───────────────────────┬─────────────────────────────────┘
                        │
               HTTP Requests/Responses
                        │
┌───────────────────────▼────────────────────┐
│          Spring Boot Backend                 │
│  ┌─────────────┐    ┌─────────────────┐   │
│  │ Controllers │◄───┤    Services     │   │
│  └─────────────┘    │  ┌─────────────┐  │   │
│                     │  │ AI Integration│◄──┘───┐
│  ┌─────────────┐    │  └─────────────┘       │
│  │   Models    │◄───┘                        │
│  └─────────────┘    ┌─────────────────┐       │
│                     │  ┌─────────────┐  │       │
│  ┌─────────────┐    │  │ Repositories│◄────┘
│  │   DTOs      │◄───┘  └─────────────┘
│  └─────────────┘       ┌─────────────┐
│                          │ Exceptions  │
│  ┌─────────────┐        └─────────────┘
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
│  │                        └─────────┘        │
│  └─────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

## 📦 Component Breakdown

### 1. Spring Boot Backend (Java)

#### Entry Point
- **`BackendApplication.java`**: Main Spring Boot application starter

#### Configuration
- **`application.yaml`**: Application configuration including:
  - MongoDB connection settings
  - File upload settings (20MB limit)
  - Chunking parameters (size: 2500 chars, overlap: 100)
  - AI service configuration (endpoint, timeout, retry settings)
- **`AppConfig.java`**: WebClient configuration for AI service integration

#### Data Models
- **`Contract.java`**: Main contract entity with processing status
- **`ContractChunk.java`**: Individual text chunks with indexing
- **`AnalysisResult.java`**: Stores AI analysis results and risk assessment
- **`RiskReport.java`**: Structured risk analysis data

#### DTOs (Data Transfer Objects)
- **`UploadResponseDto`**: Response for file upload operations
- **`AnalysisResponseDto`**: Analysis results response
- **`SearchRequestDto`**: Search query request
- **`SearchResponseDto`**: Search results response

#### Services
- **`ContractService.java`**: Core orchestrator for upload, processing, and deletion
- **`TextExtractionService.java`**: PDF/DOCX text extraction using Apache PDFBox and Apache POI
- **`ChunkingService.java`**: Text splitting with configurable chunk size and overlap
- **`AiIntegrationService.java`**: HTTP client for Python AI service communication
- **`AiHealthService.java`**: Health monitoring and status tracking

#### Exception Handling
- **`GlobalExceptionHandler.java`**: Global exception handler
- **`ContractNotFoundException.java`**: Custom exception for missing contracts
- **`FileProcessingException.java`**: File processing errors

#### Web Controllers
- **`DashboardController.java`**: Health endpoints and dashboard data
- **`ContractController.java`**: Upload, list, detail, and delete endpoints
- **`AnalysisController.java`**: Trigger analysis, view results, semantic search

#### Templates
- **Thymeleaf templates**: HTML templates for dashboard and UI

#### Repository Layer
- **`ContractRepository.java`**: MongoDB repository for contracts
- **`AnalysisResultRepository.java`**: MongoDB repository for analysis results

### 2. Python AI Microservice (FastAPI)

#### Entry Point
- **`ai-service/main.py`**: FastAPI application entry point

#### Configuration
- **`ai-service/.env`**: Environment variables
- **`ai-service/app/config.py`**: Pydantic-based configuration management

#### Core Modules
- **`ai-service/app/core/embedder.py`**: Sentence-transformer embedding service
- **`ai-service/app/core/vector_store.py`**: FAISS vector database management
- **`ai-service/app/core/ollama_client.py`**: Ollama LLM client
- **`ai-service/app/core/rag_pipeline.py`**: RAG processing pipeline
- **`ai-service/app/models/schemas.py`**: Pydantic data schemas
- **`ai-service/app/api/routes.py`**: FastAPI route definitions

## 🔗 Data Flow

### Upload & Processing Flow
1. **File Upload**: User uploads PDF/DOCX via `ContractController`
2. **File Storage**: File saved to `./uploads` directory with UUID prefix
3. **Text Extraction**: `TextExtractionService` extracts raw text
4. **Chunking**: Text split into chunks (default: 2500 chars, 100 overlap)
5. **Embedding**: Chunks sent to Python AI service via `AiIntegrationService`
6. **Vector Storage**: Embeddings stored in FAISS index per contract
7. **Persistence**: Contract metadata stored in MongoDB

### Analysis Flow
1. **Analysis Request**: User triggers analysis via `AnalysisController`
2. **Chunk Retrieval**: Relevant chunks fetched from MongoDB
3. **RAG Pipeline**: 
   - Multiple queries for comprehensive retrieval
   - Parallel summarization of chunks
   - Map-reduce summarization strategy
4. **LLM Processing**: Single Ollama call for combined summary + risk analysis
5. **Result Storage**: Analysis results persisted to MongoDB

### Search Flow
1. **Query Encoding**: User query encoded to embedding
2. **Vector Search**: FAISS similarity search with min score threshold
3. **Result Retrieval**: Top-k most similar chunks returned

## 🌐 Communication Protocol

### HTTP API Between Services
- **Base URL**: `http://localhost:5000` (configurable)
- **Timeouts**: 1200 seconds (20 minutes) for long-running operations
- **Retry Strategy**: Up to 2 retries with 1-second delay
- **Error Handling**: Comprehensive error handling with detailed logging

### Request/Response Formats

#### Embedding Endpoint
```json
// Request
{
  "contractId": "string",
  "chunks": [{"index": 0, "text": "..."}]
}

// Response
{
  "contractId": "string",
  "embeddingIds": ["uuid1", ...],
  "chunksEmbedded": 5
}
```

#### Analysis Endpoint
```json
// Request
{
  "contractId": "string",
  "chunkTexts": ["chunk1 text", "chunk2 text", ...]
}

// Response
{
  "summary": "...",
  "riskScore": 4.2,
  "penaltyClauses": [...],
  "terminationRisks": [...],
  "liabilityIssues": [...],
  "otherFlags": [...],
  "chunksUsed": 7
}
```

## 📊 Key Features

1. **Dual-Pass Analysis**: Separate summarization and risk analysis for accuracy
2. **RAG Pipeline**: Retrieval-Augmented Generation for context-aware analysis
3. **Map-Reduce Summarization**: Handles large documents efficiently
4. **Fault Tolerance**: Graceful degradation when AI service unavailable
5. **Parallel Processing**: Multi-threaded chunk summarization
6. **Vector Similarity Search**: Semantic search using embeddings

## 🛠️ Infrastructure Dependencies

- **MongoDB**: Document database for persistent storage
- **FAISS**: Vector database for similarity search
- **Ollama**: Local LLM engine
- **Sentence-Transformers**: Embedding model (all-MiniLM-L6-v2)

## 🔧 Configuration Management

All configuration is centralized and environment-aware:
- Database connections
- File upload limits
- AI service endpoints
- Model parameters
- Retry and timeout settings

This architecture provides a robust, scalable foundation for intelligent contract analysis with clear separation of concerns and well-defined interfaces between components.