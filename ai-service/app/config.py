"""
config.py
=========
Central configuration loaded from environment variables / .env file.
All other modules import `settings` from here — no scattered os.getenv() calls.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from pathlib import Path
import json


class Settings(BaseSettings):

    # ── Server ───────────────────────────────────────────────
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(5000, env="PORT")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # ── Embedding model ──────────────────────────────────────
    embedding_model: str = Field("all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(384, env="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(32, env="EMBEDDING_BATCH_SIZE")

    # ── FAISS persistence ────────────────────────────────────
    faiss_index_dir: Path = Field("./data/faiss_indexes", env="FAISS_INDEX_DIR")

    # ── Ollama ───────────────────────────────────────────────
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field("kimi-k2.6:cloud", env="OLLAMA_MODEL")
    ollama_max_tokens: int = Field(1024, env="OLLAMA_MAX_TOKENS")
    ollama_temperature: float = Field(0.1, env="OLLAMA_TEMPERATURE")

    # ── Extraction-first pipeline (lightweight model) ─────
    extraction_model: str = Field("phi3:3.8b", env="EXTRACTION_MODEL")
    extraction_temperature: float = Field(0.1, env="EXTRACTION_TEMPERATURE")
    extraction_max_tokens: int = Field(512, env="EXTRACTION_MAX_TOKENS")

    # ── Sentence filtering ────────────────────────────────
    similarity_threshold: float = Field(0.5, env="SIMILARITY_THRESHOLD")
    max_sentences_per_chunk: int = Field(10, env="MAX_SENTENCES_PER_CHUNK")

    # ── Query embeddings for sentence filtering ───────────
    # Stored as JSON string in env, parsed here
    filter_queries_json: str = Field(
        default='["payment terms","termination clause","penalty","obligations","liability","dates deadlines","parties involved"]',
        env="FILTER_QUERIES_JSON",
    )

    # ── RAG ──────────────────────────────────────────────────
    rag_top_k: int = Field(7, env="RAG_TOP_K")
    rag_min_score: float = Field(0.30, env="RAG_MIN_SCORE")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ── Computed fields ──────────────────────────────────────
    _filter_queries: list[str] | None = None

    @property
    def filter_queries(self) -> list[str]:
        """Lazy-load and cache filter queries from JSON string."""
        if self._filter_queries is None:
            try:
                self._filter_queries = json.loads(self.filter_queries_json)
            except (json.JSONDecodeError, TypeError):
                # Fallback to default
                self._filter_queries = [
                    "payment terms",
                    "termination clause",
                    "penalty",
                    "obligations",
                    "liability",
                    "dates deadlines",
                    "parties involved",
                ]
        return self._filter_queries

    # Singleton instance imported by all modules
settings = Settings()

    # Ensure directories exist
settings.faiss_index_dir.mkdir(parents=True, exist_ok=True)
