"""The rule-based walk reading: pure functions of a ReportIn.

Shared by the free product (local provider), Bring-your-own-key (as the fallback and
the ceiling) and Higashi Live. No database, no network.
"""
from __future__ import annotations

from .crawlers import CLASS_LABELS, STANCES, crawler_class, refused_classes, stance_of
from .schemas import ACTIONS, ReadingBody, Recommendation, ReportIn


SEARCH_CRAWLERS = {"googlebot", "bingbot", "duckduckbot", "applebot"}
AI_SEARCH_CAVEAT = (
    "Blocking AI training crawlers does not remove you from AI answers in Google or Bing: "
    "those are built from Googlebot and Bingbot, the same crawlers that put you in search. "
    "The only way to leave those answers is to block the search crawlers too, which also removes you from search. "
    "Visitors who arrive from an AI answer are real visitors, and blocking training crawlers does not cost you them."
)
KNOWN_ROBOTS_IGNORERS = {"bytespider"}
SEARCH_REFUSED_CAVEAT = (
    "You chose to refuse search crawlers too. Where you enforce that, the site leaves Google and Bing search "
    "and the AI answers built from those same crawlers, and the visitors they would have sent stop arriving."
)


def _came_refused(report: ReportIn) -> list[str]:
    """Names of crawlers that came although the owner's stance refuses their class."""
    refused = refused_classes(report)
    return [n for n in _names(report.crawlers) if crawler_class(n) in refused]


# Public name for the one question that decides whether a robots.txt block belongs in
# a reading: did a crawler the stance refuses actually come? The local rules have always
# used it; Live asked `ai_stance == "block_all"` instead and so withheld the block from
# paying readers that the free product handed out.
def refused_crawlers_that_came(report: ReportIn) -> list[str]:
    return _came_refused(report)


def _came_welcome(report: ReportIn) -> dict[str, list[str]]:
    """Crawlers the stance allows, grouped by class label, in first-seen order."""
    refused = refused_classes(report)
    out: dict[str, list[str]] = {}
    for n in _names(report.crawlers):
        cls = crawler_class(n)
        if cls not in refused:
            out.setdefault(CLASS_LABELS[cls], []).append(n)
    return out


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
    names = _came_refused(report) or [n for n in _names(report.crawlers) if n.casefold() not in SEARCH_CRAWLERS] or _names(report.crawlers)
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
    stance = stance_of(report)
    refused = refused_classes(report)
    came_refused = _came_refused(report)
    welcome = _came_welcome(report)

    if stance == "allow_all":
        geo = report.geo or []
        if geo:
            facts = [f"{g.engine} {'mentioned' if g.mentioned else 'did not mention'} you" + (" and cited you" if g.cited else "") for g in geo]
            paragraphs.append(". ".join(facts) + ".")
        useful = _names(c for c in report.crawlers if c.verified == "verified")
        if useful:
            paragraphs.append(f"Verified crawlers that may help discovery: {', '.join(useful)}.")
        elif welcome:
            paragraphs.append("Crawlers seen: " + "; ".join(f"{label}: {', '.join(names)}" for label, names in welcome.items()) + ".")
    else:
        seen = "; ".join(f"{label}: {', '.join(names)}" for label, names in welcome.items()) or "none"
        paragraphs.append(f"Crawlers you allow that came: {seen}.")
        refused_labels = ", ".join(CLASS_LABELS[c].split(" (")[0] for c in ("search", "answer_fetcher", "training", "seo_tools") if c in refused)
        if came_refused:
            hits: dict[str, int] = {}
            for c in report.crawlers:
                hits[c.name] = hits.get(c.name, 0) + c.hits
            arrived = ", ".join(f"{n} ({hits[n]:,} hits)" for n in came_refused)
            paragraphs.append(f"You asked to refuse {refused_labels}. These came anyway: {arrived}.")
            paragraphs.append(robots_paragraph(report, product))
        else:
            paragraphs.append(f"You asked to refuse {refused_labels}. None of them came this period.")
        if "search" in refused:
            paragraphs.append(SEARCH_REFUSED_CAVEAT)
        elif "training" in refused:
            paragraphs.append(AI_SEARCH_CAVEAT)

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
        recommendation=deterministic_recommendation(report),
    )


# ---------------------------------------------------------------------------
# Recommendation policy. The evidence sets the most that may be recommended;
# nothing downstream (a model, a template) can raise it. Every action is small
# and reversible, and Higashi never applies any of them itself.
# ---------------------------------------------------------------------------

def action_rank(action: str) -> int:
    return ACTIONS.index(action)


def _training_crawlers(report: ReportIn) -> list[str]:
    """Crawlers the owner's stance refuses that came anyway (the name is historical)."""
    return _came_refused(report)


def max_action(report: ReportIn) -> str:
    """The ceiling: the strongest action the evidence in this report allows."""
    walk = report.walk
    if walk.verdict == "Insufficient data":
        return "none"
    if walk.verdict == "Catalogue walk detected":
        if walk.records_taken_estimate <= 0:
            return "observe"
        return "rate_rule" if walk.distributed_signal else "block_rule"
    if walk.verdict == "Suspicious":
        return "robots" if walk.records_taken_estimate > 0 else "observe"
    # No walk detected: the only thing left to recommend is a robots.txt request,
    # and only when the owner has said training crawlers are unwelcome.
    if _came_refused(report):
        return "robots"
    if any(c.verified == "forged" for c in report.crawlers):
        return "observe"
    return "none"


_ROLLBACK = {
    "none": "",
    "observe": "Nothing to undo: watching changes nothing.",
    "robots": "Remove the lines from robots.txt; crawlers that honour it return on their next visit.",
    "rate_rule": "Delete the rate rule; traffic returns to normal on the next request.",
    "block_rule": "Delete the block rule; the addresses can reach the site again immediately.",
}


def deterministic_recommendation(report: ReportIn) -> Recommendation:
    """The rules' own recommendation, always at or below the ceiling (it *is* the ceiling)."""
    action = max_action(report)
    walk = report.walk
    training = _training_crawlers(report)
    search = [n for n in _names(report.crawlers) if n.casefold() in SEARCH_CRAWLERS]
    exclusions = ["verified search crawlers" + (f" ({', '.join(search)})" if search else ""), "signed-in users", "sitemap and feed fetchers"]
    do_not = ["you are not sure which pages the pattern touched", "a CDN or firewall already applies a rule for this"]

    if action == "none":
        if walk.verdict == "Insufficient data":
            reason = "There is not enough evidence yet. Too few full content responses were seen to judge, so nothing should change."
        else:
            reason = "Nothing in this report calls for a change. Every crawler that came is one your settings allow, and no copying pattern was seen."
        return Recommendation(action="none", reason=reason, confidence="high" if walk.verdict != "Insufficient data" else "low",
                              scope=[], exclusions=[], observe_days=0, rollback="", do_not_use_if=[])

    if action == "observe":
        if walk.verdict == "Suspicious":
            reason = "The signals are weak and no records appear to have been taken. Watch for a week before changing anything."
            confidence = "low"
        elif walk.verdict == "Catalogue walk detected":
            reason = "A walk shape was seen but the record estimate is zero, so the evidence does not yet justify a rule. Watch for a week."
            confidence = "medium"
        else:
            reason = "Some crawlers claimed to be search engines and were not. They took nothing measurable; watch for a week before acting."
            confidence = "medium"
        return Recommendation(action="observe", reason=reason, confidence=confidence, scope=["catalogue and listing pages"],
                              exclusions=exclusions, observe_days=7, rollback=_ROLLBACK["observe"], do_not_use_if=[])

    if action == "robots":
        names = training or _names(report.crawlers)
        touches_search = any(crawler_class(n) == "search" for n in names)
        reason = (f"Ask {', '.join(names)} to stay out with robots.txt. It is a request, not a wall: honest crawlers honour it, "
                  "some ignore it, and it changes nothing for people." + ("" if touches_search else " Search is untouched."))
        return Recommendation(action="robots", reason=reason, confidence="high", scope=["whole site"],
                              exclusions=exclusions, observe_days=0, rollback=_ROLLBACK["robots"],
                              do_not_use_if=["you rely on one of these crawlers for discovery"])

    if action == "rate_rule":
        reason = (f"About {walk.records_taken_estimate:,} records were taken by a pattern spread across many addresses, so blocking "
                  "single addresses would not help. A rate rule on the catalogue pages slows the pattern without touching normal visitors.")
        return Recommendation(action="rate_rule", reason=reason, confidence="high", scope=["catalogue and listing pages"],
                              exclusions=exclusions, observe_days=7, rollback=_ROLLBACK["rate_rule"], do_not_use_if=do_not)

    reason = (f"About {walk.records_taken_estimate:,} records were taken at {walk.per_address_rate:,.1f} requests per address per day "
              "from a small set of addresses. A block rule for that pattern on the catalogue pages is the smallest step that stops it; "
              "keep it narrow and keep the exclusions.")
    return Recommendation(action="block_rule", reason=reason, confidence="high", scope=["catalogue and listing pages"],
                          exclusions=exclusions, observe_days=7, rollback=_ROLLBACK["block_rule"], do_not_use_if=do_not)


def clamp_recommendation(candidate: Recommendation | None, report: ReportIn) -> Recommendation:
    """A recommendation from any other source (a model) may keep its reason only while
    its action stays at or below the ceiling; everything structural comes from the rules."""
    ours = deterministic_recommendation(report)
    if candidate is None:
        return ours
    if action_rank(candidate.action) > action_rank(ours.action):
        return ours
    reason = candidate.reason.strip()
    if not reason or len(reason.split()) > 80:
        return ours
    return ours.model_copy(update={"action": candidate.action, "reason": reason,
                                   "rollback": _ROLLBACK[candidate.action],
                                   "observe_days": ours.observe_days if candidate.action != "none" else 0})
