"""The model prompt and the checks that keep a model reading inside the rules.

Used identically by Bring-your-own-key (customer's model, locally) and Higashi Live
(managed model). The deterministic reading is always the fallback and the ceiling.
"""
from __future__ import annotations

import json
from typing import Any

from .deterministic import clamp_recommendation, max_action, robots_paragraph
from .schemas import ReadingBody, ReportIn

SYSTEM_PROMPT = """You write the weekly Higashi Live reading from aggregate counts only.

Use high-school English and short sentences. Never use the words "leverage" or "insights". Do not use markdown headers. Keep all prose under 250 words. Return only valid JSON with: headline, paragraphs, verdict, changes, benchmarks.

The headline is the verdict. If the owner wants to be found, lead with GEO mentions and citations, then say which crawlers may help discovery. If the owner chose block_all, lead with the AI crawlers that came, include a valid robots.txt block for them, and name crawlers known to ignore robots.txt. Never claim that Live blocked, stopped, or sits in front of traffic. If the owner chose search_only, treat search crawlers as acceptable and list AI training crawlers to block.

Use only supplied benchmark text. Every compared number must state the typical value. When a comparison is unavailable, say "not enough sites yet to compare". Never invent a typical value.

Use walk wording exactly: "Catalogue walk detected", "Suspicious", "No walk detected", or "Insufficient data". No walk detected does not prove copying did not happen. Call weak signals weak. Preserve the supplied changes exactly.

Also return "recommendation": {"action": one of none | observe | robots | rate_rule | block_rule, "reason": one or two sentences, "confidence": low | medium | high}. The context gives "max_action": you may choose that action or a weaker one, never a stronger one. Say what the step would change, what it would not, and that the owner applies it, not Higashi.

JSON shape: {"headline":"...","paragraphs":["..."],"verdict":"...","changes":["..."],"benchmarks":["..."],"recommendation":{"action":"...","reason":"...","confidence":"..."}}."""


def parse_model_json(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def constrain_model_reading(
    reading: ReadingBody,
    fallback: ReadingBody,
    report: ReportIn,
    changes: list[str],
    benchmarks: list[str],
    product: str = "Higashi",
) -> ReadingBody:
    """Accept the model's prose only where it stayed inside the rules; otherwise the rules win."""
    reading.changes = changes
    reading.benchmarks = benchmarks
    if report.ai_stance == "block_all" and not any("User-agent:" in p and "Disallow: /" in p for p in reading.paragraphs):
        reading.paragraphs.append(robots_paragraph(report, product))
    if not benchmarks and any("typical for a site" in p.casefold() for p in reading.paragraphs):
        return fallback
    if any(product.casefold() in p.casefold() and any(word in p.casefold() for word in (" blocked", " blocks", " stopped", " stops")) for p in reading.paragraphs):
        return fallback
    if any("live" in p.casefold() and any(word in p.casefold() for word in (" blocked", " blocks", " stopped", " stops")) for p in reading.paragraphs):
        return fallback
    if sum(len(value.split()) for value in [reading.headline, reading.verdict, *reading.paragraphs, *reading.changes, *reading.benchmarks]) > 250:
        return fallback
    # The rules set the ceiling; the model keeps its reason only under it.
    reading.recommendation = clamp_recommendation(reading.recommendation, report)
    return reading
