#!/usr/bin/env bash
# =============================================================
#  AI Contract Summarization Service — Setup & Launch Script
# =============================================================
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# What this does:
#   1. Creates a Python virtual environment
#   2. Installs all dependencies
#   3. Pre-downloads the sentence-transformers embedding model (~90 MB)
#   4. Checks Ollama is installed and pulls the configured model (~2.3 GB)
#   5. Creates the FAISS index directory
#   6. Starts the FastAPI service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "  AI Service Setup"
echo "=================================================="

cd "$PROJECT_DIR"

# ── 0. Load .env if present (so OLLAMA_MODEL etc are picked up) ──
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# ── 1. Virtual environment ────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "[1/6] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/6] Virtual environment already exists."
fi

source .venv/bin/activate

# ── 2. Install dependencies ───────────────────────────────────
echo "[2/6] Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "      Done."

# ── 3. Pre-download embedding model ───────────────────────────
EMBEDDING_MODEL="${EMBEDDING_MODEL:-all-MiniLM-L6-v2}"
LOCAL_MODEL_DIR="./models/all-MiniLM-L6-v2"
if [ -f "$LOCAL_MODEL_DIR/model.safetensors" ]; then
    echo "[3/6] Embedding model already cached at $LOCAL_MODEL_DIR"
else
    echo "[3/6] Downloading embedding model into project directory (~90 MB)..."
    python3 -c "
from sentence_transformers import SentenceTransformer
print('      Downloading $EMBEDDING_MODEL...')
m = SentenceTransformer('$EMBEDDING_MODEL')
m.save('$LOCAL_MODEL_DIR')
# Quick warm-up encode so first runtime use is fast
test = m.encode(['warm-up'])
print(f'      Saved to $LOCAL_MODEL_DIR/  dim={test.shape[1]}  device={m.device}')
"
    echo "      Done."
fi

# ── 4. Check Ollama ───────────────────────────────────────────
OLLAMA_MODEL="${OLLAMA_MODEL:-phi3:3.8b}"
echo "[4/6] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "      ERROR: Ollama is not installed."
    echo "      Install from: https://ollama.com/download"
    echo "      Then run: ollama pull ${OLLAMA_MODEL}"
    exit 1
fi

# Check if Ollama server is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "      Ollama not running. Starting Ollama in background..."
    ollama serve &
    sleep 3
fi

# Pull the model if not already present
echo "      Pulling model: $OLLAMA_MODEL (may take a few minutes on first run)..."
ollama pull "$OLLAMA_MODEL"
echo "      Model ready."

# ── 5. Create data directories ────────────────────────────────
echo "[5/6] Creating data directories..."
mkdir -p ./data/faiss_indexes
echo "      Done."

# ── 6. Start service ──────────────────────────────────────────
echo "[6/6] Starting AI service on port 5000..."
echo "=================================================="
echo "  Service docs: http://localhost:5000/docs"
echo "  Spring Boot integration: set app.ai.service.enabled=true"
echo "=================================================="

exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 5000 \
    --log-level info \
    --reload
