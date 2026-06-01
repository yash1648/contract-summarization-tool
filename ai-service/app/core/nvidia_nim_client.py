"""
core/nvidia_nim_client.py
=========================
NVIDIA NIM (NVIDIA Inference Microservices) client using the OpenAI-compatible API.

API docs: https://docs.api.nvidia.com/nim/reference/llm-apis
Base URL: https://integrate.api.nvidia.com/v1
Auth:     Bearer token (nvapi-...) from https://build.nvidia.com/
"""

from __future__ import annotations

import json
import re
from typing import Optional

from loguru import logger
from openai import OpenAI, APITimeoutError, RateLimitError, APIStatusError

from app.config import settings


# ── Prompts (mirror ollama_client for consistency) ───────────────────────────

COMBINED_PROMPT = """\
You are a senior legal analyst. Analyse the contract excerpts below and produce TWO outputs separated by the exact delimiter ===RISK_JSON===.

CONTRACT EXCERPTS:
{context}

PART 1 — Write a concise structured summary:
- Parties Involved
- Contract Purpose  
- Key Obligations
- Payment Terms
- Duration & Renewal
- Termination Conditions
- Key Deadlines
Only use info from the excerpts. If missing, say "Not specified."

===RISK_JSON===

PART 2 — Return ONLY valid JSON (no markdown):
{{"riskScore":<0.0-10.0>,"penaltyClauses":["..."],"terminationRisks":["..."],"liabilityIssues":["..."],"otherFlags":["..."]}}
"""

CHUNK_SUMMARY_PROMPT = """\
You are a legal assistant. Summarize the key points of the following contract excerpt in 1-3 sentences.
Focus on factual legal obligations, terms, and conditions.

EXCERPT:
{chunk}
"""

MERGE_SUMMARY_PROMPT = """\
You are a legal assistant. Combine the following summaries of contract sections into a single cohesive summary.

SECTION SUMMARIES:
{context}
"""

FINAL_SUMMARY_PROMPT = """\
You are a senior legal analyst. Write a final, comprehensive, structured summary of the contract based on the provided section summaries.
Use the following structure:
- Parties Involved
- Contract Purpose  
- Key Obligations
- Payment Terms
- Duration & Renewal
- Termination Conditions
- Key Deadlines

If any information is missing, state "Not specified."

SECTION SUMMARIES:
{context}
"""

RISK_PROMPT = """\
You are a legal risk analyst. Return ONLY valid JSON:

CONTRACT EXCERPTS:
{context}

{{"riskScore":<0.0-10.0>,"penaltyClauses":["..."],"terminationRisks":["..."],"liabilityIssues":["..."],"otherFlags":["..."]}}
"""


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
        prompt = CHUNK_SUMMARY_PROMPT.format(chunk=chunk)
        logger.debug("Generating chunk summary via NVIDIA NIM")
        return self._chat(prompt).strip()

    def merge_summaries(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = MERGE_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Merging {len(summaries)} summaries via NVIDIA NIM")
        return self._chat(prompt).strip()

    def generate_final_summary(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = FINAL_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Generating final summary via NVIDIA NIM from {len(summaries)} merged summaries")
        return self._chat(prompt).strip()

    def generate_combined(self, context_chunks: list[str]) -> dict:
        context = self._format_context(context_chunks)
        prompt = COMBINED_PROMPT.format(context=context)
        logger.info(
            f"Generating COMBINED analysis via NVIDIA NIM with {len(context_chunks)} chunks "
            f"model={settings.nvidia_model}"
        )
        raw = self._chat(prompt)
        return self._parse_combined(raw)

    def generate_risk_analysis(self, context_chunks: list[str]) -> dict:
        context = self._format_context(context_chunks)
        prompt = RISK_PROMPT.format(context=context)
        logger.info(f"Generating risk analysis via NVIDIA NIM with {len(context_chunks)} chunks")
        raw = self._chat(prompt)
        return self._parse_risk_json(raw)

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

    def _parse_combined(self, raw: str) -> dict:
        """Parse the combined response split by ===RISK_JSON===."""
        delimiter = "===RISK_JSON==="

        if delimiter in raw:
            parts = raw.split(delimiter, 1)
            summary = parts[0].strip()
            risk_raw = parts[1].strip()
        else:
            json_match = re.search(r'\{[^{}]*"riskScore"[^{}]*\}', raw, re.DOTALL)
            if json_match:
                json_start = json_match.start()
                summary = raw[:json_start].strip()
                risk_raw = json_match.group(0)
            else:
                logger.warning("Could not split combined response, treating entire response as summary")
                summary = raw.strip()
                risk_raw = ""

        risk_data = self._parse_risk_json(risk_raw) if risk_raw else {
            "riskScore": 0.0,
            "penaltyClauses": [],
            "terminationRisks": [],
            "liabilityIssues": [],
            "otherFlags": [],
        }

        risk_data["summary"] = summary
        return risk_data

    @staticmethod
    def _format_context(chunks: list[str]) -> str:
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"--- EXCERPT {i} ---\n{chunk.strip()}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse_risk_json(raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse risk JSON: {e}\nRaw: {raw[:500]}")
            data = {}

        risk_score = float(data.get("riskScore", 0.0))
        risk_score = max(0.0, min(10.0, risk_score))

        def ensure_list(val):
            if isinstance(val, list):
                return [str(x) for x in val if x]
            return []

        return {
            "riskScore":        risk_score,
            "penaltyClauses":   ensure_list(data.get("penaltyClauses")),
            "terminationRisks": ensure_list(data.get("terminationRisks")),
            "liabilityIssues":  ensure_list(data.get("liabilityIssues")),
            "otherFlags":       ensure_list(data.get("otherFlags")),
        }


# Singleton
nvidia_nim_client = NVIDIANIMClient()
