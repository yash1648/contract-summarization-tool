"""
core/ollama_client.py
=====================
Thin async wrapper around the Ollama Python SDK.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import ollama
from loguru import logger

from app.config import settings


# ── Prompt templates ─────────────────────────────────────────────────────────

SUMMARY_PROMPT = """\
You are a senior legal analyst. You have been given excerpts from a legal contract.
Your task is to write a clear, concise, structured summary of the contract.

CONTRACT EXCERPTS:
{context}

Write a structured summary covering:
1. Parties Involved
2. Contract Purpose
3. Key Obligations (each party)
4. Payment Terms (if any)
5. Duration and Renewal
6. Termination Conditions
7. Key Deadlines

Be factual and concise. Only use information present in the excerpts.
If information is not available in the excerpts, state "Not specified in reviewed sections."
"""

RISK_PROMPT = """\
You are a senior legal risk analyst. Analyse the following contract excerpts for legal risks.

CONTRACT EXCERPTS:
{context}

Identify and list all risky clauses in the following JSON format ONLY.
Return nothing but valid JSON — no markdown, no explanation:

{{
  "riskScore": <float 0.0-10.0>,
  "penaltyClauses": ["..."],
  "terminationRisks": ["..."],
  "liabilityIssues": ["..."],
  "otherFlags": ["..."]
}}
"""


# ── Client ───────────────────────────────────────────────────────────────────

class OllamaClient:

    def __init__(self):
        self._client = ollama.Client(host=settings.ollama_base_url)
        logger.info(
            f"OllamaClient initialised  host={settings.ollama_base_url}  "
            f"model={settings.ollama_model}"
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_summary(self, context_chunks: list[str]) -> str:
        context = self._format_context(context_chunks)
        prompt = SUMMARY_PROMPT.format(context=context)

        logger.info(
            f"Generating summary with {len(context_chunks)} chunks "
            f"model={settings.ollama_model}"
        )

        response = self._chat(prompt)
        return response.strip()

    def generate_risk_analysis(self, context_chunks: list[str]) -> dict:
        context = self._format_context(context_chunks)
        prompt = RISK_PROMPT.format(context=context)

        logger.info(
            f"Generating risk analysis with {len(context_chunks)} chunks "
            f"model={settings.ollama_model}"
        )

        raw = self._chat(prompt)
        return self._parse_risk_json(raw)

    def is_reachable(self) -> bool:
        """
        Check if Ollama is reachable and model is available.
        Supports both dict and object responses.
        """
        try:
            models = self._client.list()

            # 🔥 Handle BOTH response types
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

        # 🔥 Handle dict vs object response safely
        if isinstance(response, dict):
            return response.get("message", {}).get("content", "")

        return response.message.content

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
ollama_client = OllamaClient()