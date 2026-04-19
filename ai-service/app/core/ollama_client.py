"""
core/ollama_client.py
=====================
Optimised Ollama client — performs summary + risk in a SINGLE LLM call.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import ollama
from loguru import logger

from app.config import settings


# ── Combined prompt — ONE call does everything ───────────────────────────────

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

# ── Client ───────────────────────────────────────────────────────────────────

class OllamaClient:

    def __init__(self):
        self._client = ollama.Client(host=settings.ollama_base_url)
        logger.info(
            f"OllamaClient initialised  host={settings.ollama_base_url}  "
            f"model={settings.ollama_model}"
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_chunk_summary(self, chunk: str) -> str:
        prompt = CHUNK_SUMMARY_PROMPT.format(chunk=chunk)
        logger.debug("Generating chunk summary")
        return self._chat(prompt).strip()

    def merge_summaries(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = MERGE_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Merging {len(summaries)} intermediate summaries")
        return self._chat(prompt).strip()

    def generate_final_summary(self, summaries: list[str]) -> str:
        context = "\n\n".join(f"Summary {i+1}:\n{s}" for i, s in enumerate(summaries))
        prompt = FINAL_SUMMARY_PROMPT.format(context=context)
        logger.info(f"Generating final structured summary from {len(summaries)} merged summaries")
        return self._chat(prompt).strip()

    def generate_combined(self, context_chunks: list[str]) -> dict:
        """
        Single LLM call that returns both summary text and risk JSON.
        Returns: {"summary": str, "riskScore": float, "penaltyClauses": [...], ...}
        """
        context = self._format_context(context_chunks)
        prompt = COMBINED_PROMPT.format(context=context)

        logger.info(
            f"Generating COMBINED analysis with {len(context_chunks)} chunks "
            f"model={settings.ollama_model}"
        )

        raw = self._chat(prompt)
        return self._parse_combined(raw)

    def generate_risk_analysis(self, context_chunks: list[str]) -> dict:
        context = self._format_context(context_chunks)
        prompt = RISK_PROMPT.format(context=context)
        logger.info(f"Generating risk analysis with {len(context_chunks)} chunks")
        raw = self._chat(prompt)
        return self._parse_risk_json(raw)

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

    def _parse_combined(self, raw: str) -> dict:
        """Parse the combined response split by ===RISK_JSON==="""
        delimiter = "===RISK_JSON==="
        
        if delimiter in raw:
            parts = raw.split(delimiter, 1)
            summary = parts[0].strip()
            risk_raw = parts[1].strip()
        else:
            # Fallback: try to find JSON block at the end
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
ollama_client = OllamaClient()