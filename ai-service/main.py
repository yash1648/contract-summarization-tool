"""
main.py
=======
FastAPI application entry point.

Startup sequence:
  1. Start HTTP server immediately (<1 s)
  2. Load embedding model in background thread (avoids blocking startup for 5-15 s)
  3. Check LLM connectivity in background thread
  4. Restore any persisted FAISS indexes from disk (fast, happens during import)
  5. Mount API router

Run with:
    uvicorn main:app --host 0.0.0.0 --port 5000 --reload
"""
from contextlib import asynccontextmanager
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.routes import router
from app.core.embedder import embedder
from app.core.llm_client import llm_client
from app.core.vector_store import vector_store


# ── Background init tracking ───────────────────────────────────────────────

_startup_ready = threading.Event()
"""Set after background init (embedder + LLM check) completes."""


def _background_init() -> None:
    """Run heavy startup tasks in a background thread so the HTTP server
    starts serving immediately (<1 s) instead of blocking for 5-20 s."""
    # 1. Load embedding model (5-15 s even from HuggingFace cache)
    logger.info("Background init: loading embedding model…")
    embedder.load()

    # 2. FAISS indexes are loaded in VectorStore.__init__() (fast)
    logger.info(f"Background init: FAISS indexes loaded: {vector_store.total_indexes()}")

    # 3. Check LLM provider connectivity (NVIDIA NIM → Ollama fallback)
    if llm_client.is_reachable():
        if settings.nvidia_api_key:
            logger.info(f"Background init: NVIDIA NIM OK  model={settings.nvidia_model}")
        else:
            logger.info(f"Background init: Ollama OK  model={settings.ollama_model}")
    else:
        logger.warning(
            "Background init: No LLM provider reachable. "
            "Set NVIDIA_API_KEY for cloud inference or start Ollama for local inference. "
            "Embedding and search will work, but LLM calls will fail."
        )

    _startup_ready.set()
    logger.info(f"AI service fully ready on http://{settings.host}:{settings.port}")


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
    logger.info("Server will be available in <1 s; background init may take 5-20 s more.")

    # Launch heavy init in a background thread (daemon = won't block shutdown)
    threading.Thread(target=_background_init, daemon=True, name="ai-background-init").start()

    yield   # ← application runs here immediately

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

    # CORS — allow requests from Spring Boot (localhost:8080) and Docker service (springboot:8080)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://springboot:8080"],
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
    import os
    is_dev = os.getenv("ENV", "development").lower() in ("development", "dev", "")
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=is_dev,
    )
