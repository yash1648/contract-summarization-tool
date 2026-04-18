"""
main.py
=======
FastAPI application entry point.

Startup sequence:
  1. Load sentence-transformer embedding model (warm-up)
  2. Restore any persisted FAISS indexes from disk
  3. Log Ollama connectivity status
  4. Mount API router
  5. Serve on configured host:port

Run with:
    uvicorn main:app --host 0.0.0.0 --port 5000 --reload
"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.routes import router
from app.core.embedder import embedder
from app.core.ollama_client import ollama_client
from app.core.vector_store import vector_store


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Code before `yield` runs on startup; code after runs on shutdown.
    """
    # ── STARTUP ──────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  AI Contract Summarization Service — starting up")
    logger.info("=" * 60)

    # 1. Load embedding model (downloads ~90 MB on first run)
    logger.info("Loading embedding model…")
    embedder.load()

    # 2. FAISS indexes are loaded in VectorStore.__init__()
    logger.info(f"FAISS indexes loaded: {vector_store.total_indexes()}")

    # 3. Check Ollama connectivity
    if ollama_client.is_reachable():
        logger.info(f"Ollama OK  model={settings.ollama_model}")
    else:
        logger.warning(
            f"Ollama NOT reachable at {settings.ollama_base_url}. "
            f"Embedding and search will work, but LLM calls will fail. "
            f"Start Ollama and run: ollama pull {settings.ollama_model}"
        )

    logger.info(f"AI service ready on http://{settings.host}:{settings.port}")
    logger.info("=" * 60)

    yield   # ← application runs here

    # ── SHUTDOWN ─────────────────────────────────────────────
    logger.info("AI service shutting down. Goodbye.")


# ── Application factory ──────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Contract Summarization Service",
        description=(
            "RAG-based Python microservice providing embeddings (sentence-transformers + FAISS), "
            "LLM summarization, and risk analysis (Ollama llama3) for the Spring Boot backend."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow requests from Spring Boot (localhost:8080)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    # Mount all routes under /api/ai
    app.include_router(router)

    # Root redirect to API docs
    @app.get("/", include_in_schema=False)
    async def root():
        return {"service": "AI Contract Summarizer", "docs": "/docs"}

    return app


app = create_app()


# ── Dev entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=True,    # set False in production
    )
