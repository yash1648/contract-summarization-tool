"""
core/llm_client.py
===================
Unified LLM client with automatic fallback: NVIDIA NIMs (primary) → Ollama (local).

Fallback strategy:
  Tier 1: NVIDIA NIMs (cloud, fast, high-quality)
    ↓ on failure (timeout, rate-limit, 5xx)
  Tier 2: Ollama (local, degraded but functional)

Circuit breaker:
  - Tracks consecutive failures per provider
  - After MAX_CONSECUTIVE_FAILURES, cools down the provider for COOLDOWN_SECONDS
  - On success, resets the failure counter

All public methods mirror the original OllamaClient interface so this is a
drop-in replacement for both `ollama_client` and `nvidia_nim_client`.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from loguru import logger

from app.config import settings
from app.core.ollama_client import ollama_client
from app.core.nvidia_nim_client import nvidia_nim_client


# ── Circuit breaker settings ─────────────────────────────────────────────────

MAX_CONSECUTIVE_FAILURES = 3
COOLDOWN_SECONDS = 30


class _ProviderState:
    """Tracks health of a single LLM provider."""

    def __init__(self, name: str):
        self.name = name
        self.consecutive_failures = 0
        self.cooldown_until: float = 0.0

    @property
    def is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            self.cooldown_until = time.time() + COOLDOWN_SECONDS
            logger.warning(
                f"[llm] {self.name} circuit OPEN — cooling down for {COOLDOWN_SECONDS}s "
                f"({self.consecutive_failures} consecutive failures)"
            )

    def reset_cooldown(self) -> None:
        self.cooldown_until = 0.0
        self.consecutive_failures = 0


# ── Unified client ───────────────────────────────────────────────────────────

class LLMClient:
    """
    Unified LLM client with NVIDIA NIMs primary + Ollama fallback.

    Exposes the same methods as the original OllamaClient:
      - generate_chunk_summary(chunk)         → str
      - merge_summaries(summaries)            → str
      - generate_final_summary(summaries)     → str
      - generate_combined(context_chunks)     → dict
      - generate_risk_analysis(context_chunks) → dict
      - is_reachable()                        → bool
    """

    def __init__(self):
        self._nvidia = _ProviderState("nvidia")
        self._ollama = _ProviderState("ollama")
        self._nvidia_loaded = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def _ensure_nvidia_loaded(self) -> None:
        """Lazy-load the NVIDIA NIM client (don't fail if key is missing)."""
        if not self._nvidia_loaded:
            nvidia_nim_client.load()
            self._nvidia_loaded = True

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_chunk_summary(self, chunk: str) -> str:
        return self._with_fallback(
            nvidia_fn=lambda: nvidia_nim_client.generate_chunk_summary(chunk),
            ollama_fn=lambda: ollama_client.generate_chunk_summary(chunk),
            operation="generate_chunk_summary",
        )

    def merge_summaries(self, summaries: list[str]) -> str:
        return self._with_fallback(
            nvidia_fn=lambda: nvidia_nim_client.merge_summaries(summaries),
            ollama_fn=lambda: ollama_client.merge_summaries(summaries),
            operation="merge_summaries",
        )

    def generate_final_summary(self, summaries: list[str]) -> str:
        return self._with_fallback(
            nvidia_fn=lambda: nvidia_nim_client.generate_final_summary(summaries),
            ollama_fn=lambda: ollama_client.generate_final_summary(summaries),
            operation="generate_final_summary",
        )

    def generate_combined(self, context_chunks: list[str]) -> dict:
        return self._with_fallback(
            nvidia_fn=lambda: nvidia_nim_client.generate_combined(context_chunks),
            ollama_fn=lambda: ollama_client.generate_combined(context_chunks),
            operation="generate_combined",
        )

    def generate_risk_analysis(self, context_chunks: list[str]) -> dict:
        return self._with_fallback(
            nvidia_fn=lambda: nvidia_nim_client.generate_risk_analysis(context_chunks),
            ollama_fn=lambda: ollama_client.generate_risk_analysis(context_chunks),
            operation="generate_risk_analysis",
        )

    def is_reachable(self) -> bool:
        """Check if at least one provider is reachable (NVIDIA preferred)."""
        self._ensure_nvidia_loaded()

        if not self._nvidia.is_in_cooldown:
            try:
                if nvidia_nim_client.is_available():
                    return True
            except Exception:
                pass

        # Fallback to Ollama check
        return ollama_client.is_reachable()

    # ── Fallback logic ───────────────────────────────────────────────────────

    def _with_fallback(
        self,
        nvidia_fn: Callable,
        ollama_fn: Callable,
        operation: str,
    ) -> any:
        """
        Execute with fallback:
          1. Try NVIDIA NIMs (if configured and not in cooldown)
          2. On failure → try Ollama
          3. If both fail → raise RuntimeError
        """
        self._ensure_nvidia_loaded()
        last_error: Optional[Exception] = None

        # ── Tier 1: NVIDIA NIMs ──────────────────────────────────────────────
        if not self._nvidia.is_in_cooldown and settings.nvidia_api_key:
            try:
                result = nvidia_fn()
                self._nvidia.record_success()
                logger.debug(f"[llm] {operation} → NVIDIA NIM OK")
                return result
            except Exception as e:
                last_error = e
                self._nvidia.record_failure()
                logger.warning(
                    f"[llm] {operation} → NVIDIA NIM failed: {self._simplify_error(e)}"
                )

        # ── Tier 2: Ollama (local fallback) ──────────────────────────────────
        if not self._ollama.is_in_cooldown:
            try:
                result = ollama_fn()
                self._ollama.record_success()
                logger.info(f"[llm] {operation} → Ollama fallback OK")
                return result
            except Exception as e:
                last_error = e
                self._ollama.record_failure()
                logger.warning(
                    f"[llm] {operation} → Ollama fallback also failed: {self._simplify_error(e)}"
                )

        # ── Both providers failed ────────────────────────────────────────────
        error_msg = (
            f"[llm] {operation} → ALL providers failed after fallback. "
            f"NVIDIA cooldown={'ON' if self._nvidia.is_in_cooldown else 'OFF'}, "
            f"Ollama cooldown={'ON' if self._ollama.is_in_cooldown else 'OFF'}. "
            f"Last error: {self._simplify_error(last_error)}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _simplify_error(e: Optional[Exception]) -> str:
        if e is None:
            return "unknown error"
        msg = str(e)
        if "Connection refused" in msg:
            return "Connection refused — service not running"
        if "timeout" in msg.lower():
            return "Request timed out"
        if "401" in msg:
            return "Authentication failed (check API key)"
        if "429" in msg:
            return "Rate limited"
        return msg[:150] if len(msg) > 150 else msg


# Singleton — drop-in replacement for `ollama_client`
llm_client = LLMClient()
