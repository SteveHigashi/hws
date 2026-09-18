"""
Deception detection — catch bots that LIE about who they are.

WHY THIS EXISTS
`services/bot.py` classifies by NAME: it matches "GPTBot", "AhrefsBot",
"Googlebot" and ~40 more against the user-agent. That works for the large
majority of crawlers, because most announce themselves honestly.

It cannot see a bot that claims to be a person. Three real cases, all found by
hand in nginx logs on 2026-08-04 and all invisible to a name registry:

  1. A user-agent claiming "Opera/8.39 ... Presto/2.9.171". Presto is a
     rendering engine Opera discontinued in 2013, and that exact version string
     never shipped. No name in it matches any known bot.
  2. PetalBot evading its own user-agent block by presenting as
     "Mozilla/5.0 (Linux; Android 7.0) ... Mobile Safari" — from Huawei Cloud
     server space. A phone browser cannot originate from a VPC.
  3. Clients rotating fake search-engine referrers (claiming Google on one
     request, Yahoo the next, Baidu the next) to look like organic traffic and
     to slip past controls that treat search referrals leniently.

This module adds the missing layer: instead of asking "does this name match a
known bot", it asks "is this self-description internally consistent". Each
signal is a contradiction between two things the client told us, or between
what it claims and where it actually came from.

DESIGN
- Returns REASONS, never a bare boolean. The dashboard should be able to show
  *why* something was judged non-human, so a user can disagree with it. This
  follows the project's "measurement tool, not an optimization playbook"
  positioning: report the evidence, let the human conclude.
- `confidence` is deliberately conservative. A single weak signal is reported
  but does not on its own mark traffic as fake.
- PRIVACY: the caller passes a raw IP so the cloud-range test can run, but this
  module never stores, logs or returns it. Only the verdict leaves the function,
  so the existing ip_hash-only storage model is unchanged.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Optional, TypedDict


class Verdict(TypedDict):
    deceptive: bool
    confidence: str          # "high" | "medium" | "low" | "none"
    reasons: list[str]
    signals: list[str]       # machine-readable signal keys, for aggregation


# ─────────────────────────────────────────────────────────────────────────────
# Signal 1 — impossible or long-dead browser engines
# ─────────────────────────────────────────────────────────────────────────────
# A real browser auto-updates. A user-agent naming an engine that has not
# shipped for a decade is not an old machine, it is a fabricated string: the
# engines below cannot reach a modern TLS-terminated site in a working state.

_DEAD_ENGINE_PATTERNS = [
    # Opera's Presto engine was retired in 2013 (Opera 12 was the last).
    (re.compile(r"Presto/[\d.]+", re.I), "claims Opera Presto, an engine retired in 2013"),
    # Trident/IE. IE11 (Trident/7.0) died in 2022; anything older is fabricated.
    (re.compile(r"MSIE [1-7]\.0", re.I), "claims Internet Explorer 7 or older"),
    (re.compile(r"Trident/[1-3]\.0", re.I), "claims a Trident version that predates IE8"),
    # Netscape / very old Gecko.
    (re.compile(r"Netscape", re.I), "claims Netscape"),
]

# Version-number sanity. Chrome and Firefox ship every few weeks; a 2026 client
# reporting a version this old is either a bot or a museum piece, and museum
# pieces do not browse a directory at scale.
_CHROME_VER = re.compile(r"Chrome/(\d+)\.", re.I)
_FIREFOX_VER = re.compile(r"Firefox/(\d+)\.", re.I)
_CHROME_MIN_PLAUSIBLE = 70    # Chrome 70 = late 2018
_FIREFOX_MIN_PLAUSIBLE = 70   # Firefox 70 = late 2019


# ─────────────────────────────────────────────────────────────────────────────
# Signal 2 — a consumer browser arriving from cloud SERVER space
# ─────────────────────────────────────────────────────────────────────────────
# Phones and laptops sit behind consumer ISPs. They do not originate inside a
# cloud provider's compute range. A "Mobile Safari" user-agent from a VPC is
# therefore fabricated by construction, no name-matching required.
#
# Deliberately conservative: these are compute ranges, NOT the consumer-facing
# CDN/edge ranges of the same companies, because real users legitimately appear
# behind corporate VPNs and some mobile carriers CGNAT through cloud space.

_CLOUD_RANGES = [
    # Huawei Cloud (this is exactly how PetalBot evaded its UA block)
    "114.119.128.0/19",
    # AWS EC2 (major compute blocks)
    "3.0.0.0/9", "13.32.0.0/12", "18.128.0.0/9", "52.0.0.0/10", "54.64.0.0/11",
    # Google Cloud compute. Two /10s, not one — 34.128.0.0/10 covers 34.128–34.191
    # and was missed on the first pass, which let a real forged-referral case through.
    "34.64.0.0/10", "34.128.0.0/10", "35.184.0.0/13", "35.192.0.0/12",
    # Microsoft Azure compute
    "20.0.0.0/8", "40.64.0.0/10",
    # Alibaba Cloud
    "47.74.0.0/15", "47.88.0.0/14",
    # DigitalOcean / Linode / Hetzner / OVH — common scraper hosts
    "165.227.0.0/16", "159.65.0.0/16", "139.59.0.0/16",
    "172.104.0.0/15", "45.79.0.0/16",
    "5.9.0.0/16", "78.46.0.0/15", "94.130.0.0/16",
    "51.38.0.0/16", "51.75.0.0/16", "51.83.0.0/16",
]

_CLOUD_NETS = [ipaddress.ip_network(c) for c in _CLOUD_RANGES]

# A user-agent that claims to be a human-driven browser (as opposed to a
# self-declared bot, which bot.py already handles honestly).
_CONSUMER_BROWSER_RE = re.compile(
    r"(Mobile Safari|iPhone|iPad|Android.*Chrome|Windows NT.*Chrome|"
    r"Macintosh.*Safari|Windows NT.*Firefox|Macintosh.*Chrome)",
    re.I,
)


def _in_cloud_range(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version != 4:
        return False          # IPv6 cloud ranges not enumerated; skip rather than guess
    return any(addr in net for net in _CLOUD_NETS)


# ─────────────────────────────────────────────────────────────────────────────
# Signal 3 — a search-engine referral that cannot be real
# ─────────────────────────────────────────────────────────────────────────────
# A genuine Google click comes from a person on a consumer connection. A
# "referred by Google" hit originating inside a datacenter is a forged referrer,
# usually to blend into analytics or to pass controls that trust search traffic.

_SEARCH_REFERRER_RE = re.compile(
    r"^https?://(www\.)?(google|bing|yahoo|baidu|yandex|duckduckgo|ecosia)\.",
    re.I,
)


def _search_engine_of(referrer: Optional[str]) -> Optional[str]:
    if not referrer:
        return None
    m = _SEARCH_REFERRER_RE.match(referrer.strip())
    return m.group(2).lower() if m else None


# ─────────────────────────────────────────────────────────────────────────────
# Per-request analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze(user_agent: str, client_ip: str = "", referrer: Optional[str] = None) -> Verdict:
    """
    Judge whether a request's self-description is internally consistent.

    Call this only for traffic `bot.py` did NOT already classify — an honest
    self-declared crawler is not deceptive, it is just a crawler.

    The IP is used for range comparison and is never retained or returned.
    """
    reasons: list[str] = []
    signals: list[str] = []
    ua = user_agent or ""

    # 1. dead / impossible engines
    for pattern, why in _DEAD_ENGINE_PATTERNS:
        if pattern.search(ua):
            reasons.append(why)
            signals.append("dead_engine")
            break

    # 1b. implausible version numbers on a live engine
    m = _CHROME_VER.search(ua)
    if m and int(m.group(1)) < _CHROME_MIN_PLAUSIBLE:
        reasons.append(f"claims Chrome {m.group(1)}, far older than any maintained release")
        signals.append("stale_version")
    m = _FIREFOX_VER.search(ua)
    if m and int(m.group(1)) < _FIREFOX_MIN_PLAUSIBLE:
        reasons.append(f"claims Firefox {m.group(1)}, far older than any maintained release")
        signals.append("stale_version")

    claims_browser = bool(_CONSUMER_BROWSER_RE.search(ua))
    from_cloud = bool(client_ip) and _in_cloud_range(client_ip)

    # 2. consumer browser from cloud server space
    if claims_browser and from_cloud:
        reasons.append("presents a consumer browser but originates from cloud server space")
        signals.append("browser_from_datacenter")

    # 3. search referral from cloud server space
    engine = _search_engine_of(referrer)
    if engine and from_cloud:
        reasons.append(f"claims a {engine} referral but originates from cloud server space")
        signals.append("forged_search_referrer")

    # 4. empty user-agent alongside a search referral — real browsers always
    #    send a user-agent, so this pairing is contradictory.
    if engine and not ua.strip():
        reasons.append(f"claims a {engine} referral but sent no user-agent")
        signals.append("forged_search_referrer")

    strong = {"browser_from_datacenter", "forged_search_referrer", "dead_engine"}
    n_strong = len(strong.intersection(signals))
    if n_strong >= 2:
        confidence = "high"
    elif n_strong == 1:
        confidence = "medium"
    elif signals:
        confidence = "low"
    else:
        confidence = "none"

    return {
        "deceptive": bool(signals),
        "confidence": confidence,
        "reasons": reasons,
        "signals": signals,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cross-request pattern: referrer rotation
# ─────────────────────────────────────────────────────────────────────────────
# The strongest spoofing tell is only visible across requests. A real visitor
# arrives from one search engine. A scraper rotating fabricated referrers claims
# several different ones from the same origin. On viabandwidth this cleanly
# separated 3 spoofing clients from ~500 ordinary ones.
#
# Kept as a pure function over already-aggregated counts so the caller owns the
# query and no visitor identifier passes through this module.

ROTATION_THRESHOLD = 3


def rotation_verdict(distinct_engines: int, window_desc: str = "the period") -> Verdict:
    """
    Judge one visitor's referrer pattern.

    `distinct_engines` = how many DIFFERENT search engines that visitor claimed
    to arrive from. Two is plausible over a long window. Three or more is not.
    """
    if distinct_engines >= ROTATION_THRESHOLD:
        return {
            "deceptive": True,
            "confidence": "high",
            "reasons": [
                f"claimed {distinct_engines} different search engines as the referrer "
                f"within {window_desc}; a real visitor arrives from one"
            ],
            "signals": ["referrer_rotation"],
        }
    return {"deceptive": False, "confidence": "none", "reasons": [], "signals": []}


SIGNAL_LABELS = {
    "dead_engine":            "Dead browser engine",
    "stale_version":          "Implausible browser version",
    "browser_from_datacenter": "Browser UA from server space",
    "forged_search_referrer": "Forged search referral",
    "referrer_rotation":      "Rotating search referrers",
}
