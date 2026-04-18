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
#   3. Checks Ollama is installed and pulls llama3
#   4. Creates the FAISS index directory
#   5. Starts the FastAPI service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "  AI Service Setup"
echo "=================================================="

cd "$PROJECT_DIR"

# ── 1. Virtual environment ────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "[1/5] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/5] Virtual environment already exists."
fi

source .venv/bin/activate

# ── 2. Install dependencies ───────────────────────────────────
echo "[2/5] Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "      Done."

# ── 3. Check Ollama ───────────────────────────────────────────
echo "[3/5] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "      ERROR: Ollama is not installed."
    echo "      Install from: https://ollama.com/download"
    echo "      Then run: ollama pull llama3"
    exit 1
fi

# Check if Ollama server is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "      Ollama not running. Starting Ollama in background..."
    ollama serve &
    sleep 3
fi

# Pull the model if not already present
MODEL=${OLLAMA_MODEL:-llama3}
echo "      Pulling model: $MODEL (this may take a few minutes on first run)..."
ollama pull "$MODEL"
echo "      Model ready."

# ── 4. Create data directories ────────────────────────────────
echo "[4/5] Creating data directories..."
mkdir -p ./data/faiss_indexes
echo "      Done."

# ── 5. Copy .env if missing ───────────────────────────────────
if [ ! -f ".env" ]; then
    echo "      No .env found — using defaults from .env template."
fi

# ── 6. Start service ──────────────────────────────────────────
echo "[5/5] Starting AI service on port 5000..."
echo "=================================================="
echo "  Service docs: http://localhost:5000/docs"
echo "  Spring Boot integration: set app.ai.service.enabled=true"
echo "=================================================="

exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 5000 \
    --log-level info \
    --reload
