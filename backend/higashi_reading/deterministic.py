"""The rule-based walk reading: pure functions of a ReportIn.

Shared by the free product (local provider), Bring-your-own-key (as the fallback and
the ceiling) and Higashi Live. No database, no network.
"""
from __future__ import annotations

from .schemas import ReadingBody, ReportIn


SEARCH_CRAWLERS = {"googlebot", "bingbot", "duckduckbot", "applebot"}
AI_SEARCH_CAVEAT = (
    "Blocking AI training crawlers does not remove you from AI answers in Google or Bing: "
    "those are built from Googlebot and Bingbot, the same crawlers that put you in search. "
    "The only way to leave those answers is to block the search crawlers too, which also removes you from search. "
    "Visitors who arrive from an AI answer are real visitors, and blocking training crawlers does not cost you them."
)
KNOWN_ROBOTS_IGNORERS = {"bytespider"}


def size_bucket(pageviews: int) -> str:
    if pageviews < 1_000:
        return "<1k"
    if pageviews < 10_000:
        return "1k-10k"
    if pageviews < 100_000:
        return "10k-100k"
    return ">100k"


def changes_between(current: ReportIn, previous: ReportIn | None) -> list[str]:
    if previous is None:
        return []
    changes: list[str] = []
    old = {item.name: item for item in previous.crawlers}
    new = {item.name: item for item in current.crawlers}
    for name in sorted(new.keys() - old.keys(), key=str.casefold):
        changes.append(f"New crawler: {name}.")
    for name in sorted(old.keys() - new.keys(), key=str.casefold):
        changes.append(f"Crawler gone: {name}.")
    for name in sorted(old.keys() & new.keys(), key=str.casefold):
        before, after = old[name].hits, new[name].hits
        if before == 0 and after > 0:
            changes.append(f"{name} rose from 0 to {after:,} hits.")
        elif before > 0 and after >= before * 2:
            changes.append(f"{name} hits rose at least 2x, from {before:,} to {after:,}.")
        elif after * 2 <= before and after != before:
            changes.append(f"{name} hits fell at least 2x, from {before:,} to {after:,}.")
    if current.walk.verdict != previous.walk.verdict:
        changes.append(f"Walk verdict changed from {previous.walk.verdict} to {current.walk.verdict}.")
    old_geo = {(g.engine, g.query_id): (g.mentioned, g.cited) for g in (previous.geo or [])}
    new_geo = {(g.engine, g.query_id): (g.mentioned, g.cited) for g in (current.geo or [])}
    for key in sorted(old_geo.keys() | new_geo.keys()):
        if old_geo.get(key) != new_geo.get(key):
            changes.append(f"GEO result changed for {key[0]} query {key[1]}.")
    return changes


def headline(report: ReportIn) -> str:
    forged = [c for c in report.crawlers if c.verified == "forged"]
    if report.ai_stance == "found" and report.geo:
        mentioned = [g.engine for g in report.geo if g.mentioned]
        missed = [g.engine for g in report.geo if not g.mentioned]
        if mentioned and missed:
            return f"{', '.join(mentioned)} mentioned you, {', '.join(missed)} did not"
    if report.walk.verdict == "Catalogue walk detected":
        return "A scraper walked your catalogue"
    if forged:
        return f"{len(forged)} crawler{'s are' if len(forged) != 1 else ' is'} lying about who they are"
    return "Nothing unusual this week"


def robots_paragraph(report: ReportIn, product: str = "Higashi") -> str:
    names = [n for n in _names(report.crawlers) if n.casefold() not in SEARCH_CRAWLERS]
    if not names:
        names = _names(report.crawlers)
    lines = "\n".join(f"User-agent: {name}\nDisallow: /" for name in names) or "User-agent: *\nDisallow: /"
    ignorers = [name for name in names if name.casefold() in KNOWN_ROBOTS_IGNORERS]
    note = (
        f" Known to ignore robots.txt: {', '.join(ignorers)}."
        if ignorers else " None of these are on the current known-ignore list."
    )
    return f"Paste this into robots.txt:\n{lines}\n{product} reports what arrived. It does not sit in front of your site.{note}"


def _names(crawlers) -> list[str]:
    """Crawler names once each, in first-seen order: verified and unverified hits of one
    crawler arrive as separate entries and must not read as two crawlers."""
    seen: list[str] = []
    for c in crawlers:
        if c.name not in seen:
            seen.append(c.name)
    return seen


def no_comparison_notes(report: ReportIn) -> list[str]:
    """What a local reading says instead of benchmarks: it has no other sites to compare with."""
    return [f"{name}: no comparison to other sites (that needs Higashi Live)." for name in _names(report.crawlers)]


def deterministic_reading(
    report: ReportIn,
    changes: list[str] | None = None,
    benchmarks: list[str] | None = None,
    unavailable: list[str] | None = None,
    product: str = "Higashi",
) -> ReadingBody:
    """The rule-based reading. Free, local, no model.

    `changes`, `benchmarks` and `unavailable` are what only a service with history and
    other sites can supply; the free product passes none of them and gets an honest
    reading that says so. `product` names who is speaking in the robots.txt paragraph.
    """
    changes = changes or []
    benchmarks = benchmarks or []
    unavailable = unavailable if unavailable is not None else no_comparison_notes(report)
    paragraphs: list[str] = []
    if report.ai_stance == "found":
        geo = report.geo or []
        if geo:
            facts = [f"{g.engine} {'mentioned' if g.mentioned else 'did not mention'} you" + (" and cited you" if g.cited else "") for g in geo]
            paragraphs.append(". ".join(facts) + ".")
        useful = _names(c for c in report.crawlers if c.verified == "verified")
        if useful:
            paragraphs.append(f"Verified crawlers that may help discovery: {', '.join(useful)}.")
    elif report.ai_stance == "block_all":
        hits: dict[str, int] = {}
        for c in report.crawlers:
            hits[c.name] = hits.get(c.name, 0) + c.hits
        arrived = ", ".join(f"{name} ({n:,} hits)" for name, n in hits.items()) or "No AI crawlers"
        paragraphs.append(f"AI crawlers seen: {arrived}.")
        paragraphs.append(robots_paragraph(report, product))
        paragraphs.append(AI_SEARCH_CAVEAT)
    else:
        search = [n for n in _names(report.crawlers) if n.casefold() in SEARCH_CRAWLERS]
        training = [n for n in _names(report.crawlers) if n.casefold() not in SEARCH_CRAWLERS]
        paragraphs.append(f"Search crawlers seen: {', '.join(search) or 'none'}. AI training crawlers to consider blocking: {', '.join(training) or 'none'}.")

    walk = report.walk.verdict
    if walk == "No walk detected":
        paragraphs.append("No walk detected. This does not prove that copying did not happen.")
    elif walk == "Suspicious":
        paragraphs.append("Suspicious. The supporting signals are weak because neither primary walk shape was proven.")
    elif walk == "Insufficient data":
        paragraphs.append("Insufficient data. There were too few full content responses to judge.")
    else:
        paragraphs.append(
            f"Catalogue walk detected. About {report.walk.records_taken_estimate:,} records may have been taken. "
            "There are not enough sites yet to compare that estimate."
        )
    paragraphs.extend(benchmarks)
    paragraphs.extend(unavailable)
    return ReadingBody(
        headline=headline(report),
        paragraphs=paragraphs,
        verdict=walk,
        changes=changes,
        benchmarks=benchmarks,
    )
