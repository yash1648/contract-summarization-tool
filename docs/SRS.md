# Software Requirements Specification (SRS)
# AI Contract Summarization System (RAG-Based)

## 1. Introduction

### 1.1 Purpose

This document provides a detailed description of the requirements for the AI Contract Summarization System, a web-based application that leverages Retrieval-Augmented Generation (RAG) and Natural Language Processing (NLP) to analyze and summarize legal contracts.

The system is intended for:
- Legal professionals
- Businesses
- Individuals handling contracts

### 1.2 Scope

The system enables users to:
- Upload contract documents (PDF/DOCX) with magic-byte validation
- Automatically generate summaries and extract structured fields
- Detect and highlight risky clauses (penalties, termination, liability)
- Perform semantic search with AI-synthesised answers
- Ask natural-language questions about contracts
- Store and manage contract data with processing status tracking

It integrates:
- Spring Boot backend (Java 21)
- Thymeleaf frontend
- MongoDB database
- Python AI microservice (FastAPI)
- NVIDIA NIM (primary LLM) + Ollama (fallback LLM)
- FAISS vector similarity search
- sentence-transformers embedding model

### 1.3 Definitions & Acronyms

| Term | Meaning |
|------|---------|
| NLP | Natural Language Processing |
| LLM | Large Language Model |
| RAG | Retrieval-Augmented Generation |
| Embedding | Vector representation of text |
| FAISS | Facebook AI Similarity Search |
| NVIDIA NIM | NVIDIA Inference Microservices |
| TTLCache | Time-To-Live Cache |

### 1.4 References
- Project abstract
- IEEE SRS Guidelines

---

## 2. Overall Description

### 2.1 Product Perspective

The system is a modular monolithic web application with an integrated AI pipeline comprising two services: a Spring Boot backend serving Thymeleaf pages and REST endpoints, and a Python FastAPI microservice handling all AI/ML workloads.

### 2.2 Product Functions

The system performs the following:
- Document upload and parsing (PDF/DOCX with magic-byte validation)
- Text preprocessing and chunking (configurable size/overlap)
- Embedding generation (sentence-transformers)
- Vector storage and retrieval (FAISS per-contract indexes)
- AI-based summarization and risk analysis (map-reduce RAG)
- Extraction-first pipeline for low-resource machines
- Semantic search with AI answer synthesis
- Natural-language Q&A on contract content
- Asynchronous analysis with frontend polling notifications
- Graceful degradation when AI services are unavailable

### 2.3 User Classes

| User Type | Description |
|-----------|-------------|
| General User | Uploads and analyzes contracts via web interface |
| Admin (optional) | Monitors system usage and AI service health |

### 2.4 Operating Environment

| Component | Technology |
|-----------|------------|
| OS | Linux / Windows / macOS |
| Backend | Spring Boot 3.x (Java 21) |
| Frontend | Thymeleaf templates |
| Database | MongoDB 6.0 |
| AI Service | FastAPI (Python 3.11+) |
| Vector Store | FAISS |
| LLM (primary) | NVIDIA NIM (cloud) |
| LLM (fallback) | Ollama (local) |
| Browser | Chrome / Firefox / Edge |

### 2.5 Design Constraints

- Limited LLM context window requires chunking strategy
- Dependency on AI model accuracy — results should be reviewed
- Integration complexity between Java and Python services
- First-time embedding model download requires internet (~80MB)
- Embdedding model loads asynchronously (5-20s background startup)

### 2.6 Assumptions

- Users provide valid contract documents
- AI models are pre-trained and available
- At least one LLM provider is configured (NVIDIA NIM or Ollama)
- MongoDB is accessible at the configured URI

---

## 3. System Features

### 3.1 Document Upload
**Description:** Allows users to upload contract files (PDF/DOCX, max 20MB). Files are validated by MIME type and magic-byte signatures to prevent extension spoofing.

**Inputs:** PDF or DOCX file
**Outputs:** Stored document with processing status

### 3.2 Text Extraction
**Description:** Extracts raw text from uploaded files using Apache PDFBox (PDF) and Apache POI (DOCX).

### 3.3 Chunking & Embedding
**Description:** Splits text into configurable chunks (default 2000 chars, 200 overlap) and converts chunks into 384-dimension vector embeddings using sentence-transformers (`all-MiniLM-L6-v2`).

### 3.4 Vector Storage (FAISS)
**Description:** Stores embeddings in per-contract FAISS indexes. Indexes are persisted natively (no pickle) with JSON metadata for safe cross-version loading.

### 3.5 Semantic Retrieval (RAG Core)
**Description:** Converts user query into embedding and retrieves relevant chunks via FAISS approximate nearest-neighbour search. Supports cross-contract and per-contract search.

### 3.6 Summarization & Risk Analysis
**Description:** Generates concise summary using LLM. Uses map-reduce strategy — chunks summarized in parallel, then a single combined LLM call produces both summary and structured risk JSON (penalty clauses, termination risks, liability issues, other flags). Score normalized 0-10 with LOW/MEDIUM/HIGH risk levels.

### 3.7 Extraction-First Pipeline
**Description:** Lightweight alternative to full RAG analysis for low-resource machines. Splits chunks into sentences, filters by cosine similarity against domain queries, extracts structured JSON fields per chunk (parties, obligations, payment terms, dates, penalties, termination).

### 3.8 Semantic Search & Q&A
**Description:** Users can search contracts with natural language. The system returns semantically similar chunks (FAISS) with an AI-synthesised answer (via `/api/ai/ask`). Falls back to local term-frequency matching when AI is unavailable.

### 3.9 Dual LLM Provider
**Description:** Automatic failover between NVIDIA NIM (cloud, primary) and Ollama (local, fallback). Provider health is tracked per-request. No configuration changes needed to switch providers.

### 3.10 Data Storage (MongoDB)
**Description:** Stores contracts, chunks, analysis results, and risk reports. Includes processing status tracking (UPLOADED → EXTRACTING → CHUNKING → PENDING_AI → ANALYZING → COMPLETED/FAILED).

---

## 4. Functional Requirements

| ID | Description |
|----|-------------|
| FR1 | System shall allow users to upload PDF/DOCX files (max 20MB) |
| FR2 | System shall validate uploaded files by MIME type and magic-byte signatures |
| FR3 | System shall extract text from uploaded documents |
| FR4 | System shall split text into configurable chunks |
| FR5 | System shall convert text chunks into vector embeddings |
| FR6 | System shall store embeddings in per-contract FAISS indexes |
| FR7 | System shall perform similarity search using embeddings |
| FR8 | System shall produce contract summary using LLM (map-reduce) |
| FR9 | System shall identify risky clauses (penalties, termination, liability) |
| FR10 | System shall support extraction-first pipeline for low-resource machines |
| FR11 | System shall synthesise natural-language answers for search queries |
| FR12 | System shall support natural-language Q&A on contract content |
| FR13 | System shall provide health check endpoint for AI service monitoring |
| FR14 | System shall store processed results in MongoDB |
| FR15 | System shall display results via Thymeleaf web interface |
| FR16 | System shall auto-trigger analysis on upload via background thread pool |
| FR17 | System shall support LLM provider failover (NVIDIA NIM → Ollama) |
| FR18 | System shall poll frontend for async analysis completion notifications |
| FR19 | System shall cache health checks (30s TTL) to reduce load |
| FR20 | System shall gracefully degrade when AI service is unavailable |

---

## 5. Non-Functional Requirements

### 5.1 Performance
- Response time < 5 seconds for small documents (embedding + search)
- HTTP server starts in < 1 second (embedding model loads async)
- Analysis may take 30-120 seconds depending on document size

### 5.2 Scalability
- System should handle multiple concurrent uploads
- Dedicated thread pool for analysis (2 threads)
- Background startup avoids blocking HTTP server

### 5.3 Usability
- Simple and intuitive web interface (Thymeleaf)
- Dashboard with live AI service status
- Toast notifications for async operation completion
- Search page with semantic results

### 5.4 Security
- Magic-byte validation prevents file extension spoofing
- UUID-prefixed filenames prevent path traversal
- Filename sanitization on save
- No API keys committed to repository

### 5.5 Reliability
- Graceful degradation when AI services are unavailable
- Local text search fallback when FAISS/AI is down
- Automatic LLM provider failover (NVIDIA → Ollama)
- Retry logic with configurable attempts and delays

---

## 6. System Workflow

### Upload & Processing
```
User uploads PDF/DOCX
  → MIME type validation
  → Magic-byte signature check
  → File saved to ./uploads/
  → Text extraction (PDFBox / POI)
  → Chunking (2000 chars, 200 overlap)
  → POST /api/ai/embed → Embedding → FAISS storage
  → Persist to MongoDB
  → Auto-submit async analysis (background thread)
```

### RAG Analysis
```
Trigger analysis (manual or auto)
  → Fetch chunks from MongoDB
  → POST /api/ai/analyze
      → Multi-query FAISS retrieval
      → Map: parallel chunk summarization
      → Reduce: single LLM call for summary + risk
  → Save AnalysisResult to MongoDB
  → Notify frontend via polling endpoint
```

### Semantic Search
```
User submits query
  → POST /api/ai/search → FAISS similarity search
  → (fallback: localTextSearch term matching)
  → If AI available: POST /api/ai/ask → answer synthesis
  → Return { query, answer, results[], count }
```

---

## 7. Data Requirements

### MongoDB Collections

**Contract:**
```
{
  "_id": "ObjectId",
  "fileName": "string",
  "fileType": "string",
  "fileSize": "long",
  "storagePath": "string",
  "status": "UPLOADED|EXTRACTING|CHUNKING|PENDING_AI|ANALYZING|COMPLETED|FAILED",
  "extractedText": "string",
  "chunks": [{ index, text, embeddingId, embedded }],
  "totalChunks": "int",
  "analysisResultId": "string|null",
  "createdAt": "datetime",
  "processedAt": "datetime|null"
}
```

**AnalysisResult:**
```
{
  "_id": "ObjectId",
  "contractId": "string",
  "contractFileName": "string",
  "summary": "string",
  "riskScore": "double",
  "riskLevel": "LOW|MEDIUM|HIGH",
  "riskReport": {
    "penaltyClauses": ["string"],
    "terminationRisks": ["string"],
    "liabilityIssues": ["string"],
    "otherFlags": ["string"]
  },
  "chunksUsed": "int",
  "analyzedAt": "datetime"
}
```

### AI Service Request/Response Examples

**POST /api/ai/analyze**
```json
// Request
{
  "contractId": "...",
  "chunkTexts": ["chunk 1", "chunk 2"]
}

// Response
{
  "summary": "This agreement...",
  "riskScore": 4.2,
  "penaltyClauses": ["Late fee of 5%"],
  "terminationRisks": ["30-day notice required"],
  "liabilityIssues": ["Indemnification clause"],
  "otherFlags": ["Non-compete clause"],
  "chunksUsed": 2
}
```

---

## 8. Architecture Diagrams

### Component Architecture
```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ Thymeleaf│────►│Spring Boot   │────►│Python FastAPI│
│ Frontend │     │Backend       │     │AI Microservice│
└──────────┘     │(com.grim)    │     └──────┬───────┘
                 └──────┬───────┘            │
                        │                    │
                 ┌──────▼───────┐    ┌───────▼───────┐
                 │   MongoDB    │    │  FAISS + LLM  │
                 └──────────────┘    └───────────────┘
```

### Data Flow
```
Upload → Extract → Chunk → Embed(Faiss) → Store(MongoDB) → Analyze(LLM) → Display
```

---

## 9. Advantages

- Semantic understanding using embeddings (beyond keyword search)
- Efficient processing via RAG (retrieve only relevant chunks)
- Scalable architecture with clear separation of concerns
- Improved accuracy with map-reduce summarization
- Fault tolerance with dual LLM provider and local fallbacks
- Fast startup via background initialization
- Safe file handling with magic-byte validation

## 10. Limitations

- Requires GPU acceleration for large-scale embedding
- AI output may not be 100% accurate — human review recommended
- Initial setup complexity (multiple services)
- First-time embedding model download requires internet (~80MB)
- Cross-contract search limited to AI service availability

## 11. Future Enhancements

- Legal chatbot interface
- Multi-language support
- Fine-tuned legal LLM
- Real-time collaboration
- Document comparison across contracts
- Batch upload and analysis
- Role-based access control
