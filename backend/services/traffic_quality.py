from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from services.bot import classify_bot


TRAFFIC_CLASSES = (
    "verified_human",
    "likely_human",
    "known_bot",
    "ai_crawler",
    "suspicious",
    "unknown",
)

TRAFFIC_LABELS = {
    "verified_human": "Verified Humans",
    "likely_human": "Likely Humans",
    "known_bot": "Known Bots",
    "ai_crawler": "AI/SEO Crawlers",
    "suspicious": "Suspicious",
    "unknown": "Unknown",
}

SCANNER_PATH_RE = re.compile(
    r"("
    r"wp-json|wp-login|wp-admin|xmlrpc\.php|phpinfo|swagger|\.env|"
    r"config|application\.ya?ml|auth\.php|admin|login|shell|"
    r"vendor/phpunit|composer\.(json|lock)|\.git|\.svn|backup|"
    r"database|db_backup|passwd|boaform|cgi-bin|actuator|setup\.php"
    r")",
    re.IGNORECASE,
)

OLD_PLATFORM_RE = re.compile(
    r"("
    r"/wp-content/|/wp-includes/|/wp-json|/feed/?$|/comments/feed|"
    r"/category/|/tag/|/author/|/20\d{2}/\d{2}/|/xmlrpc\.php"
    r")",
    re.IGNORECASE,
)

SCANNER_UA_RE = re.compile(
    r"("
    r"l9scan|leakix|censys|shodan|zgrab|masscan|turnitin|"
    r"validation server|nuclei|nikto|sqlmap|acunetix|nessus|"
    r"nmap|dirbuster|gobuster|wpscan"
    r")",
    re.IGNORECASE,
)

HUMAN_REFERRER_RE = re.compile(
    r"("
    r"google\.|bing\.|duckduckgo\.|yahoo\.|ecosia\.|perplexity\.|"
    r"chatgpt\.com|claude\.ai|facebook\.|linkedin\.|t\.co|twitter\.|"
    r"x\.com|reddit\.|threads\.net|bsky\.app|instagram\.|telegram\.|"
    r"whatsapp\."
    r")",
    re.IGNORECASE,
)

STATIC_ASSET_RE = re.compile(
    r"\.(css|js|map|png|jpe?g|gif|svg|ico|webp|avif|woff2?|ttf|eot|pdf|zip|gz)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SessionQuality:
    traffic_class: str
    confidence: float
    reasons: list[str]

    def as_dict(self) -> dict:
        return {
            "traffic_class": self.traffic_class,
            "confidence": self.confidence,
            "reasons": self.reasons,
        }


def path_from_url(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            return parsed.path or "/"
    except Exception:
        pass
    return value.split("?", 1)[0] or "/"


def classify_path(path: str | None) -> tuple[str, list[str]]:
    normalized = path_from_url(path)
    reasons: list[str] = []
    if SCANNER_PATH_RE.search(normalized):
        reasons.append("scanner/security path")
        return "scanner", reasons
    if OLD_PLATFORM_RE.search(normalized):
        reasons.append("old platform/archive residue")
        return "platform_residue", reasons
    if STATIC_ASSET_RE.search(normalized):
        reasons.append("static asset")
        return "asset", reasons
    return "content", reasons


def classify_user_agent(user_agent: str | None) -> tuple[str, list[str]]:
    if SCANNER_UA_RE.search(user_agent or ""):
        return "scanner", ["scanner user agent"]

    bot = classify_bot(user_agent or "")
    if bot:
        if bot.get("category") == "ai_crawler":
            return "ai_crawler", [f"known AI crawler: {bot['name']}"]
        return "known_bot", [f"known bot: {bot['name']}"]

    return "unknown", []


def has_js_proof(events: Iterable, has_behavior_events: bool = False) -> bool:
    if has_behavior_events:
        return True
    for event in events:
        if getattr(event, "screen_width", None) or getattr(event, "screen_height", None):
            return True
        if getattr(event, "language", None):
            return True
        if getattr(event, "lcp", None) or getattr(event, "fcp", None) or getattr(event, "ttfb", None):
            return True
        if getattr(event, "scroll_depth", None) is not None:
            return True
        meta = getattr(event, "meta", None) or {}
        if isinstance(meta, dict) and any(k in meta for k in ("tracker", "visibility", "viewport")):
            return True
    return False


def is_credible_referrer(referrer_domain: str | None, events: Iterable) -> bool:
    if referrer_domain and HUMAN_REFERRER_RE.search(referrer_domain):
        return True
    for event in events:
        referrer = getattr(event, "referrer", None)
        if referrer and HUMAN_REFERRER_RE.search(referrer):
            return True
    return False


def classify_session(session, events: list, has_behavior_events: bool = False) -> dict:
    reasons: list[str] = []
    page_count = getattr(session, "page_count", None) or len(events) or 1
    referrer_domain = getattr(session, "referrer_domain", None)
    paths = [path_from_url(getattr(event, "page_url", "")) for event in events]
    any_404 = any(bool(getattr(event, "is_404", False)) for event in events)
    all_404 = bool(events) and all(bool(getattr(event, "is_404", False)) for event in events)

    ua_votes = Counter()
    for event in events:
        ua_class, ua_reasons = classify_user_agent(getattr(event, "user_agent", None))
        ua_votes[ua_class] += 1
        reasons.extend(ua_reasons)

    if ua_votes["ai_crawler"]:
        return SessionQuality("ai_crawler", 0.98, sorted(set(reasons))).as_dict()
    if ua_votes["known_bot"]:
        return SessionQuality("known_bot", 0.98, sorted(set(reasons))).as_dict()

    path_reasons: list[str] = []
    scanner_path = False
    for path in paths:
        path_class, p_reasons = classify_path(path)
        scanner_path = scanner_path or path_class == "scanner"
        path_reasons.extend(p_reasons)

    suspicious_reasons = []
    if ua_votes["scanner"]:
        suspicious_reasons.append("scanner user agent")
    if scanner_path:
        suspicious_reasons.append("scanner/security path")
    if page_count <= 1 and not referrer_domain and any_404:
        suspicious_reasons.append("one-page no-referrer 404")
    if all_404 and not referrer_domain:
        suspicious_reasons.append("404-only no-referrer session")

    if suspicious_reasons:
        return SessionQuality(
            "suspicious",
            0.9,
            sorted(set(reasons + path_reasons + suspicious_reasons)),
        ).as_dict()

    if has_js_proof(events, has_behavior_events):
        return SessionQuality("verified_human", 0.9, ["JS or behavior proof"]).as_dict()

    if is_credible_referrer(referrer_domain, events):
        return SessionQuality("likely_human", 0.7, ["credible referrer"]).as_dict()

    content_paths = [p for p in paths if classify_path(p)[0] == "content"]
    if page_count > 1 and content_paths and not any_404:
        return SessionQuality("likely_human", 0.62, ["multi-page clean content visit"]).as_dict()

    return SessionQuality("unknown", 0.35, ["browser-like log session without proof"]).as_dict()


def quality_confidence(has_verified: bool, likely_humans: int, total_sessions: int) -> str:
    if total_sessions == 0:
        return "none"
    if has_verified:
        return "high"
    if likely_humans:
        return "low"
    return "very low"
