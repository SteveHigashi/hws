"""The walk reading in the free product: local rules, or the customer's own model key.

Both run on this install and send nothing anywhere. The rules (higashi_reading) are
the ceiling: a model may write the prose, it cannot escalate past what the rules
say. Higashi Live is the third provider and is handled by routers/live.py; nothing
here ever calls it.
"""
from __future__ import annotations

import json
import logging

from higashi_reading import (
    ReadingBody,
    ReportIn,
    SYSTEM_PROMPT,
    constrain_model_reading,
    model_context,
    deterministic_reading,
    max_action,
    no_comparison_notes,
    parse_model_json,
)
from services.ai_providers import call_model, get_provider

log = logging.getLogger("higashi.walk_reading")
PRODUCT = "Higashi"
PROVIDERS = ("local", "byok", "live")


def local_reading(report: dict) -> ReadingBody:
    """The rule-based reading from this install's own counts. No key, no network."""
    return deterministic_reading(ReportIn.model_validate(report), product=PRODUCT)


async def byok_reading(report: dict, model: str, api_keys: dict) -> tuple[ReadingBody, str, str | None]:
    """The same prompt Live uses, through the customer's own provider key, locally.

    Returns (reading, provider_used, note). Falls back to the local rules — and says
    so in `note` — when no key is set for the model's provider, the call fails, or the
    model wrote outside the rules.
    """
    parsed_report = ReportIn.model_validate(report)
    fallback = deterministic_reading(parsed_report, product=PRODUCT)
    provider = get_provider(model)
    if not api_keys.get(provider):
        return fallback, "local", f"No {provider} key is set on this install; showing the rule-based reading."
    context = model_context(parsed_report, [], [], no_comparison_notes(parsed_report))
    try:
        text, _in, _out = await call_model(model, SYSTEM_PROMPT, json.dumps(context, separators=(",", ":")), api_keys)
    except Exception as exc:  # the customer's key, quota or network — never a 500 on the dashboard
        log.warning("byok reading failed: %s", exc)
        return fallback, "local", "Your model key did not answer; showing the rule-based reading."
    parsed = parse_model_json(text)
    if not parsed:
        return fallback, "local", "Your model returned something unreadable; showing the rule-based reading."
    try:
        reading = ReadingBody.model_validate(parsed)
    except Exception:
        return fallback, "local", "Your model returned the wrong shape; showing the rule-based reading."
    constrained = constrain_model_reading(reading, fallback, parsed_report, [], [], product=PRODUCT)
    if constrained is fallback:
        return fallback, "local", "Your model wrote outside the rules; showing the rule-based reading."
    return constrained, "byok", None
