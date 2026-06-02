"""
core/prompts.py
===============
Shared prompt templates and response parsers for LLM clients.

All prompt templates live here so they are maintained in ONE place
instead of being duplicated across OllamaClient and NVIDIANIMClient.

Parsing helpers (_parse_combined, _parse_risk_json, _format_context)
are also shared to avoid duplicated logic.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from loguru import logger


# ════════════════════════════════════════════════════════════════════════════
#  COMBINED prompt — summary + risk in a single LLM call
# ════════════════════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════════════════════
#  EXTRACTION prompt — structured field extraction per chunk
#  Used by the extraction-first pipeline (rag_pipeline.extract).
#  Returns ONLY JSON — no summary, no ===RISK_JSON=== delimiter.
# ════════════════════════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """\
You are a senior legal analyst. Extract structured information from the following contract excerpt.

Return ONLY valid JSON (no markdown, no explanation) with these fields:
{{
  "parties": ["list of party names mentioned"],
  "obligations": ["key obligations or duties"],
  "payment_terms": ["payment amounts, schedules, methods"],
  "dates": ["effective dates, deadlines, durations"],
  "penalties": ["penalty clauses or financial consequences"],
  "termination": ["termination conditions or notice periods"],
  "other": ["any other notable legal provisions"]
}}

If a field has no relevant information, use an empty list [].

CONTRACT EXCERPT:
{chunk}
"""


# ════════════════════════════════════════════════════════════════════════════
#  CHUNK_SUMMARY prompt — one-chunk summarization
# ════════════════════════════════════════════════════════════════════════════

CHUNK_SUMMARY_PROMPT = """\
You are a legal assistant. Summarize the key points of the following contract excerpt in 1-3 sentences.
Focus on factual legal obligations, terms, and conditions.

EXCERPT:
{chunk}
"""


# ════════════════════════════════════════════════════════════════════════════
#  MERGE_SUMMARY prompt — combine multiple section summaries
# ════════════════════════════════════════════════════════════════════════════

MERGE_SUMMARY_PROMPT = """\
You are a legal assistant. Combine the following summaries of contract sections into a single cohesive summary.

SECTION SUMMARIES:
{context}
"""


# ════════════════════════════════════════════════════════════════════════════
#  FINAL_SUMMARY prompt — comprehensive structured summary
# ════════════════════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════════════════════
#  QA_PROMPT — answer a user question based on contract excerpts
# ════════════════════════════════════════════════════════════════════════════

QA_PROMPT = """\
You are a senior legal analyst. Answer the user's question based SOLELY on the contract excerpts provided below.

If the excerpts do NOT contain enough information to answer the question, say "The provided contract excerpts do not specify this." Do NOT make up or infer information.

CONTRACT EXCERPTS:
{context}

QUESTION: {query}

Provide a clear, concise answer. If you reference specific clauses, sections, or terms from the excerpts, mention them. If the information is spread across multiple excerpts, synthesise it into a single coherent response."""


# ════════════════════════════════════════════════════════════════════════════
#  RISK_PROMPT — risk analysis only (JSON output)
# ════════════════════════════════════════════════════════════════════════════

RISK_PROMPT = """\
You are a legal risk analyst. Return ONLY valid JSON:

CONTRACT EXCERPTS:
{context}

{{"riskScore":<0.0-10.0>,"penaltyClauses":["..."],"terminationRisks":["..."],"liabilityIssues":["..."],"otherFlags":["..."]}}
"""


# ════════════════════════════════════════════════════════════════════════════
#  Parsing helpers
# ════════════════════════════════════════════════════════════════════════════


def format_context(chunks: list[str]) -> str:
    """Format a list of chunk texts into labelled excerpts for prompts."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"--- EXCERPT {i} ---\n{chunk.strip()}")
    return "\n\n".join(parts)


def parse_combined(raw: str) -> dict:
    """
    Parse the combined response split by ===RISK_JSON===.

    Expected format:
        <summary text>
        ===RISK_JSON===
        {"riskScore": ..., "penaltyClauses": [...], ...}

    Falls back to locating a JSON block if the delimiter is missing.
    """
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

    risk_data = parse_risk_json(risk_raw) if risk_raw else {
        "riskScore": 0.0,
        "penaltyClauses": [],
        "terminationRisks": [],
        "liabilityIssues": [],
        "otherFlags": [],
    }

    risk_data["summary"] = summary
    return risk_data


def parse_risk_json(raw: str) -> dict:
    """
    Parse risk JSON from raw LLM output, handling markdown fences and
    arbitrary text wrapping.
    """
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


def parse_extraction(raw: str) -> dict:
    """
    Parse extraction JSON from the extraction pipeline.

    Expected format:
        {"parties": [...], "obligations": [...], "payment_terms": [...], ...}

    Returns a dict with all expected fields defaulting to empty lists.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()

    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extraction JSON: {e}\nRaw: {raw[:500]}")
        data = {}

    def ensure_list(val):
        if isinstance(val, list):
            return [str(x) for x in val if x]
        return []

    return {
        "parties":        ensure_list(data.get("parties")),
        "obligations":    ensure_list(data.get("obligations")),
        "payment_terms":  ensure_list(data.get("payment_terms")),
        "dates":          ensure_list(data.get("dates")),
        "penalties":      ensure_list(data.get("penalties")),
        "termination":    ensure_list(data.get("termination")),
        "other":          ensure_list(data.get("other")),
    }
