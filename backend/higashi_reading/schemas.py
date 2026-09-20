"""Report and reading shapes shared by the free product and Higashi Live.

Pure pydantic, no database, no network. The privacy validator on ReportIn is the
same on both sides on purpose: what the free product may build locally is exactly
what Live may receive.
"""
from __future__ import annotations

from datetime import date
import ipaddress
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


_UA_MARKERS = re.compile(
    r"(?:mozilla/\d|applewebkit/|chrome/\d|safari/\d|firefox/\d|curl/\d|wget/\d|user-agent\s*:)",
    re.IGNORECASE,
)
_PATH_MARKERS = re.compile(r"^(?:/|\.{1,2}/|[A-Za-z]:\\)")


def _private_string(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    try:
        ipaddress.ip_address(candidate.strip("[]"))
        return True
    except ValueError:
        pass
    if re.search(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])", candidate):
        return True
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() in {"http", "https", "ftp"} and parsed.netloc:
        return True
    looks_like_markup = bool(re.search(r"<!doctype|</?[a-z][^>]*>", candidate, re.IGNORECASE))
    contains_path_separator = "/" in candidate or "\\" in candidate
    return bool(_PATH_MARKERS.search(candidate) or _UA_MARKERS.search(candidate) or looks_like_markup or contains_path_separator)


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Crawler(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    verified: Literal["verified", "unverified", "forged"]
    hits: int = Field(ge=0)
    bytes: int = Field(ge=0)
    records_taken: int = Field(ge=0)


class Walk(StrictModel):
    verdict: Literal["Catalogue walk detected", "Suspicious", "No walk detected", "Insufficient data"]
    shape_triggered: bool
    order_triggered: bool
    distributed_signal: bool
    asset_fetch_signal: bool
    per_address_rate: float = Field(ge=0)
    records_taken_estimate: int = Field(ge=0)


class GeoResult(StrictModel):
    engine: str = Field(min_length=1, max_length=100)
    query_id: str = Field(min_length=1, max_length=200)
    mentioned: bool
    cited: bool


class ReportIn(StrictModel):
    site_id: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date
    site_type: Literal["business", "blog", "shop", "directory", "other"]
    ai_stance: Literal["found", "search_only", "block_all"]
    pageviews_human: int = Field(ge=0)
    sessions_human: int = Field(ge=0)
    engaged_sessions: int = Field(ge=0)
    crawlers: list[Crawler] = Field(max_length=500)
    walk: Walk
    geo: list[GeoResult] | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def reject_private_data(cls, value: Any):
        for item in _walk_strings(value):
            if _private_string(item):
                raise ValueError("IP addresses, paths, URLs, user agents, and page content are not accepted")
        return value

    @model_validator(mode="after")
    def validate_period_and_counts(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if self.engaged_sessions > self.sessions_human:
            raise ValueError("engaged_sessions cannot exceed sessions_human")
        return self


ACTIONS = ("none", "observe", "robots", "rate_rule", "block_rule")
ACTION_LABELS = {
    "none": "No action",
    "observe": "Watch for a week",
    "robots": "Ask crawlers to stay out (robots.txt)",
    "rate_rule": "Slow the pattern down (rate rule)",
    "block_rule": "Refuse the pattern (block rule)",
}


class Recommendation(StrictModel):
    """What a safe next step could be, if any. The rules set `action`'s maximum
    (see deterministic.max_action); a model may write `reason`, never raise `action`."""
    action: Literal["none", "observe", "robots", "rate_rule", "block_rule"]
    reason: str = Field(min_length=1, max_length=600)
    confidence: Literal["low", "medium", "high"]
    scope: list[str] = Field(default_factory=list, max_length=10)        # section names, never paths
    exclusions: list[str] = Field(default_factory=list, max_length=20)   # who must never be caught by the rule
    observe_days: int = Field(default=0, ge=0, le=90)
    rollback: str = Field(default="", max_length=300)
    do_not_use_if: list[str] = Field(default_factory=list, max_length=10)


class ReadingBody(StrictModel):
    headline: str
    paragraphs: list[str]
    verdict: str
    changes: list[str]
    benchmarks: list[str]
    recommendation: Recommendation | None = None
