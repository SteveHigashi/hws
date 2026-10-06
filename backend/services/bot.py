import bisect
import ipaddress
import json
import math
import os
from pathlib import Path
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# Known AI and web crawlers with metadata for analytics
_CRAWLER_REGISTRY = [
    # AI training / inference crawlers
    {"name": "GPTBot",            "pattern": r"GPTBot",              "category": "ai_crawler", "avi_weight": 1.5, "reach_mult": 200, "description": "OpenAI training crawler"},
    {"name": "ChatGPT-User",      "pattern": r"ChatGPT-User",        "category": "ai_crawler", "avi_weight": 1.5, "reach_mult": 200, "description": "OpenAI real-time browsing"},
    {"name": "OAI-SearchBot",     "pattern": r"OAI-SearchBot",       "category": "ai_crawler", "avi_weight": 1.5, "reach_mult": 200, "description": "OpenAI ChatGPT Search indexing"},
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
    # OpenAI publishes a separate prefix feed per crawler purpose, so each name
    # is checked against its own feed rather than a shared pool: an address that
    # is legitimate for ChatGPT-User is not thereby legitimate for GPTBot.
    # No FCrDNS suffix is listed because OpenAI publishes no reverse-DNS
    # contract; inventing one would manufacture evidence.
    "GPTBot": {
        "groups": ("gptbot",),
        "suffixes": (),
    },
    "OAI-SearchBot": {
        "groups": ("oai-searchbot",),
        "suffixes": (),
    },
    "ChatGPT-User": {
        "groups": ("chatgpt-user",),
        "suffixes": (),
    },
    # Ahrefs publishes an official prefix feed. No reverse-DNS contract is
    # claimed here for the same reason as OpenAI: none is published.
    "AhrefsBot": {
        "groups": ("ahrefsbot",),
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


# How old published ranges may get before they stop counting as evidence at all.
# The refresh timer runs weekly, so the default tolerates two consecutive
# failures before verdicts soften: long enough not to flap on a transient
# outage, short enough that genuinely abandoned data stops deciding anything.
#
# Zero or less means NO range data is ever fresh, which disables prefix-based
# verdicts entirely and leaves every claim unverified unless FCrDNS proves it.
# It is deliberately not a switch for trusting the bundled file forever: that
# reading would turn the safest-looking value into the least safe behaviour.
# An operator with no outbound access who genuinely wants to keep standing
# behind a frozen snapshot has to say so in days, explicitly and visibly.
#
# An unparseable value falls back to the default rather than to either extreme.
_DEFAULT_RANGE_MAX_AGE_DAYS = 14
try:
    RANGE_MAX_AGE_DAYS = int(
        os.getenv("HIGASHI_CRAWLER_RANGE_MAX_AGE_DAYS", str(_DEFAULT_RANGE_MAX_AGE_DAYS))
    )
except (TypeError, ValueError):
    RANGE_MAX_AGE_DAYS = _DEFAULT_RANGE_MAX_AGE_DAYS

_METADATA_KEY = "_meta"


def _read_ranges(path: Path) -> tuple[dict[str, list[str]], Optional[datetime]]:
    """Return the crawler families and when the file was generated.

    The generation time is read from the file's own metadata rather than its
    mtime, because mtime is rewritten by packaging, copying and git checkout and
    so says when the file arrived rather than when the data was true. mtime is
    used only as a fallback for files written before stamping existed.
    """
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return {}, None
    if not isinstance(payload, dict):
        return {}, None

    generated_at = None
    meta = payload.get(_METADATA_KEY)
    if isinstance(meta, dict) and isinstance(meta.get("generated_at"), str):
        stamp = meta["generated_at"].strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(stamp)
            generated_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            generated_at = None
    if generated_at is None:
        try:
            generated_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            generated_at = None

    families = {k: v for k, v in payload.items() if k != _METADATA_KEY}
    return families, generated_at


def _ranges_are_fresh(generated_at: Optional[datetime]) -> bool:
    """Whether the ranges are current enough to decide anything.

    Governs both directions: a file too old to accuse with is also too old to
    authenticate with, because a released prefix can be reallocated.
    """
    if RANGE_MAX_AGE_DAYS <= 0:
        # Age-based trust switched off: nothing is ever fresh.
        return False
    if generated_at is None:
        # No provenance means freshness cannot be shown, and an unprovable claim
        # must not become an accusation.
        return False
    age = datetime.now(timezone.utc) - generated_at
    return age <= timedelta(days=RANGE_MAX_AGE_DAYS)


_RANGE_DATA, _RANGE_GENERATED_AT = _read_ranges(_RANGE_FILE)
_PREFIX_INDEX = _PrefixIndex(_RANGE_DATA)


def reload_crawler_ranges(path: Optional[str] = None) -> None:
    """Reload a last-known-good range file, mainly for the scheduled refresher."""
    global _PREFIX_INDEX
    global _RANGE_GENERATED_AT
    data, generated_at = _read_ranges(Path(path) if path else _RANGE_FILE)
    _PREFIX_INDEX = _PrefixIndex(data)
    _RANGE_GENERATED_AT = generated_at


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
    # Published prefixes are usable as evidence only while they are current.
    # Staleness cuts both ways: an operator that ADDS egress makes a stale file
    # accuse legitimate traffic, and an operator that RELEASES a prefix makes a
    # stale file authenticate whoever was allocated it next. The second is the
    # quieter failure, since a forged crawler collects a verified badge instead
    # of a red banner, so an aged file is not allowed to decide either way.
    ranges_usable = _ranges_are_fresh(_RANGE_GENERATED_AT)
    range_data_available = ranges_usable and any(
        _PREFIX_INDEX.has_family(group) for group in groups
    )
    if ranges_usable and groups and _PREFIX_INDEX.contains(address, groups):
        return "verified", "published_prefix"

    suffixes = rule["suffixes"]
    if suffixes and fcrdns_lookup is not None:
        # FCrDNS is accepted as fallback evidence, but core never starts a DNS
        # request: the no-outbound guarantee is stricter than convenience.
        # This path is deliberately NOT gated on the range file's age. It is a
        # live lookup against the operator's own DNS, so it does not go stale
        # the way a cached prefix list does.
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

    # A valid address outside a CURRENT vendor feed, with no independently
    # supplied FCrDNS proof, is a forged claim. Without an authoritative set, or
    # with one too old to stand behind, failed or absent DNS evidence leaves the
    # claim unverified. range_data_available is already false for stale ranges.
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
