"""The model prompt and the checks that keep a model reading inside the rules.

Used identically by Bring-your-own-key (customer's model, locally) and Higashi Live
(managed model). The deterministic reading is always the fallback and the ceiling.
"""
from __future__ import annotations

import json
from typing import Any

from .crawlers import RAW_STANCE_TOKENS, stance_context
from .deterministic import clamp_recommendation, max_action, robots_paragraph
from .schemas import ReadingBody, ReportIn

SYSTEM_PROMPT = """You write the weekly Higashi Live reading from aggregate counts only.

Use high-school English and short sentences. Never use the words "leverage" or "insights". Do not use markdown headers. Keep all prose under 250 words. Return only valid JSON with: headline, paragraphs, verdict, changes, benchmarks.

The headline says what happened this week — the crawler that mattered and what it took. Never make the headline the owner's own setting; they already know what they chose. If the stance refuses nothing, lead with GEO mentions and citations, then say which crawlers may help discovery. Otherwise lead with the refused crawlers that came anyway, include a valid robots.txt block for exactly those, and name any known to ignore robots.txt.

The context gives "stance": what the owner chose, in "chose", with "means", "does_not_mean", "refuses" and "allows". Describe the choice in those words and those class names — "training crawlers", "search crawlers", "answer fetchers", "SEO tools" — and use "does_not_mean" when it matters. Never print an internal value such as search_only, block_all or refuse_training; they are plumbing and mean nothing to the reader.

Nothing here is enforced. A stance is what the owner asked for and a recommendation is a rule they would apply themselves, on their own server. Never write that a crawler will not be able to fetch, cannot reach, is prevented, or has been blocked or stopped — a crawler that ignores robots.txt keeps coming, and this report may already show one that did. Write "you can refuse", "the rule would ask them not to", "where you enforce it". Never claim that Live or Higashi blocked, stopped, or sits in front of traffic.

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


def model_context(report: ReportIn, changes: list[str], qualified: list[str], unavailable: list[str]) -> dict:
    """What the model is shown. The raw stance values are replaced by their labels here,
    so a leak needs the model to invent the word rather than copy it out of its input."""
    dumped = report.model_dump(mode="json")
    dumped.pop("ai_stance", None)
    dumped.pop("stance", None)
    return {
        "report": dumped,
        "stance": stance_context(report),
        "changes": changes,
        "qualified_benchmarks": qualified,
        "unavailable_benchmarks": unavailable,
        "max_action": max_action(report),
    }


# Higashi never enforces: the owner applies a rule on their own server, and a crawler
# that ignores robots.txt keeps arriving. Prose promising that a crawler is unable to
# fetch is therefore false as well as off-contract — a model wrote exactly that, and
# the same report showed GPTBot taking 420 records after ignoring robots.txt.
ENFORCEMENT_CLAIMS = (
    "will not be able to", "won't be able to", "will be unable to", "unable to fetch",
    "cannot fetch", "can't fetch", "cannot access", "can't access", "cannot crawl",
    "can't crawl", "cannot reach", "can't reach", "no longer be able to",
    "will be prevented", "is prevented", "are prevented", "will be denied",
    "will not fetch", "won't fetch", "will stop fetching", "have been blocked",
    "has been blocked", "is now blocked", "are now blocked",
)


# The same words are true when the owner has applied the rule themselves. A check that
# refused "where you enforce the refusal, training crawlers cannot fetch those pages"
# would throw away the one honest way to say it, so the qualifier is read too.
ENFORCEMENT_QUALIFIERS = (
    "where you enforce", "if you enforce", "when you enforce", "once you enforce",
    "where you apply", "if you apply", "when you apply", "once you apply",
    "where you add", "if you add", "where the rule", "where it is enforced",
    "where enforced", "would ask", "asks them not to",
)


def _sentences(text: str) -> list[str]:
    out, current = [], []
    for char in text:
        current.append(char)
        if char in ".!?":
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def enforcement_claim_in(reading: ReadingBody) -> str | None:
    """The unqualified promise of enforcement a reading made, if any.

    Judged per sentence: the claim is only a defect when the same sentence does not
    say the owner has to apply the rule for it to be true.
    """
    prose = " ".join([reading.headline, *reading.paragraphs, *reading.changes,
                      *reading.benchmarks, _recommendation_reason(reading)])
    for sentence in _sentences(prose):
        folded = sentence.casefold()
        if any(q in folded for q in ENFORCEMENT_QUALIFIERS):
            continue
        for claim in ENFORCEMENT_CLAIMS:
            if claim in folded:
                return claim
    return None


def _recommendation_reason(reading: ReadingBody) -> str:
    rec = reading.recommendation
    if isinstance(rec, dict):
        return rec.get("reason", "") or ""
    return getattr(rec, "reason", "") or ""


def raw_stance_token_in(reading: ReadingBody) -> str | None:
    """The internal stance value a reading leaked, if any.

    Asking the model not to print them is not a control; this is. A reading that names
    one is refused whole and the deterministic reading is served instead.
    """
    prose = " ".join([reading.headline, reading.verdict, *reading.paragraphs,
                      *reading.changes, *reading.benchmarks,
                      _recommendation_reason(reading)]).casefold()
    for token in RAW_STANCE_TOKENS:
        if token in prose:
            return token
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
    # The verdict is data, not prose: it is one of four strings the walk produced.
    # ReadingBody types it as a plain str for the model's sake, so nothing else stops
    # a model returning a sentence here — one did. Take the report's, as with changes.
    reading.verdict = report.walk.verdict
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
    if raw_stance_token_in(reading):
        return fallback
    if enforcement_claim_in(reading):
        return fallback
    # The rules set the ceiling; the model keeps its reason only under it.
    reading.recommendation = clamp_recommendation(reading.recommendation, report)
    return reading
