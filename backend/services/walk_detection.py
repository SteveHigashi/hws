"""Pure, after-the-fact catalogue-walk detectors over privacy-safe log rows.

The caller must replace a raw address with a stable, site-salted identity before
constructing a row. This module performs no I/O, DNS, database access, blocking,
rate limiting, response changes, or other enforcement.

SHAPE and ORDER are deliberately independent primary triggers. The first live
detector required both and was defeated by one line that shuffled the attacker's
queue. A detector hung on one implementation property is one line of attacker
code away from being switched off.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import math
from pathlib import PurePosixPath
import re
from statistics import median
from typing import Iterable, Mapping, Optional
from urllib.parse import unquote


ASSET_EXTENSIONS = {
    ".avif", ".css", ".eot", ".gif", ".ico", ".jpeg", ".jpg", ".js",
    ".map", ".mp4", ".png", ".svg", ".ttf", ".webm", ".webp", ".woff",
    ".woff2",
}
NON_CONTENT_PATHS = {
    "/favicon.ico", "/robots.txt", "/sitemap.xml", "/llms.txt",
}
_DYNAMIC_SEGMENT = re.compile(
    r"^(?:\d{2,}|[0-9a-f]{8,}|[0-9a-f-]{32,}|[a-z0-9]+(?:-[a-z0-9]+)+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LogRow:
    timestamp: datetime
    identity: str
    method: str
    path: str
    status: int
    response_bytes: int
    content_type: Optional[str] = None
    referrer: Optional[str] = None
    user_agent: str = ""
    bot_name: Optional[str] = None
    bot_verification: Optional[str] = None

    @classmethod
    def from_mapping(cls, value: Mapping) -> "LogRow":
        timestamp = value["timestamp"]
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return cls(
            timestamp=timestamp,
            identity=str(value["identity"]),
            method=str(value.get("method", "GET")).upper(),
            path=normalise_path(str(value.get("path", "/"))),
            status=int(value.get("status", 0)),
            response_bytes=max(0, int(value.get("response_bytes", 0))),
            content_type=value.get("content_type") or None,
            referrer=value.get("referrer") or None,
            user_agent=str(value.get("user_agent", "")),
            bot_name=value.get("bot_name"),
            bot_verification=value.get("bot_verification"),
        )


@dataclass(frozen=True)
class DetectionResult:
    window_start: datetime
    window_end: datetime
    verdict: str
    headline: str
    score: int
    triggers: tuple[str, ...]
    signals: tuple[str, ...]
    records_taken: int
    total_content_requests: int
    distinct_identities: int
    shape_oneshot_identities: int
    shape_share: float
    order_pairs: int
    order_ratio: float
    content_responses: int
    asset_responses: int
    assetless_identity_share: float
    referer_absence_ratio: float
    shared_queue_pairs: int
    shared_queue_ratio: float
    median_requests_per_address_day: float
    p95_requests_per_address_day: float
    singleton_address_share: float
    rate_blind_spot: bool
    forged_claims: int
    verified_claims: int
    unverified_claims: int
    engagement_absence_ratio: Optional[float] = None

    def to_dict(self) -> dict:
        value = asdict(self)
        value["window_start"] = self.window_start.isoformat()
        value["window_end"] = self.window_end.isoformat()
        value["triggers"] = list(self.triggers)
        value["signals"] = list(self.signals)
        return value


@lru_cache(maxsize=65_536)
def normalise_path(raw: str) -> str:
    value = unquote(raw.split("?", 1)[0].split("#", 1)[0] or "/")
    parts: list[str] = []
    for part in value.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


@lru_cache(maxsize=65_536)
def is_asset_path(path: str) -> bool:
    clean = normalise_path(path).lower()
    if PurePosixPath(clean).suffix in ASSET_EXTENSIONS:
        return True
    return any(part in {"assets", "static", "fonts", "images", "img"} for part in clean.split("/"))


def is_asset_response(row: LogRow) -> bool:
    media_type = (row.content_type or "").split(";", 1)[0].strip().lower()
    return (
        is_asset_path(row.path)
        or media_type.startswith(("image/", "font/", "audio/", "video/"))
        or media_type in {"application/javascript", "text/javascript", "text/css"}
    )


def is_content_candidate(row: LogRow) -> bool:
    if row.method != "GET" or row.path.lower() in NON_CONTENT_PATHS or is_asset_response(row):
        return False
    suffix = PurePosixPath(row.path.lower()).suffix
    return not suffix or suffix in {".html", ".htm"}


@lru_cache(maxsize=65_536)
def path_pattern(path: str) -> str:
    """Infer a catalogue family without assuming a framework or route prefix."""
    clean = normalise_path(path)
    parts = [part for part in clean.split("/") if part]
    if not parts:
        return "/"
    if len(parts) == 1:
        return "/:item"
    last = parts[-1]
    if _DYNAMIC_SEGMENT.match(last) or "." not in last:
        parts[-1] = ":item"
    return "/" + "/".join(parts)


def infer_content_patterns(rows: Iterable[LogRow], min_distinct: int = 3) -> set[str]:
    paths: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if is_content_candidate(row) and 200 <= row.status < 300:
            paths[path_pattern(row.path)].add(row.path)
    return {pattern for pattern, values in paths.items() if len(values) >= min_distinct}


def response_size_baselines(
    rows: Iterable[LogRow],
    patterns: Optional[set[str]] = None,
    window_size: int = 1000,
) -> dict[str, float]:
    """Return the rolling median successful-response size for each path family."""
    histories: dict[str, deque[int]] = defaultdict(lambda: deque(maxlen=window_size))
    for row in sorted(rows, key=lambda item: item.timestamp):
        pattern = path_pattern(row.path)
        if patterns is not None and pattern not in patterns:
            continue
        if is_content_candidate(row) and 200 <= row.status < 300 and row.method == "GET":
            histories[pattern].append(row.response_bytes)
    return {pattern: float(median(values)) for pattern, values in histories.items() if values}


def records_taken_rows(rows: Iterable[LogRow]) -> list[LogRow]:
    values = list(rows)
    patterns = infer_content_patterns(values)
    baselines = response_size_baselines(values, patterns)
    taken: list[LogRow] = []
    for row in values:
        baseline = baselines.get(path_pattern(row.path), 0)
        # NON-NEGOTIABLE: a 200 is not evidence that a record left the server.
        # Gated and stub responses are often 200 too. Every records-taken count
        # is based on bytes versus a per-path rolling median.
        if (
            path_pattern(row.path) in patterns
            and row.method == "GET"
            and 200 <= row.status < 300
            and baseline >= 1024
            and row.response_bytes >= max(1024, baseline * 0.60)
        ):
            taken.append(row)
    return taken


def detect_shape(
    rows: Iterable[LogRow],
    records: Optional[list[LogRow]] = None,
    min_oneshot_identities: int = 10,
    min_share: float = 0.70,
) -> dict:
    values = list(rows)
    records = records if records is not None else records_taken_rows(values)
    request_counts = Counter(row.identity for row in values)
    asset_counts = Counter(row.identity for row in values if is_asset_response(row))
    oneshot = [
        row for row in records
        if request_counts[row.identity] == 1
        and asset_counts[row.identity] == 0
        and row.bot_verification != "verified"
    ]
    identities = {row.identity for row in oneshot}
    eligible_records = [row for row in records if row.bot_verification != "verified"]
    share = len(oneshot) / len(eligible_records) if eligible_records else 0.0
    return {
        "fired": len(identities) >= min_oneshot_identities and share >= min_share,
        "oneshot_identities": len(identities),
        "oneshot_records": len(oneshot),
        "share": round(share, 4),
    }


def detect_order(
    rows: Iterable[LogRow],
    records: Optional[list[LogRow]] = None,
    min_adjacent: int = 12,
    min_ratio: float = 0.85,
) -> dict:
    values = list(rows)
    records = records if records is not None else records_taken_rows(values)
    sequence = [
        PurePosixPath(row.path).name.lower()
        for row in sorted(records, key=lambda item: item.timestamp)
        if row.bot_verification != "verified"
    ]
    pairs = [(left, right) for left, right in zip(sequence, sequence[1:]) if left != right]
    descending = sum(1 for left, right in pairs if right < left)
    directional = max(descending, len(pairs) - descending)
    ratio = directional / len(pairs) if pairs else 0.0
    return {
        "fired": len(pairs) >= min_adjacent and ratio >= min_ratio,
        "pairs": len(pairs),
        "directional_pairs": directional,
        "ratio": round(ratio, 4),
    }


def asset_fetch_signal(rows: Iterable[LogRow], records: Optional[list[LogRow]] = None) -> dict:
    values = list(rows)
    records = records if records is not None else records_taken_rows(values)
    content_counts = Counter(row.identity for row in records)
    asset_counts = Counter(
        row.identity for row in values
        if row.method == "GET" and 200 <= row.status < 400 and is_asset_response(row)
    )
    identities = set(content_counts)
    assetless = sum(1 for identity in identities if asset_counts[identity] == 0)
    return {
        "content_responses": sum(content_counts.values()),
        "asset_responses": sum(asset_counts[identity] for identity in identities),
        "content_only_identities": assetless,
        "assetless_identity_share": round(assetless / len(identities), 4) if identities else 0.0,
    }


def per_address_rate(rows: Iterable[LogRow], records: Optional[list[LogRow]] = None) -> dict:
    values = list(rows)
    records = records if records is not None else records_taken_rows(values)
    by_identity: dict[str, list[LogRow]] = defaultdict(list)
    for row in records:
        if row.bot_verification != "verified":
            by_identity[row.identity].append(row)
    rates = []
    for identity_rows in by_identity.values():
        active_days = max(1, len({row.timestamp.date() for row in identity_rows}))
        rates.append(len(identity_rows) / active_days)
    rates.sort()
    if not rates:
        return {"median": 0.0, "p95": 0.0, "singleton_share": 0.0, "blind_spot": False}
    p95_index = max(0, math.ceil(len(rates) * 0.95) - 1)
    singleton_share = sum(1 for rate in rates if rate == 1) / len(rates)
    return {
        "median": round(float(median(rates)), 2),
        "p95": round(float(rates[p95_index]), 2),
        "singleton_share": round(singleton_share, 4),
        "blind_spot": singleton_share >= 0.50,
    }


def distributed_walk_signal(rows: Iterable[LogRow], records: Optional[list[LogRow]] = None) -> dict:
    values = list(rows)
    records = records if records is not None else records_taken_rows(values)
    ordered = sorted(records, key=lambda item: item.timestamp)
    missing_referrer = sum(1 for row in ordered if not row.referrer or row.referrer == "-")
    cross_pairs = [
        (left, right)
        for left, right in zip(ordered, ordered[1:])
        if left.identity != right.identity
    ]

    def first_letter(row: LogRow) -> str:
        name = PurePosixPath(row.path).name.lower()
        return next((char for char in name if char.isalnum()), "")

    shared = sum(
        1 for left, right in cross_pairs
        if first_letter(left) and first_letter(left) == first_letter(right)
    )
    return {
        "referer_absence_ratio": round(missing_referrer / len(ordered), 4) if ordered else 0.0,
        "cross_address_pairs": len(cross_pairs),
        "shared_first_letter_pairs": shared,
        "shared_queue_ratio": round(shared / len(cross_pairs), 4) if cross_pairs else 0.0,
    }


def engagement_absence_signal(total_sessions: int, engaged_sessions: int) -> Optional[float]:
    """Aggregate corroboration only; this value is never a primary trigger."""
    if total_sessions <= 0:
        return None
    return round(max(0, total_sessions - engaged_sessions) / total_sessions, 4)


def analyze_walk(
    rows: Iterable[LogRow | Mapping],
    engagement_absence_ratio: Optional[float] = None,
) -> DetectionResult:
    values = [row if isinstance(row, LogRow) else LogRow.from_mapping(row) for row in rows]
    if not values:
        now = datetime.now(timezone.utc)
        return DetectionResult(
            window_start=now,
            window_end=now,
            verdict="insufficient_data",
            headline="Not enough log data to judge catalogue walking.",
            score=0,
            triggers=(),
            signals=(),
            records_taken=0,
            total_content_requests=0,
            distinct_identities=0,
            shape_oneshot_identities=0,
            shape_share=0.0,
            order_pairs=0,
            order_ratio=0.0,
            content_responses=0,
            asset_responses=0,
            assetless_identity_share=0.0,
            referer_absence_ratio=0.0,
            shared_queue_pairs=0,
            shared_queue_ratio=0.0,
            median_requests_per_address_day=0.0,
            p95_requests_per_address_day=0.0,
            singleton_address_share=0.0,
            rate_blind_spot=False,
            forged_claims=0,
            verified_claims=0,
            unverified_claims=0,
            engagement_absence_ratio=engagement_absence_ratio,
        )

    records = records_taken_rows(values)
    eligible_records = [row for row in records if row.bot_verification != "verified"]
    shape = detect_shape(values, records)
    order = detect_order(values, records)
    assets = asset_fetch_signal(values, eligible_records)
    rates = per_address_rate(values, eligible_records)
    distributed = distributed_walk_signal(values, eligible_records)
    claims = Counter(row.bot_verification for row in values if row.bot_name)

    triggers = tuple(
        name for name, fired in (("shape", shape["fired"]), ("order", order["fired"])) if fired
    )
    signals: list[str] = []
    score = 0
    if shape["fired"]:
        score += 45
    if order["fired"]:
        score += 40
    if claims["forged"]:
        score += 45
        signals.append("forged_crawler_claim")
    if assets["content_responses"] >= 10 and assets["assetless_identity_share"] >= 0.80:
        score += 20
        signals.append("asset_fetch_absence")
    if len(records) >= 10 and distributed["referer_absence_ratio"] >= 0.80:
        score += 10
        signals.append("referer_absence")
    if distributed["cross_address_pairs"] >= 12 and distributed["shared_queue_ratio"] >= 0.60:
        score += 15
        signals.append("shared_queue_fingerprint")
    if rates["p95"] >= 100 and not rates["blind_spot"]:
        score += 10
        signals.append("high_per_address_rate")
    if engagement_absence_ratio is not None and engagement_absence_ratio >= 0.90:
        # Corroboration only. Five points can strengthen a finding but can never
        # create one on its own because legitimate crawler and reader sessions
        # often have no behavior event.
        score += 5
        signals.append("engagement_absence")
    score = min(100, score)

    if triggers:
        verdict = "walk_detected"
        headline = "A catalogue walk was detected in this log window."
    elif claims["forged"] or score >= 50:
        verdict = "suspicious"
        headline = "Suspicious catalogue access needs review, but no walk shape was proven."
    elif len(eligible_records) < 3:
        verdict = "insufficient_data"
        headline = "Not enough full catalogue responses to judge walking."
    else:
        verdict = "no_walk_detected"
        headline = "No catalogue walk was detected in this log window."

    identities = {row.identity for row in eligible_records}
    return DetectionResult(
        window_start=min(row.timestamp for row in values),
        window_end=max(row.timestamp for row in values),
        verdict=verdict,
        headline=headline,
        score=score,
        triggers=triggers,
        signals=tuple(signals),
        records_taken=len(eligible_records),
        total_content_requests=sum(
            1 for row in values
            if is_content_candidate(row) and row.bot_verification != "verified"
        ),
        distinct_identities=len(identities),
        shape_oneshot_identities=shape["oneshot_identities"],
        shape_share=shape["share"],
        order_pairs=order["pairs"],
        order_ratio=order["ratio"],
        content_responses=assets["content_responses"],
        asset_responses=assets["asset_responses"],
        assetless_identity_share=assets["assetless_identity_share"],
        referer_absence_ratio=distributed["referer_absence_ratio"],
        shared_queue_pairs=distributed["cross_address_pairs"],
        shared_queue_ratio=distributed["shared_queue_ratio"],
        median_requests_per_address_day=rates["median"],
        p95_requests_per_address_day=rates["p95"],
        singleton_address_share=rates["singleton_share"],
        rate_blind_spot=rates["blind_spot"],
        forged_claims=claims["forged"],
        verified_claims=claims["verified"],
        unverified_claims=claims["unverified"],
        engagement_absence_ratio=engagement_absence_ratio,
    )


def analyze_windows(
    rows: Iterable[LogRow | Mapping],
    window_minutes: int = 30,
) -> list[DetectionResult]:
    """Analyze aligned windows so a multi-day import preserves attack episodes."""
    values = [row if isinstance(row, LogRow) else LogRow.from_mapping(row) for row in rows]
    if not values:
        return []
    seconds = max(1, window_minutes) * 60
    grouped: dict[int, list[LogRow]] = defaultdict(list)
    for row in values:
        grouped[int(row.timestamp.timestamp()) // seconds].append(row)
    return [analyze_walk(grouped[key]) for key in sorted(grouped)]
