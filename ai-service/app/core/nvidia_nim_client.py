"""
core/nvidia_nim_client.py
=========================
NVIDIA NIM (NVIDIA Inference Microservices) client using the OpenAI-compatible API.

API docs: https://docs.api.nvidia.com/nim/reference/llm-apis
Base URL: https://integrate.api.nvidia.com/v1
Auth:     Bearer token (nvapi-...) from https://build.nvidia.com/

Prompts and response parsers are in core/prompts.py (shared with OllamaClient).
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from openai import OpenAI, APITimeoutError, RateLimitError, APIStatusError

from app.config import settings
from app.core import prompts


class NVIDIANIMClient:
    """
    Client for NVIDIA NIM hosted inference API.
    Uses the OpenAI Python SDK with a custom base_url.
    """

    def __init__(self):
        self._client: OpenAI | None = None
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Create the OpenAI client. No-op if already loaded or key is missing."""
        if self._loaded:
            return

        key = settings.nvidia_api_key
        if not key:
            logger.warning(
                "NVIDIA_API_KEY is not set — NVIDIA NIM client will not be available. "
                "Set NVIDIA_API_KEY in .env or fallback to Ollama."
            )
            self._loaded = True  # Mark loaded so we don't retry every call
            return

        self._client = OpenAI(
            base_url=settings.nvidia_base_url,
            api_key=key,
            timeout=settings.nvidia_timeout,
            max_retries=2,
        )
        self._loaded = True
        logger.info(
            f"NVIDIANIMClient ready  model={settings.nvidia_model}  "
            f"base_url={settings.nvidia_base_url}"
        )

    def is_available(self) -> bool:
        """Check if the client is configured and the API is reachable."""
        if not self._loaded:
            self.load()
        if self._client is None:
            return False
        try:
            models = self._client.models.list()
            return any(settings.nvidia_model in m.id for m in models)
        except Exception as e:
            logger.debug(f"NVIDIA NIM not available: {e}")
            return False

    # ── Public API (mirrors OllamaClient interface) ──────────────────────────

    def generate_chunk_summary(self, chunk: str) -> str:
        prompt = prompts.CHUNK_SUMMARY_PROMPT.format(chunk=chunk)
        logger.debug("Generating chunk summary via NVIDIA NIM")
        return self._chat(prompt).strip()

    def merge_summaries(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = prompts.MERGE_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Merging {len(summaries)} summaries via NVIDIA NIM")
        return self._chat(prompt).strip()

    def generate_final_summary(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = prompts.FINAL_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Generating final summary via NVIDIA NIM from {len(summaries)} merged summaries")
        return self._chat(prompt).strip()

    def generate_combined(self, context_chunks: list[str]) -> dict:
        context = prompts.format_context(context_chunks)
        prompt = prompts.COMBINED_PROMPT.format(context=context)
        logger.info(
            f"Generating COMBINED analysis via NVIDIA NIM with {len(context_chunks)} chunks "
            f"model={settings.nvidia_model}"
        )
        raw = self._chat(prompt)
        return prompts.parse_combined(raw)

    def generate_risk_analysis(self, context_chunks: list[str]) -> dict:
        context = prompts.format_context(context_chunks)
        prompt = prompts.RISK_PROMPT.format(context=context)
        logger.info(f"Generating risk analysis via NVIDIA NIM with {len(context_chunks)} chunks")
        raw = self._chat(prompt)
        return prompts.parse_risk_json(raw)

    def generate_answer(self, query: str, context_chunks: list[str]) -> str:
        """
        Synthesise a concise answer to the user's query from the given chunks.
        Used by the Q&A search endpoint.
        """
        context = prompts.format_context(context_chunks)
        prompt = prompts.QA_PROMPT.format(context=context, query=query)
        logger.info(f"Generating Q&A answer via NVIDIA NIM  query='{query}'  chunks={len(context_chunks)}")
        return self._chat(prompt).strip()

    def generate_extraction(self, chunk_text: str) -> dict:
        """
        Extract structured fields from a single chunk using the extraction prompt.
        Used by the extraction-first pipeline.
        """
        prompt = prompts.EXTRACTION_PROMPT.format(chunk=chunk_text)
        logger.debug("Generating extraction analysis via NVIDIA NIM")
        raw = self._chat(prompt)
        return prompts.parse_extraction(raw)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _chat(self, prompt: str) -> str:
        """Send a chat completion request to NVIDIA NIM."""
        if self._client is None:
            self.load()
        if self._client is None:
            raise ConnectionError(
                "NVIDIA NIM client is not configured (NVIDIA_API_KEY missing). "
                "Use fallback provider instead."
            )

        response = self._client.chat.completions.create(
            model=settings.nvidia_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.nvidia_temperature,
            max_tokens=settings.nvidia_max_tokens,
            stream=False,
        )

        return response.choices[0].message.content or ""


# Singleton
nvidia_nim_client = NVIDIANIMClient()
