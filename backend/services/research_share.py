"""Voluntary research sharing. Separate from Higashi Live on purpose.

An operator may choose to share the aggregate figures Higashi has already worked
out for their own dashboard, so that JotNotes can improve Higashi and Higashi
Live, improve crawler detection, study trends across sites, and publish aggregate
industry research, reports and white papers.

Three things keep this honest:

  - It is OFF unless the operator turned it on. Installing Higashi, buying Live,
    entering a Live key and configuring Live all leave it off.
  - It needs no Live key. An operator who has never bought anything can opt in,
    and an operator who pays for Live is not opted in by paying.
  - It reuses figures the dashboard already derived. There is no second
    collection path, no extra instrumentation and nothing gathered that Higashi
    was not already holding.

What is sent is listed in WHAT_IS_SHARED below and is the whole of it.
"""
import hashlib
from typing import Any, Dict

import httpx

_TIMEOUT = 10.0

# The payload, in the operator's language. The README and the privacy page quote
# this list, and `build_research_payload` is tested against it so the three
# cannot drift apart.
WHAT_IS_SHARED = [
    "an install id, which is a one-way hash - it tells us two reports came from "
    "the same install without telling us which install",
    "the period the figures cover",
    "the kind of site you said this is, and the crawler stance you chose",
    "counts: human pageviews, human sessions, engaged sessions",
    "per crawler: its name, whether it verified, how many hits and how many bytes",
    "the catalogue-walk verdict and the signals behind it",
]

# Deliberately NOT sent. Asserted by the tests.
NEVER_SHARED = (
    "ip", "ip_address", "url", "path", "referer", "referrer",
    "user_agent", "ua", "query_id", "site_id", "email", "key", "token",
    "secret", "password", "host", "hostname", "domain",
)


def install_id(site_id: Any) -> str:
    """A stable, one-way id for an install.

    Reports need to be groupable - two reports from one site are one site's
    trend, not two sites' - but grouping does not need to be reversible. This is
    a SHA-256 of the site id, truncated. It is sent INSTEAD of site_id, never
    alongside it.
    """
    return hashlib.sha256(str(site_id).encode()).hexdigest()[:16]


def build_research_payload(report: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the research payload from the aggregate report already built.

    Takes the dashboard's own report rather than querying again, so research
    sharing cannot drift into collecting more than Higashi already holds. Two
    fields are dropped rather than forwarded:

      site_id  - replaced by the one-way install_id.
      geo      - despite the name these are the operator's own answer-engine
                 probes, including the id of each query they asked. That is the
                 operator's business and is no use for aggregate research.
    """
    return {
        "install_id": install_id(report.get("site_id", "")),
        "period_start": report.get("period_start"),
        "period_end": report.get("period_end"),
        "site_type": report.get("site_type"),
        "stance": report.get("stance"),
        "pageviews_human": report.get("pageviews_human"),
        "sessions_human": report.get("sessions_human"),
        "engaged_sessions": report.get("engaged_sessions"),
        "crawlers": report.get("crawlers"),
        "walk": report.get("walk"),
    }


async def send_research(research_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST to the research endpoint. Never raises into a caller.

    No Live key is sent: research sharing is not a Live entitlement and must not
    require, or imply, a subscription.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{research_url.rstrip('/')}/v1/research",
                json=payload,
            )
        if resp.status_code >= 400:
            return {"error": f"research endpoint returned {resp.status_code}"}
        return resp.json() if resp.content else {"ok": True}
    except Exception as exc:
        return {"error": str(exc)}
