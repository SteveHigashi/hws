import bisect
import ipaddress
import json
import math
import os
from pathlib import Path
import re
from typing import Optional

# Known AI and web crawlers with metadata for analytics
_CRAWLER_REGISTRY = [
    # AI training / inference crawlers
    {"name": "GPTBot",            "pattern": r"GPTBot",              "category": "ai_crawler", "avi_weight": 1.5, "reach_mult": 200, "description": "OpenAI training crawler"},
    {"name": "ChatGPT-User",      "pattern": r"ChatGPT-User",        "category": "ai_crawler", "avi_weight": 1.5, "reach_mult": 200, "description": "OpenAI real-time browsing"},
    {"name": "ClaudeBot",         "pattern": r"ClaudeBot|anthropic-ai", "category": "ai_crawler", "avi_weight": 1.3, "reach_mult": 50,  "description": "Anthropic / Claude"},
    {"name": "PerplexityBot",     "pattern": r"PerplexityBot",       "category": "ai_crawler", "avi_weight": 1.2, "reach_mult": 25,  "description": "Perplexity AI"},
    {"name": "Google-Extended",   "pattern": r"Google-Extended",     "category": "ai_crawler", "avi_weight": 1.2, "reach_mult": 150, "description": "Google Gemini training"},
    {"name": "Meta-ExternalAgent","pattern": r"Meta-ExternalAgent|FacebookBot", "category": "ai_crawler", "avi_weight": 1.1, "reach_mult": 80, "description": "Meta AI"},
    {"name": "Bytespider",        "pattern": r"Bytespider",          "category": "ai_crawler", "avi_weight": 1.1, "reach_mult": 60,  "description": "ByteDance / TikTok AI"},
    {"name": "Applebot-Extended", "pattern": r"Applebot-Extended",   "category": "ai_crawler", "avi_weight": 1.1, "reach_mult": 40,  "description": "Apple Intelligence"},
    {"name": "CCBot",             "pattern": r"CCBot",               "category": "ai_crawler", "avi_weight": 1.0, "reach_mult": 10,  "description": "Common Crawl (AI training data)"},
    {"name": "YouBot",            "pattern": r"YouBot",              "category": "ai_crawler", "avi_weight": 1.0, "reach_mult": 8,   "description": "You.com AI"},
    {"name": "cohere-ai",         "pattern": r"cohere-ai|CohereBot", "category": "ai_crawler", "avi_weight": 1.0, "reach_mult": 8,   "description": "Cohere AI"},
    {"name": "Diffbot",           "pattern": r"Diffbot",             "category": "ai_crawler", "avi_weight": 0.8, "reach_mult": 5,   "description": "Diffbot knowledge graph"},
    {"name": "ImagesiftBot",      "pattern": r"ImagesiftBot",        "category": "ai_crawler", "avi_weight": 0.7, "reach_mult": 3,   "description": "Image AI training"},
    {"name": "omgili",            "pattern": r"omgili|Webz\.io",     "category": "ai_crawler", "avi_weight": 0.7, "reach_mult": 5,   "description": "News/data AI feeds"},
    # SEO crawlers
    {"name": "Googlebot",         "pattern": r"Googlebot(?!-Extended)",  "category": "seo_crawler", "avi_weight": 0, "reach_mult": 0, "description": "Google Search"},
    {"name": "Bingbot",           "pattern": r"bingbot",             "category": "seo_crawler", "avi_weight": 0, "reach_mult": 0,   "description": "Bing Search"},
    {"name": "YandexBot",         "pattern": r"YandexBot|yandex",    "category": "seo_crawler", "avi_weight": 0, "reach_mult": 0,   "description": "Yandex Search"},
    {"name": "Baiduspider",       "pattern": r"Baiduspider",         "category": "seo_crawler", "avi_weight": 0, "reach_mult": 0,   "description": "Baidu Search"},
    {"name": "DuckDuckBot",       "pattern": r"DuckDuckBot",         "category": "seo_crawler", "avi_weight": 0, "reach_mult": 0,   "description": "DuckDuckGo"},
    {"name": "Applebot",          "pattern": r"Applebot(?!-Extended)", "category": "seo_crawler", "avi_weight": 0, "reach_mult": 0,  "description": "Apple Search"},
    # SEO audit tools
    {"name": "SemrushBot",        "pattern": r"SemrushBot|semrush",  "category": "seo_audit",   "avi_weight": 0, "reach_mult": 0,   "description": "Semrush"},
    {"name": "AhrefsBot",         "pattern": r"AhrefsBot|ahrefs",    "category": "seo_audit",   "avi_weight": 0, "reach_mult": 0,   "description": "Ahrefs"},
    {"name": "MJ12bot",           "pattern": r"MJ12bot|majestic",    "category": "seo_audit",   "avi_weight": 0, "reach_mult": 0,   "description": "Majestic SEO"},
    {"name": "DotBot",            "pattern": r"DotBot|moz\.com",     "category": "seo_audit",   "avi_weight": 0, "reach_mult": 0,   "description": "Moz"},
    # Social preview crawlers
    {"name": "Twitterbot",        "pattern": r"Twitterbot",          "category": "social_crawler", "avi_weight": 0, "reach_mult": 0, "description": "Twitter/X link preview"},
    {"name": "facebookexternalhit","pattern": r"facebookexternalhit","category": "social_crawler", "avi_weight": 0, "reach_mult": 0, "description": "Facebook link preview"},
    {"name": "LinkedInBot",       "pattern": r"LinkedInBot",         "category": "social_crawler", "avi_weight": 0, "reach_mult": 0, "description": "LinkedIn link preview"},
    {"name": "TelegramBot",       "pattern": r"TelegramBot",         "category": "social_crawler", "avi_weight": 0, "reach_mult": 0, "description": "Telegram link preview"},
    {"name": "WhatsApp",          "pattern": r"WhatsApp",            "category": "social_crawler", "avi_weight": 0, "reach_mult": 0, "description": "WhatsApp link preview"},
    # Security scanners / validation probes
    {"name": "Turnitin",          "pattern": r"Turnitin",            "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Turnitin crawler"},
    {"name": "l9scan",            "pattern": r"l9scan",              "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Security scanner"},
    {"name": "LeakIX",            "pattern": r"LeakIX",              "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Internet exposure scanner"},
    {"name": "Censys",            "pattern": r"Censys",              "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Internet scanner"},
    {"name": "Shodan",            "pattern": r"Shodan",              "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Internet scanner"},
    {"name": "zgrab",             "pattern": r"zgrab",               "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Internet scanner"},
    {"name": "masscan",           "pattern": r"masscan",             "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Port scanner"},
    {"name": "Let's Encrypt",     "pattern": r"Let'?s Encrypt validation server", "category": "generic_bot", "avi_weight": 0, "reach_mult": 0, "description": "Certificate validation server"},
]

# Compiled once at import time
_COMPILED = [
    {**entry, "_re": re.compile(entry["pattern"], re.IGNORECASE)}
    for entry in _CRAWLER_REGISTRY
]

# Published crawler ranges are bundled so classification never depends on an
# outbound request. The optional refresh script replaces this file on the
# operator's schedule; request or traffic data is never sent anywhere.
_DEFAULT_RANGE_FILE = Path(__file__).resolve().parent.parent / "data" / "crawler_ranges.json"
_RANGE_FILE = Path(os.getenv("HIGASHI_CRAWLER_RANGES", str(_DEFAULT_RANGE_FILE)))

_NETWORK_RULES = {
    "Googlebot": {
        "groups": ("googlebot", "google-special", "google-user"),
        "suffixes": (".googlebot.com", ".google.com", ".googleusercontent.com"),
    },
    "Google-Extended": {
        "groups": ("googlebot", "google-special", "google-user"),
        "suffixes": (".googlebot.com", ".google.com", ".googleusercontent.com"),
    },
    "Bingbot": {
        "groups": ("bingbot",),
        "suffixes": (".search.msn.com",),
    },
    "Applebot": {
        "groups": ("applebot",),
        "suffixes": (".applebot.apple.com", ".apple.com"),
    },
    "Applebot-Extended": {
        "groups": ("applebot",),
        "suffixes": (".applebot.apple.com", ".apple.com"),
    },
    "DuckDuckBot": {
        "groups": ("duckduckbot", "duckassistbot"),
        "suffixes": (".duckduckgo.com",),
    },
    "PerplexityBot": {
        "groups": ("perplexitybot",),
        "suffixes": (),
    },
    # These operators publish a stable FCrDNS contract but no prefix feed in
    # the bundled dataset. They can be verified by DNS, otherwise the honest
    # answer is "unverified" rather than "forged".
    "YandexBot": {"groups": (), "suffixes": (".yandex.ru", ".yandex.net")},
    "Baiduspider": {"groups": (), "suffixes": (".baidu.com", ".baidu.jp")},
}


class _PrefixIndex:
    """Sorted integer intervals: O(log n) membership with no per-row parsing."""

    def __init__(self, raw: dict[str, list[str]]):
        self._families: dict[str, dict[int, tuple[list[int], list[int]]]] = {}
        for family, prefixes in raw.items():
            versions: dict[int, list[tuple[int, int]]] = {4: [], 6: []}
            for prefix in prefixes:
                try:
                    network = ipaddress.ip_network(prefix, strict=False)
                except ValueError:
                    continue
                versions[network.version].append(
                    (int(network.network_address), int(network.broadcast_address))
                )
            packed = {}
            for version, intervals in versions.items():
                intervals.sort()
                if intervals:
                    packed[version] = (
                        [start for start, _ in intervals],
                        [end for _, end in intervals],
                    )
            self._families[family] = packed

    def has_family(self, family: str) -> bool:
        return bool(self._families.get(family))

    def contains(self, address, families: tuple[str, ...]) -> bool:
        needle = int(address)
        for family in families:
            packed = self._families.get(family, {}).get(address.version)
            if not packed:
                continue
            starts, ends = packed
            pos = bisect.bisect_right(starts, needle) - 1
            if pos >= 0 and needle <= ends[pos]:
                return True
        return False


def _read_ranges(path: Path) -> dict[str, list[str]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


_PREFIX_INDEX = _PrefixIndex(_read_ranges(_RANGE_FILE))


def reload_crawler_ranges(path: Optional[str] = None) -> None:
    """Reload a last-known-good range file, mainly for the scheduled refresher."""
    global _PREFIX_INDEX
    _PREFIX_INDEX = _PrefixIndex(_read_ranges(Path(path) if path else _RANGE_FILE))


def _verification_for(
    bot_name: str,
    ip_address: Optional[str],
    fcrdns_lookup=None,
) -> tuple[str, Optional[str]]:
    """Return the required three-state verdict and the verification method."""
    if not ip_address:
        return "unverified", None
    try:
        address = ipaddress.ip_address(ip_address)
    except ValueError:
        return "unverified", None

    rule = _NETWORK_RULES.get(bot_name)
    if not rule:
        return "unverified", None

    groups = rule["groups"]
    range_data_available = any(_PREFIX_INDEX.has_family(group) for group in groups)
    if groups and _PREFIX_INDEX.contains(address, groups):
        return "verified", "published_prefix"

    suffixes = rule["suffixes"]
    if suffixes and fcrdns_lookup is not None:
        # FCrDNS is accepted as fallback evidence, but core never starts a DNS
        # request: the no-outbound guarantee is stricter than convenience.
        # A deployment that already has locally resolved, forward-confirmed
        # evidence may inject this pure lookup during an offline import.
        hostname = fcrdns_lookup(str(address))
        if isinstance(hostname, bool):
            fcrdns_ok = hostname
        else:
            hostname = (hostname or "").lower().rstrip(".")
            fcrdns_ok = any(hostname.endswith(suffix) for suffix in suffixes)
        if fcrdns_ok:
            return "verified", "fcrdns"

    # A valid address outside an available vendor feed, with no independently
    # supplied FCrDNS proof, is a forged claim. Without an authoritative set,
    # failed or absent DNS evidence leaves the claim unverified.
    if range_data_available:
        return "forged", "prefix_mismatch"
    return "unverified", None

_GENERIC_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|curl|wget|python-requests|java|ruby|perl|php"
    r"|go-http|httpclient|libwww|scrapy|mechanize|headless|phantom|selenium|puppeteer"
    r"|aiohttp|httpx|okhttp|axios|node-fetch|undici|fasthttp|reqwest",
    re.IGNORECASE,
)

# Lookup maps for metric calculations
AVI_WEIGHTS: dict[str, float]  = {e["name"]: e["avi_weight"]  for e in _CRAWLER_REGISTRY if e["avi_weight"] > 0}
REACH_MULTS: dict[str, int]    = {e["name"]: e["reach_mult"]  for e in _CRAWLER_REGISTRY if e["reach_mult"] > 0}


def classify_bot(
    user_agent: str,
    ip_address: Optional[str] = None,
    fcrdns_lookup=None,
) -> Optional[dict]:
    """Return crawler metadata plus verified/unverified/forged network state."""
    if not user_agent:
        return {
            "name": "empty-ua", "category": "generic_bot", "avi_weight": 0,
            "reach_mult": 0, "description": "Empty user agent",
            "verification_state": "unverified", "verification_method": None,
        }

    for entry in _COMPILED:
        if entry["_re"].search(user_agent):
            state, method = _verification_for(entry["name"], ip_address, fcrdns_lookup)
            return {
                "name":        entry["name"],
                "category":    entry["category"],
                "avi_weight":  entry["avi_weight"],
                "reach_mult":  entry["reach_mult"],
                "description": entry["description"],
                "verification_state": state,
                "verification_method": method,
            }

    if _GENERIC_BOT_RE.search(user_agent):
        return {
            "name": "generic-bot", "category": "generic_bot", "avi_weight": 0,
            "reach_mult": 0, "description": "Generic bot",
            "verification_state": "unverified", "verification_method": None,
        }

    return None


def is_bot_request(user_agent: str, ip_address: Optional[str] = None) -> bool:
    return classify_bot(user_agent, ip_address) is not None


def calc_avi(crawler_stats: list[dict]) -> float:
    """
    AI Visibility Index — 0 to 100.
    Weighted by crawler importance × pages crawled × log of total crawls.
    Measures how deeply AI systems are indexing this site.
    """
    score = 0.0
    for stat in crawler_stats:
        weight = AVI_WEIGHTS.get(stat["name"], 0)
        if weight > 0 and stat["unique_pages"] > 0:
            score += weight * stat["unique_pages"] * math.log10(stat["total"] + 1)
    return min(100.0, round(score / 2, 1))


def calc_shadow_reach(crawler_stats: list[dict]) -> int:
    """
    Shadow Reach Index — a relative measure of AI-mediated exposure.
    Weights each crawler's crawl count by its relative audience size.
    Not a literal user count; an index for comparing periods and pages.
    """
    total = 0
    for stat in crawler_stats:
        mult = REACH_MULTS.get(stat["name"], 0)
        if mult > 0:
            total += stat["total"] * mult
    return total // 100
