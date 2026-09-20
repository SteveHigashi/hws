from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, distinct
from datetime import datetime, timedelta
import asyncio
import time
from collections import Counter, defaultdict

from database import get_db
from models.behavior import BehaviorEvent
from models.bot_visit import BotVisit
from models.event import Event
from models.session import Session
from models.site import Site
from routers.auth import get_current_user
from services.traffic_quality import (
    TRAFFIC_CLASSES,
    TRAFFIC_LABELS,
    classify_path,
    classify_session,
    path_from_url,
    quality_confidence,
)

router = APIRouter()


def since(days: int):
    return datetime.utcnow() - timedelta(days=days)


def clean_site_id(site_id):
    """Return a proper UUID object so SQLAlchemy serialises it correctly."""
    import uuid as _uuid
    try:
        return _uuid.UUID(site_id) if site_id else None
    except ValueError:
        return None


def _chunks(items: list, size: int = 800):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _class_bucket(traffic_class: str) -> str:
    if traffic_class in ("verified_human", "likely_human"):
        return "human"
    if traffic_class in ("known_bot", "ai_crawler"):
        return "bot"
    return traffic_class


# Overview, Traffic Quality, Scanner Noise and Suspicious all ask for the same context in
# one page load; compute it once and keep it briefly. Keyed per site and window.
_QUALITY_CACHE: dict = {}
_QUALITY_TTL = 300.0
# Single-flight: a page load fires four requests that all need this context. Without the
# lock each one computed it independently and a single CPU spent minutes on the same work.
_QUALITY_LOCKS: dict = {}


async def _traffic_quality_context(db: AsyncSession, days: int, site_id: str | None = None) -> dict:
    site_uuid = clean_site_id(site_id) if site_id else None
    cache_key = (str(site_uuid), days)
    cached = _QUALITY_CACHE.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    lock = _QUALITY_LOCKS.setdefault(cache_key, asyncio.Lock())
    async with lock:
        cached = _QUALITY_CACHE.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        return await _build_traffic_quality_context(db, days, site_uuid, cache_key)


async def _build_traffic_quality_context(db: AsyncSession, days: int, site_uuid, cache_key) -> dict:
    s = since(days)

    session_conds = [Session.started_at >= s]
    if site_uuid:
        session_conds.append(Session.site_id == site_uuid)

    # Plain column rows, not ORM objects: the classifier only reads a dozen fields and a
    # busy site has 200k+ events in a month. Row objects keep attribute access, so
    # classify_session() and the consumers below are unchanged.
    sessions_result = await db.execute(
        select(Session.id, Session.started_at, Session.page_count, Session.referrer_domain,
               Session.duration_seconds, Session.is_bounce)
        .where(*session_conds)
    )
    sessions = sessions_result.all()
    session_ids = [session.id for session in sessions]

    # One windowed query per table, not 800-id IN() batches: each batch cost ~1.6 s of
    # bind-parameter and row overhead (57 batches for a busy month), while the whole window
    # comes back in one indexed pass in a few seconds. Rows are attached only to sessions
    # in the window, which is what the batches selected anyway.
    session_set = set(session_ids)
    events_by_session = defaultdict(list)
    if session_ids:
        event_cols = (Event.session_id, Event.page_url, Event.referrer, Event.user_agent, Event.is_404,
                      Event.duration_seconds, Event.scroll_depth, Event.screen_width, Event.screen_height,
                      Event.language, Event.lcp, Event.fcp, Event.ttfb, Event.meta)
        event_conds = [Event.timestamp >= s]
        if site_uuid:
            event_conds.append(Event.site_id == site_uuid)
        events_result = await db.execute(
            select(*event_cols).where(*event_conds).order_by(Event.session_id, Event.timestamp)
        )
        for event in events_result.all():
            if event.session_id in session_set:
                events_by_session[event.session_id].append(event)

    behavior_session_ids = set()
    if session_ids:
        behavior_conds = [BehaviorEvent.timestamp >= s]
        if site_uuid:
            behavior_conds.append(BehaviorEvent.site_id == site_uuid)
        behavior_result = await db.execute(
            select(distinct(BehaviorEvent.session_id)).where(*behavior_conds)
        )
        behavior_session_ids.update(row[0] for row in behavior_result.all() if row[0] in session_set)

    quality_by_session = {}
    counts = Counter({traffic_class: 0 for traffic_class in TRAFFIC_CLASSES})
    confidence_totals = Counter()

    for session in sessions:
        quality = classify_session(
            session,
            events_by_session.get(session.id, []),
            session.id in behavior_session_ids,
        )
        quality_by_session[session.id] = quality
        traffic_class = quality["traffic_class"]
        counts[traffic_class] += 1
        confidence_totals[traffic_class] += quality["confidence"]

    bot_conds = [BotVisit.timestamp >= s]
    if site_uuid:
        bot_conds.append(BotVisit.site_id == site_uuid)
    bot_result = await db.execute(
        select(BotVisit.bot_category, func.count(BotVisit.id).label("visits"))
        .where(*bot_conds)
        .group_by(BotVisit.bot_category)
    )
    bot_counts = {row.bot_category: row.visits for row in bot_result.all()}

    total_sessions = len(sessions)
    likely = counts["likely_human"]
    verified = counts["verified_human"]
    has_verified = verified > 0

    ctx = {
        "since": s,
        "sessions": sessions,
        "events_by_session": events_by_session,
        "quality_by_session": quality_by_session,
        "counts": counts,
        "confidence_totals": confidence_totals,
        "bot_counts": bot_counts,
        "total_sessions": total_sessions,
        "real_traffic_estimate": verified + likely,
        "traffic_confidence": quality_confidence(has_verified, likely, total_sessions),
        "has_js_proof": has_verified,
    }
    _QUALITY_CACHE[cache_key] = (time.monotonic() + _QUALITY_TTL, ctx)
    return ctx


def _quality_payload(ctx: dict, days: int) -> dict:
    counts = ctx["counts"]
    confidence_totals = ctx["confidence_totals"]
    total_sessions = ctx["total_sessions"]
    classes = []

    for traffic_class in TRAFFIC_CLASSES:
        count = counts[traffic_class]
        avg_confidence = (
            round(confidence_totals[traffic_class] / count, 2)
            if count
            else None
        )
        classes.append({
            "class": traffic_class,
            "label": TRAFFIC_LABELS[traffic_class],
            "count": count,
            "share": round(count / total_sessions * 100, 1) if total_sessions else 0,
            "confidence": avg_confidence,
        })

    bot_counts = ctx["bot_counts"]
    ai_crawlers = bot_counts.get("ai_crawler", 0)
    known_bots = sum(bot_counts.values()) - ai_crawlers

    return {
        "days": days,
        "total_sessions": total_sessions,
        "classes": classes,
        "verified_humans": counts["verified_human"],
        "likely_humans": counts["likely_human"],
        "suspicious_sessions": counts["suspicious"],
        "unknown_sessions": counts["unknown"],
        "real_traffic_estimate": ctx["real_traffic_estimate"],
        "traffic_confidence": ctx["traffic_confidence"],
        "has_js_proof": ctx["has_js_proof"],
        "known_bots": known_bots,
        "ai_crawlers": ai_crawlers,
        "bot_visits": sum(bot_counts.values()),
        "bot_counts": bot_counts,
        "note": (
            "No JS-tracked sessions yet; human estimate is based on log signals."
            if not ctx["has_js_proof"] and total_sessions
            else None
        ),
    }


def _event_day(value) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Sites list
# ---------------------------------------------------------------------------

@router.get("/sites")
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Site).where(Site.active == True).order_by(Site.name))
    sites = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "domain": s.domain,
            "tracker_key": s.tracker_key,
        }
        for s in sites
    ]


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def overview(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)

    def event_filter(*extra):
        conds = [Event.timestamp >= s, Event.is_bot == False, *extra]
        if site_id:
            conds.append(Event.site_id == clean_site_id(site_id))
        return conds

    def session_filter(*extra):
        conds = [Session.started_at >= s, *extra]
        if site_id:
            conds.append(Session.site_id == clean_site_id(site_id))
        return conds

    views_r = await db.execute(select(func.count(Event.id)).where(*event_filter(Event.is_404 == False)))
    visitors_r = await db.execute(select(func.count(func.distinct(Event.ip_hash))).where(*event_filter()))
    sessions_r = await db.execute(select(func.count(Session.id)).where(*session_filter()))
    bounces_r = await db.execute(select(func.count(Session.id)).where(*session_filter(Session.is_bounce == True)))
    returning_r = await db.execute(select(func.count(Session.id)).where(*session_filter(Session.is_returning == True)))
    avg_dur_r = await db.execute(select(func.avg(Session.duration_seconds)).where(*session_filter(Session.duration_seconds.isnot(None))))
    avg_pages_r = await db.execute(select(func.avg(Session.page_count)).where(*session_filter()))
    fournot_r = await db.execute(select(func.count(Event.id)).where(*event_filter(Event.is_404 == True)))

    views = views_r.scalar() or 0
    visitors = visitors_r.scalar() or 0
    sessions = sessions_r.scalar() or 0
    bounces = bounces_r.scalar() or 0
    returning = returning_r.scalar() or 0
    avg_dur = avg_dur_r.scalar()
    avg_pages = avg_pages_r.scalar()
    errors_404 = fournot_r.scalar() or 0
    quality_ctx = await _traffic_quality_context(db, days, site_id)
    quality = _quality_payload(quality_ctx, days)

    return {
        "page_views": views,
        "unique_visitors": visitors,
        "sessions": sessions,
        "bounce_rate": round((bounces / sessions * 100), 1) if sessions else 0,
        "returning_visitor_rate": round((returning / sessions * 100), 1) if sessions else 0,
        "avg_session_duration": round(avg_dur, 1) if avg_dur else None,
        "avg_pages_per_session": round(float(avg_pages), 2) if avg_pages else None,
        "errors_404": errors_404,
        "period_days": days,
        "verified_humans": quality["verified_humans"],
        "likely_humans": quality["likely_humans"],
        "known_bots": quality["known_bots"],
        "ai_crawlers": quality["ai_crawlers"],
        "suspicious_sessions": quality["suspicious_sessions"],
        "unknown_sessions": quality["unknown_sessions"],
        "real_traffic_estimate": quality["real_traffic_estimate"],
        "traffic_confidence": quality["traffic_confidence"],
        "has_js_proof": quality["has_js_proof"],
    }


# ---------------------------------------------------------------------------
# Top pages
# ---------------------------------------------------------------------------

@router.get("/top-pages")
async def top_pages(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    traffic: str = Query("all", pattern="^(all|humans|ai_crawlers|suspicious)$"),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    site_uuid = clean_site_id(site_id) if site_id else None

    if traffic == "ai_crawlers":
        conds = [BotVisit.timestamp >= s, BotVisit.bot_category == "ai_crawler"]
        if site_uuid:
            conds.append(BotVisit.site_id == site_uuid)
        result = await db.execute(
            select(BotVisit.page_path, func.count(BotVisit.id).label("views"))
            .where(*conds)
            .group_by(BotVisit.page_path)
            .order_by(desc("views"))
            .limit(limit)
        )
        return [
            {"page": row.page_path, "views": row.views, "avg_duration": None, "avg_scroll": None}
            for row in result
        ]

    if traffic in ("humans", "suspicious"):
        ctx = await _traffic_quality_context(db, days, site_id)
        wanted = {"verified_human", "likely_human"} if traffic == "humans" else {"suspicious"}
        session_ids = [
            sid for sid, quality in ctx["quality_by_session"].items()
            if quality["traffic_class"] in wanted
        ]
        page_counts = Counter()
        duration_totals = Counter()
        duration_counts = Counter()
        scroll_totals = Counter()
        scroll_counts = Counter()
        for sid in session_ids:
            for event in ctx["events_by_session"].get(sid, []):
                if getattr(event, "is_404", False):
                    continue
                page_counts[event.page_url] += 1
                if event.duration_seconds is not None:
                    duration_totals[event.page_url] += event.duration_seconds
                    duration_counts[event.page_url] += 1
                if event.scroll_depth is not None:
                    scroll_totals[event.page_url] += event.scroll_depth
                    scroll_counts[event.page_url] += 1
        rows = page_counts.most_common(limit)
        return [
            {
                "page": page,
                "views": views,
                "avg_duration": round(duration_totals[page] / duration_counts[page], 1) if duration_counts[page] else None,
                "avg_scroll": round(scroll_totals[page] / scroll_counts[page]) if scroll_counts[page] else None,
            }
            for page, views in rows
        ]

    conds = [Event.timestamp >= s, Event.is_bot == False, Event.is_404 == False]
    if site_uuid:
        conds.append(Event.site_id == site_uuid)
    result = await db.execute(
        select(
            Event.page_url,
            func.count(Event.id).label("views"),
            func.avg(Event.duration_seconds).label("avg_duration"),
            func.avg(Event.scroll_depth).label("avg_scroll"),
        )
        .where(*conds)
        .group_by(Event.page_url)
        .order_by(desc("views"))
        .limit(limit)
    )
    return [
        {
            "page": row.page_url,
            "views": row.views,
            "avg_duration": round(float(row.avg_duration), 1) if row.avg_duration else None,
            "avg_scroll": round(float(row.avg_scroll)) if row.avg_scroll else None,
        }
        for row in result
    ]


# ---------------------------------------------------------------------------
# Traffic quality
# ---------------------------------------------------------------------------

@router.get("/traffic-quality")
async def traffic_quality(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    ctx = await _traffic_quality_context(db, days, site_id)
    return _quality_payload(ctx, days)


@router.get("/traffic-quality/timeseries")
async def traffic_quality_timeseries(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    ctx = await _traffic_quality_context(db, days, site_id)
    rows = defaultdict(lambda: Counter({traffic_class: 0 for traffic_class in TRAFFIC_CLASSES}))

    for session in ctx["sessions"]:
        day = _event_day(session.started_at)
        traffic_class = ctx["quality_by_session"][session.id]["traffic_class"]
        rows[day][traffic_class] += 1

    bot_conds = [BotVisit.timestamp >= ctx["since"]]
    site_uuid = clean_site_id(site_id) if site_id else None
    if site_uuid:
        bot_conds.append(BotVisit.site_id == site_uuid)
    bot_result = await db.execute(
        select(
            func.strftime("%Y-%m-%d", BotVisit.timestamp).label("day"),
            BotVisit.bot_category,
            func.count(BotVisit.id).label("visits"),
        )
        .where(*bot_conds)
        .group_by("day", BotVisit.bot_category)
    )
    for row in bot_result.all():
        if row.bot_category == "ai_crawler":
            rows[row.day]["ai_crawler_visits"] += row.visits
        else:
            rows[row.day]["known_bot_visits"] += row.visits

    output = []
    for day in sorted(rows):
        item = {"date": day}
        for traffic_class in TRAFFIC_CLASSES:
            item[traffic_class] = rows[day][traffic_class]
        item["known_bot_visits"] = rows[day]["known_bot_visits"]
        item["ai_crawler_visits"] = rows[day]["ai_crawler_visits"]
        output.append(item)
    return output


@router.get("/suspicious-traffic")
async def suspicious_traffic(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    ctx = await _traffic_quality_context(db, days, site_id)
    reason_counts = Counter()
    path_counts = Counter()
    ua_counts = Counter()

    for sid, quality in ctx["quality_by_session"].items():
        if quality["traffic_class"] != "suspicious":
            continue
        for reason in quality["reasons"]:
            reason_counts[reason] += 1
        for event in ctx["events_by_session"].get(sid, []):
            path_counts[path_from_url(event.page_url)] += 1
            if event.user_agent:
                ua_counts[event.user_agent[:180]] += 1

    return {
        "sessions": ctx["counts"]["suspicious"],
        "top_reasons": [{"reason": reason, "sessions": count} for reason, count in reason_counts.most_common(limit)],
        "top_paths": [{"path": path, "hits": count} for path, count in path_counts.most_common(limit)],
        "top_user_agents": [{"user_agent": ua, "hits": count} for ua, count in ua_counts.most_common(limit)],
    }


@router.get("/human-pages")
async def human_pages(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    return await top_pages(days=days, limit=limit, traffic="humans", site_id=site_id, db=db, _=_)


@router.get("/seo-404s")
async def seo_404s(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(25, ge=1, le=100),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.is_404 == True]
    site_uuid = clean_site_id(site_id) if site_id else None
    if site_uuid:
        conds.append(Event.site_id == site_uuid)

    result = await db.execute(select(Event).where(*conds))
    buckets = {
        "seo_actionable": Counter(),
        "scanner_security": Counter(),
        "platform_residue": Counter(),
    }

    for event in result.scalars().all():
        path = path_from_url(event.page_url)
        path_class, _ = classify_path(path)
        ua_class = "scanner" if event.user_agent and any(s in event.user_agent.lower() for s in ("l9scan", "leakix", "censys", "shodan", "zgrab", "masscan")) else ""
        if path_class == "scanner" or ua_class == "scanner":
            buckets["scanner_security"][path] += 1
        elif path_class == "platform_residue":
            buckets["platform_residue"][path] += 1
        else:
            buckets["seo_actionable"][path] += 1

    return {
        "summary": {key: sum(counter.values()) for key, counter in buckets.items()},
        "seo_actionable": [{"page": page, "hits": hits} for page, hits in buckets["seo_actionable"].most_common(limit)],
        "scanner_security": [{"page": page, "hits": hits} for page, hits in buckets["scanner_security"].most_common(limit)],
        "platform_residue": [{"page": page, "hits": hits} for page, hits in buckets["platform_residue"].most_common(limit)],
    }


# ---------------------------------------------------------------------------
# Exit pages
# ---------------------------------------------------------------------------

@router.get("/exit-pages")
async def exit_pages(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Session.started_at >= s, Session.exit_page.isnot(None)]
    if site_id:
        conds.append(Session.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Session.exit_page, func.count(Session.id).label("exits"))
        .where(*conds)
        .group_by(Session.exit_page)
        .order_by(desc("exits"))
        .limit(limit)
    )
    return [{"page": row.exit_page, "exits": row.exits} for row in result]


# ---------------------------------------------------------------------------
# New vs returning
# ---------------------------------------------------------------------------

@router.get("/new-vs-returning")
async def new_vs_returning(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Session.started_at >= s]
    if site_id:
        conds.append(Session.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(
            Session.is_returning,
            func.count(Session.id).label("sessions"),
        )
        .where(*conds)
        .group_by(Session.is_returning)
    )
    rows = {r.is_returning: r.sessions for r in result}
    new_s = rows.get(False, 0)
    ret_s = rows.get(True, 0)
    total = new_s + ret_s
    return {
        "new": new_s,
        "returning": ret_s,
        "new_pct": round((new_s / total * 100), 1) if total else 0,
        "returning_pct": round((ret_s / total * 100), 1) if total else 0,
    }


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

@router.get("/not-found")
async def not_found_pages(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.is_404 == True]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Event.page_url, func.count(Event.id).label("hits"))
        .where(*conds)
        .group_by(Event.page_url)
        .order_by(desc("hits"))
        .limit(limit)
    )
    return [{"page": row.page_url, "hits": row.hits} for row in result]


# ---------------------------------------------------------------------------
# UTM campaigns
# ---------------------------------------------------------------------------

@router.get("/utm-campaigns")
async def utm_campaigns(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Session.started_at >= s, Session.utm_source.isnot(None)]
    if site_id:
        conds.append(Session.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(
            Session.utm_source,
            Session.utm_medium,
            Session.utm_campaign,
            func.count(Session.id).label("sessions"),
        )
        .where(*conds)
        .group_by(Session.utm_source, Session.utm_medium, Session.utm_campaign)
        .order_by(desc("sessions"))
        .limit(50)
    )
    return [
        {
            "source": r.utm_source,
            "medium": r.utm_medium,
            "campaign": r.utm_campaign,
            "sessions": r.sessions,
        }
        for r in result
    ]


# ---------------------------------------------------------------------------
# Search queries
# ---------------------------------------------------------------------------

@router.get("/search-queries")
async def search_queries(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.search_query.isnot(None)]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Event.search_query, func.count(Event.id).label("arrivals"))
        .where(*conds)
        .group_by(Event.search_query)
        .order_by(desc("arrivals"))
        .limit(limit)
    )
    return [{"query": r.search_query, "arrivals": r.arrivals} for r in result]


# ---------------------------------------------------------------------------
# Traffic sources
# ---------------------------------------------------------------------------

@router.get("/traffic-sources")
async def traffic_sources(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Session.started_at >= s, Session.referrer_domain.isnot(None)]
    if site_id:
        conds.append(Session.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Session.referrer_domain, func.count(Session.id).label("sessions"))
        .where(*conds)
        .group_by(Session.referrer_domain)
        .order_by(desc("sessions"))
        .limit(limit)
    )
    return [{"source": row.referrer_domain, "sessions": row.sessions} for row in result]


# ---------------------------------------------------------------------------
# Geo
# ---------------------------------------------------------------------------

@router.get("/geo")
async def geo_breakdown(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.is_bot == False, Event.country.isnot(None)]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Event.country, func.count(func.distinct(Event.ip_hash)).label("visitors"))
        .where(*conds)
        .group_by(Event.country)
        .order_by(desc("visitors"))
    )
    return [{"country": row.country, "visitors": row.visitors} for row in result]


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@router.get("/devices")
async def device_breakdown(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.is_bot == False]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Event.device_type, func.count(Event.id).label("views"))
        .where(*conds)
        .group_by(Event.device_type)
    )
    return [{"device": row.device_type, "views": row.views} for row in result]


# ---------------------------------------------------------------------------
# Browsers
# ---------------------------------------------------------------------------

@router.get("/browsers")
async def browser_breakdown(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.is_bot == False, Event.browser.isnot(None)]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(Event.browser, func.count(Event.id).label("views"))
        .where(*conds)
        .group_by(Event.browser)
        .order_by(desc("views"))
        .limit(10)
    )
    return [{"browser": row.browser, "views": row.views} for row in result]


# ---------------------------------------------------------------------------
# Timeseries
# ---------------------------------------------------------------------------

@router.get("/timeseries")
async def timeseries(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = since(days)
    conds = [Event.timestamp >= s, Event.is_bot == False]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(
            func.strftime("%Y-%m-%d", Event.timestamp).label("day"),
            func.count(Event.id).label("views"),
            func.count(func.distinct(Event.ip_hash)).label("visitors"),
        )
        .where(*conds)
        .group_by("day")
        .order_by("day")
    )
    return [{"date": row.day, "views": row.views, "visitors": row.visitors} for row in result]


# ---------------------------------------------------------------------------
# Live count (visitors in last 5 minutes)
# ---------------------------------------------------------------------------

@router.get("/live-count")
async def live_count(
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    conds = [Event.timestamp >= cutoff, Event.is_bot == False]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(func.count(func.distinct(Event.ip_hash))).where(*conds)
    )
    return {"count": result.scalar() or 0}


# ---------------------------------------------------------------------------
# Recent visitors feed
# ---------------------------------------------------------------------------

@router.get("/recent-visitors")
async def recent_visitors(
    limit: int = Query(10, ge=1, le=50),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    conds = [Event.is_bot == False]
    if site_id:
        conds.append(Event.site_id == clean_site_id(site_id))
    result = await db.execute(
        select(
            Event.timestamp,
            Event.page_url,
            Event.country,
            Event.referrer,
            Event.device_type,
        )
        .where(*conds)
        .order_by(desc(Event.timestamp))
        .limit(limit)
    )
    rows = []
    for row in result:
        referrer_domain = None
        if row.referrer:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(row.referrer)
                referrer_domain = parsed.netloc or None
            except Exception:
                pass
        rows.append({
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "page_url": row.page_url,
            "country": row.country,
            "referrer_domain": referrer_domain,
            "device_type": row.device_type,
        })
    return rows
