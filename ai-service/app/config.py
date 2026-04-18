"""
config.py
=========
Central configuration loaded from environment variables / .env file.
All other modules import `settings` from here — no scattered os.getenv() calls.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


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
    ollama_model: str = Field("llama3", env="OLLAMA_MODEL")
    ollama_max_tokens: int = Field(1024, env="OLLAMA_MAX_TOKENS")
    ollama_temperature: float = Field(0.1, env="OLLAMA_TEMPERATURE")

    # ── RAG ──────────────────────────────────────────────────
    rag_top_k: int = Field(7, env="RAG_TOP_K")
    rag_min_score: float = Field(0.30, env="RAG_MIN_SCORE")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton instance imported by all modules
settings = Settings()

# Ensure directories exist
settings.faiss_index_dir.mkdir(parents=True, exist_ok=True)
