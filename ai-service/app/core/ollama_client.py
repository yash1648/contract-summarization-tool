"""
core/ollama_client.py
=====================
Optimised Ollama client — performs summary + risk in a SINGLE LLM call.

Prompts and response parsers are now in core/prompts.py (shared across
OllamaClient and NVIDIANIMClient).
"""

from __future__ import annotations

from typing import Optional

import ollama
from loguru import logger

from app.config import settings
from app.core import prompts


class OllamaClient:

    def __init__(self):
        self._client = ollama.Client(host=settings.ollama_base_url)
        logger.info(
            f"OllamaClient initialised  host={settings.ollama_base_url}  "
            f"model={settings.ollama_model}"
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_chunk_summary(self, chunk: str) -> str:
        prompt = prompts.CHUNK_SUMMARY_PROMPT.format(chunk=chunk)
        logger.debug("Generating chunk summary")
        return self._chat(prompt).strip()

    def merge_summaries(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = prompts.MERGE_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Merging {len(summaries)} intermediate summaries")
        return self._chat(prompt).strip()

    def generate_final_summary(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = prompts.FINAL_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Generating final structured summary from {len(summaries)} merged summaries")
        return self._chat(prompt).strip()

    def generate_combined(self, context_chunks: list[str]) -> dict:
        """
        Single LLM call that returns both summary text and risk JSON.
        Returns: {"summary": str, "riskScore": float, "penaltyClauses": [...], ...}
        """
        context = prompts.format_context(context_chunks)
        prompt = prompts.COMBINED_PROMPT.format(context=context)

        logger.info(
            f"Generating COMBINED analysis with {len(context_chunks)} chunks "
            f"model={settings.ollama_model}"
        )

        raw = self._chat(prompt)
        return prompts.parse_combined(raw)

    def generate_risk_analysis(self, context_chunks: list[str]) -> dict:
        context = prompts.format_context(context_chunks)
        prompt = prompts.RISK_PROMPT.format(context=context)
        logger.info(f"Generating risk analysis with {len(context_chunks)} chunks")
        raw = self._chat(prompt)
        return prompts.parse_risk_json(raw)

    def generate_extraction(self, chunk_text: str) -> dict:
        """
        Extract structured fields from a single chunk using the extraction prompt.
        Used by the extraction-first pipeline.
        """
        prompt = prompts.EXTRACTION_PROMPT.format(chunk=chunk_text)
        logger.debug("Generating extraction analysis")
        raw = self._chat(prompt)
        return prompts.parse_extraction(raw)

    def is_reachable(self) -> bool:
        """
        Check if Ollama is reachable and model is available.
        Supports both dict and object responses.
        """
        try:
            models = self._client.list()

            if isinstance(models, dict):
                model_list = models.get("models", [])
                names = [m.get("name", "") for m in model_list]
            else:
                model_list = getattr(models, "models", [])
                names = [getattr(m, "model", "") for m in model_list]

            reachable = any(settings.ollama_model in n for n in names)

            if not reachable:
                logger.warning(
                    f"Ollama is up but model '{settings.ollama_model}' not found. "
                    f"Available: {names}. Run: ollama pull {settings.ollama_model}"
                )

            return reachable

        except Exception as e:
            logger.warning(f"Ollama not reachable: {e}")
            return False

    # ── Private helpers ──────────────────────────────────────────────────────

    def _chat(self, prompt: str) -> str:
        response = self._client.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": settings.ollama_temperature,
                "num_predict": settings.ollama_max_tokens,
            },
        )

        # Handle dict vs object response safely
        if isinstance(response, dict):
            return response.get("message", {}).get("content", "")

        return response.message.content


# Singleton
ollama_client = OllamaClient()
