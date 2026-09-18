from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, Integer
from datetime import datetime, timedelta
from typing import List, Dict, Any
from models.event import Event
from models.session import Session
from models.bot_visit import BotVisit


async def generate_insights(db: AsyncSession, site_id, days: int = 7) -> List[Dict[str, Any]]:
    insights = []
    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    prior_start = current_start - timedelta(days=days)

    # --- Traffic spike / drop by country ---
    current_geo = await db.execute(
        select(Event.country, func.count(func.distinct(Event.ip_hash)).label("v"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False, Event.country.isnot(None))
        .group_by(Event.country)
    )
    prior_geo = await db.execute(
        select(Event.country, func.count(func.distinct(Event.ip_hash)).label("v"))
        .where(Event.site_id == site_id, Event.timestamp >= prior_start, Event.timestamp < current_start, Event.is_bot == False, Event.country.isnot(None))
        .group_by(Event.country)
    )
    cur_geo = {r.country: r.v for r in current_geo}
    pri_geo = {r.country: r.v for r in prior_geo}

    for country, cur_v in cur_geo.items():
        pri_v = pri_geo.get(country, 0)
        if pri_v > 0 and cur_v > 5:
            pct = ((cur_v - pri_v) / pri_v) * 100
            if pct >= 50:
                insights.append({
                    "type": "geo_spike",
                    "severity": "high" if pct >= 200 else "medium",
                    "text": f"Traffic from {country} increased {round(pct)}% compared to the previous {days} days.",
                    "data": {"country": country, "current": cur_v, "prior": pri_v, "change_pct": round(pct)},
                })
            elif pct <= -50:
                insights.append({
                    "type": "geo_drop",
                    "severity": "medium",
                    "text": f"Traffic from {country} dropped {abs(round(pct))}% compared to the previous {days} days.",
                    "data": {"country": country, "current": cur_v, "prior": pri_v, "change_pct": round(pct)},
                })

    # --- High bounce pages ---
    page_sessions = await db.execute(
        select(Session.entry_page, func.count(Session.id).label("total"), func.sum(func.cast(Session.is_bounce, Integer)).label("bounces"))
        .where(Session.site_id == site_id, Session.started_at >= current_start)
        .group_by(Session.entry_page)
        .having(func.count(Session.id) >= 10)
    )
    for row in page_sessions:
        rate = (row.bounces / row.total) * 100 if row.total else 0
        if rate >= 80:
            insights.append({
                "type": "high_bounce_page",
                "severity": "medium",
                "text": f"'{_short_url(row.entry_page)}' has a {round(rate)}% bounce rate — visitors are leaving without exploring further.",
                "data": {"page": row.entry_page, "bounce_rate": round(rate), "sessions": row.total},
            })

    # --- Traffic source intelligence ---
    cur_sources = await db.execute(
        select(Session.referrer_domain, func.count(Session.id).label("s"))
        .where(Session.site_id == site_id, Session.started_at >= current_start, Session.referrer_domain.isnot(None))
        .group_by(Session.referrer_domain).order_by(desc("s")).limit(5)
    )
    pri_sources = await db.execute(
        select(Session.referrer_domain, func.count(Session.id).label("s"))
        .where(Session.site_id == site_id, Session.started_at >= prior_start, Session.started_at < current_start, Session.referrer_domain.isnot(None))
        .group_by(Session.referrer_domain)
    )
    pri_src = {r.referrer_domain: r.s for r in pri_sources}
    for row in cur_sources:
        prior_s = pri_src.get(row.referrer_domain, 0)
        if prior_s == 0 and row.s >= 5:
            insights.append({
                "type": "new_source",
                "severity": "info",
                "text": f"New traffic source detected: {row.referrer_domain} sent {row.s} sessions this period with no prior history.",
                "data": {"source": row.referrer_domain, "sessions": row.s},
            })

    # --- Dead pages (views but no return) ---
    dead = await db.execute(
        select(Event.page_url, func.count(Event.id).label("views"), func.avg(Event.duration_seconds).label("avg_dur"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False)
        .group_by(Event.page_url)
        .having(func.count(Event.id) >= 20, func.avg(Event.duration_seconds) < 10)
        .order_by(desc("views"))
        .limit(3)
    )
    for row in dead:
        insights.append({
            "type": "dead_page",
            "severity": "low",
            "text": f"'{_short_url(row.page_url)}' gets {row.views} views but visitors spend less than 10 seconds on average — possible content mismatch or slow load.",
            "data": {"page": row.page_url, "views": row.views, "avg_duration": round(row.avg_dur or 0, 1)},
        })

    # --- Overall traffic trend ---
    cur_total = await db.execute(
        select(func.count(Event.id)).where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False)
    )
    pri_total = await db.execute(
        select(func.count(Event.id)).where(Event.site_id == site_id, Event.timestamp >= prior_start, Event.timestamp < current_start, Event.is_bot == False)
    )
    c = cur_total.scalar() or 0
    p = pri_total.scalar() or 0
    if p > 0 and c > 0:
        pct = ((c - p) / p) * 100
        if abs(pct) >= 20:
            direction = "up" if pct > 0 else "down"
            insights.append({
                "type": "overall_trend",
                "severity": "info",
                "text": f"Overall traffic is {direction} {abs(round(pct))}% compared to the previous {days}-day period ({p:,} → {c:,} page views).",
                "data": {"current": c, "prior": p, "change_pct": round(pct)},
            })

    # --- Page velocity spikes ---
    cur_page_v = await db.execute(
        select(Event.page_url, func.count(Event.id).label("v"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False, Event.is_404 == False)
        .group_by(Event.page_url)
        .having(func.count(Event.id) >= 15)
        .order_by(desc(func.count(Event.id)))
        .limit(30)
    )
    pri_page_v = await db.execute(
        select(Event.page_url, func.count(Event.id).label("v"))
        .where(Event.site_id == site_id, Event.timestamp >= prior_start, Event.timestamp < current_start, Event.is_bot == False, Event.is_404 == False)
        .group_by(Event.page_url)
    )
    cur_pv = {r.page_url: r.v for r in cur_page_v}
    pri_pv = {r.page_url: r.v for r in pri_page_v}
    for url, cur_v in cur_pv.items():
        pri_v = pri_pv.get(url, 0)
        if pri_v > 0:
            pct = ((cur_v - pri_v) / pri_v) * 100
            if pct >= 150 and cur_v >= 20:
                insights.append({
                    "type": "page_spike",
                    "severity": "high" if pct >= 400 else "medium",
                    "text": f"'{_short_url(url)}' surged {round(pct)}% — from {pri_v:,} to {cur_v:,} views. Something drove significant attention to this page.",
                    "data": {"page": url, "current": cur_v, "prior": pri_v, "change_pct": round(pct)},
                })
        elif pri_v == 0 and cur_v >= 50:
            insights.append({
                "type": "page_breakout",
                "severity": "info",
                "text": f"New breakout: '{_short_url(url)}' attracted {cur_v:,} views with no prior traffic history.",
                "data": {"page": url, "current": cur_v},
            })

    # --- Scroll depth regression ---
    cur_scroll = await db.execute(
        select(Event.page_url, func.avg(Event.scroll_depth).label("avg_scroll"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False, Event.scroll_depth.isnot(None))
        .group_by(Event.page_url)
        .having(func.count(Event.id) >= 10)
    )
    pri_scroll = await db.execute(
        select(Event.page_url, func.avg(Event.scroll_depth).label("avg_scroll"))
        .where(Event.site_id == site_id, Event.timestamp >= prior_start, Event.timestamp < current_start, Event.is_bot == False, Event.scroll_depth.isnot(None))
        .group_by(Event.page_url)
        .having(func.count(Event.id) >= 10)
    )
    cur_sc = {r.page_url: float(r.avg_scroll) for r in cur_scroll}
    pri_sc = {r.page_url: float(r.avg_scroll) for r in pri_scroll}
    for url, cur_s in cur_sc.items():
        pri_s = pri_sc.get(url)
        if pri_s and (pri_s - cur_s) >= 20:
            insights.append({
                "type": "scroll_regression",
                "severity": "medium",
                "text": f"Scroll depth on '{_short_url(url)}' dropped from {round(pri_s)}% to {round(cur_s)}% — visitors are reading less of this page than before.",
                "data": {"page": url, "current_scroll": round(cur_s), "prior_scroll": round(pri_s)},
            })

    # --- Performance regression (LCP) ---
    cur_lcp = await db.execute(
        select(Event.page_url, func.avg(Event.lcp).label("avg_lcp"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False, Event.lcp.isnot(None))
        .group_by(Event.page_url)
        .having(func.count(Event.id) >= 10)
    )
    pri_lcp = await db.execute(
        select(Event.page_url, func.avg(Event.lcp).label("avg_lcp"))
        .where(Event.site_id == site_id, Event.timestamp >= prior_start, Event.timestamp < current_start, Event.is_bot == False, Event.lcp.isnot(None))
        .group_by(Event.page_url)
        .having(func.count(Event.id) >= 10)
    )
    cur_l = {r.page_url: float(r.avg_lcp) for r in cur_lcp}
    pri_l = {r.page_url: float(r.avg_lcp) for r in pri_lcp}
    for url, cur_v in cur_l.items():
        pri_v = pri_l.get(url)
        if pri_v and (cur_v - pri_v) >= 500:
            insights.append({
                "type": "lcp_regression",
                "severity": "high" if cur_v > 4000 else "medium",
                "text": f"Page load time (LCP) on '{_short_url(url)}' worsened from {round(pri_v):,}ms to {round(cur_v):,}ms — visitors may be experiencing a noticeably slow load.",
                "data": {"page": url, "current_lcp_ms": round(cur_v), "prior_lcp_ms": round(pri_v)},
            })

    # --- Returning visitor decline ---
    cur_ret_r = await db.execute(
        select(func.count(Session.id).label("total"), func.sum(func.cast(Session.is_returning, Integer)).label("returning_count"))
        .where(Session.site_id == site_id, Session.started_at >= current_start)
    )
    pri_ret_r = await db.execute(
        select(func.count(Session.id).label("total"), func.sum(func.cast(Session.is_returning, Integer)).label("returning_count"))
        .where(Session.site_id == site_id, Session.started_at >= prior_start, Session.started_at < current_start)
    )
    cur_ret = cur_ret_r.one_or_none()
    pri_ret = pri_ret_r.one_or_none()
    if cur_ret and pri_ret and cur_ret.total > 20 and pri_ret.total > 20:
        cur_rate = (cur_ret.returning_count or 0) / cur_ret.total * 100
        pri_rate = (pri_ret.returning_count or 0) / pri_ret.total * 100
        if (pri_rate - cur_rate) >= 15:
            insights.append({
                "type": "returning_visitor_drop",
                "severity": "medium",
                "text": f"Returning visitor rate fell from {round(pri_rate)}% to {round(cur_rate)}% — fewer people are coming back. This often signals a change in content frequency or notification strategy.",
                "data": {"current_rate": round(cur_rate), "prior_rate": round(pri_rate)},
            })

    # --- AI crawler surge ---
    cur_ai_r = await db.execute(
        select(func.count(BotVisit.id))
        .where(BotVisit.site_id == site_id, BotVisit.timestamp >= current_start, BotVisit.bot_category == "ai_crawler")
    )
    pri_ai_r = await db.execute(
        select(func.count(BotVisit.id))
        .where(BotVisit.site_id == site_id, BotVisit.timestamp >= prior_start, BotVisit.timestamp < current_start, BotVisit.bot_category == "ai_crawler")
    )
    cur_ai = cur_ai_r.scalar() or 0
    pri_ai = pri_ai_r.scalar() or 0
    if pri_ai > 0 and cur_ai > 0:
        pct = ((cur_ai - pri_ai) / pri_ai) * 100
        if pct >= 100:
            insights.append({
                "type": "ai_crawler_surge",
                "severity": "info",
                "text": f"AI crawler activity increased {round(pct)}% this period ({cur_ai:,} visits vs {pri_ai:,} prior). Your content is attracting more attention from AI indexing systems.",
                "data": {"current": cur_ai, "prior": pri_ai, "change_pct": round(pct)},
            })

    # Sort: high severity first
    order = {"high": 0, "medium": 1, "info": 2, "low": 3}
    insights.sort(key=lambda x: order.get(x["severity"], 9))
    return insights


def _short_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return p.path or url
    except Exception:
        return url


async def generate_summary(db: AsyncSession, site_id, days: int = 7) -> dict:
    """
    Synthesizes a natural language performance summary from raw data.
    No external LLM calls — built from conditional sentence templates applied to real metrics.
    """
    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    prior_start = current_start - timedelta(days=days)
    period_label = "week" if days == 7 else f"{days}-day period"

    # Views + visitors
    cur_v_r = await db.execute(
        select(func.count(Event.id).label("views"), func.count(func.distinct(Event.ip_hash)).label("visitors"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False, Event.is_404 == False)
    )
    cur_v = cur_v_r.one()
    pri_views_r = await db.execute(
        select(func.count(Event.id))
        .where(Event.site_id == site_id, Event.timestamp >= prior_start, Event.timestamp < current_start, Event.is_bot == False, Event.is_404 == False)
    )
    pri_views = pri_views_r.scalar() or 0

    # Sessions + bounce
    sess_r = await db.execute(
        select(func.count(Session.id).label("total"), func.sum(func.cast(Session.is_bounce, Integer)).label("bounces"))
        .where(Session.site_id == site_id, Session.started_at >= current_start)
    )
    sess_row = sess_r.one()

    # Top referrer source
    src_r = await db.execute(
        select(Session.referrer_domain, func.count(Session.id).label("s"))
        .where(Session.site_id == site_id, Session.started_at >= current_start, Session.referrer_domain.isnot(None))
        .group_by(Session.referrer_domain)
        .order_by(desc("s"))
        .limit(1)
    )
    top_src = src_r.one_or_none()

    # Top page + avg duration
    page_r = await db.execute(
        select(Event.page_url, func.count(Event.id).label("v"), func.avg(Event.duration_seconds).label("dur"))
        .where(Event.site_id == site_id, Event.timestamp >= current_start, Event.is_bot == False, Event.is_404 == False)
        .group_by(Event.page_url)
        .order_by(desc("v"))
        .limit(1)
    )
    top_page = page_r.one_or_none()

    # AI crawlers
    ai_bots = []
    avi = 0.0
    # Label is "total_count" not "t" — bare "t" collides with Row's internal _t
    # accessor in SQLAlchemy 2.0.19+ and returns the whole Row tuple.
    ai_r = await db.execute(
        select(BotVisit.bot_name, func.count(BotVisit.id).label("total_count"), func.count(func.distinct(BotVisit.page_path)).label("up"))
        .where(BotVisit.site_id == site_id, BotVisit.timestamp >= current_start, BotVisit.bot_category == "ai_crawler")
        .group_by(BotVisit.bot_name)
        .order_by(desc("total_count"))
    )
    for r in ai_r.all():
        ai_bots.append({"name": r.bot_name, "total": int(r.total_count or 0), "unique_pages": int(r.up or 0)})
    if ai_bots:
        from services.bot import calc_avi
        avi = calc_avi(ai_bots)

    # --- Derive values ---
    views    = cur_v.views    or 0
    visitors = cur_v.visitors or 0
    sessions = sess_row.total  or 0
    bounces  = sess_row.bounces or 0
    bounce_rate = round((bounces / sessions * 100), 1) if sessions else 0
    view_delta_pct = round(((views - pri_views) / pri_views) * 100) if pri_views > 0 else None

    # --- Build narrative sentences ---
    sentences = []

    # S1: Traffic headline
    if view_delta_pct is not None and views > 0:
        if view_delta_pct >= 5:
            sentences.append(f"Your site received {views:,} page views this {period_label} — up {view_delta_pct}% from the prior period.")
        elif view_delta_pct <= -5:
            sentences.append(f"Your site received {views:,} page views this {period_label} — down {abs(view_delta_pct)}% from the prior period.")
        else:
            sentences.append(f"Your site received {views:,} page views this {period_label}, roughly in line with the prior period.")
    elif views > 0:
        sentences.append(f"Your site received {views:,} page views this {period_label}.")
    else:
        sentences.append(f"No page view data recorded for this {period_label} yet.")

    # S2: Visitor engagement quality
    if visitors > 0 and sessions > 0:
        if bounce_rate < 35:
            sentences.append(f"Engagement is strong — only {bounce_rate}% of sessions bounced, meaning most visitors explored beyond their landing page.")
        elif bounce_rate > 70:
            sentences.append(f"Bounce rate is elevated at {bounce_rate}% — most visitors are leaving without exploring further, which is worth investigating.")
        else:
            sentences.append(f"That brought {visitors:,} unique visitors across {sessions:,} sessions with a {bounce_rate}% bounce rate.")

    # S3: Top traffic source
    if top_src and top_src.s >= 3 and sessions > 0:
        src_pct = round(top_src.s / sessions * 100)
        if src_pct >= 20:
            sentences.append(f"Your strongest traffic channel was {top_src.referrer_domain}, contributing {src_pct}% of sessions.")

    # S4: Top page
    if top_page and top_page.v >= 5:
        dur_note = ""
        if top_page.dur and top_page.dur >= 60:
            mins = int(top_page.dur // 60)
            secs = int(top_page.dur % 60)
            dur_str = f"{mins}m {secs}s" if secs else f"{mins}m"
            dur_note = f", with visitors averaging {dur_str} on the page"
        sentences.append(f"Your most-visited page was '{_short_url(top_page.page_url)}' with {top_page.v:,} views{dur_note}.")

    # S5: AI indexing presence
    if ai_bots:
        names = [b["name"] for b in ai_bots[:3]]
        if len(names) == 1:
            bots_str = names[0]
        elif len(names) == 2:
            bots_str = f"{names[0]} and {names[1]}"
        else:
            bots_str = f"{names[0]}, {names[1]}, and {names[2]}"
        extra = f" (and {len(ai_bots) - 3} more)" if len(ai_bots) > 3 else ""
        system_word = "system" if len(ai_bots) == 1 else "systems"
        sentences.append(f"{len(ai_bots)} AI {system_word} — {bots_str}{extra} — indexed your content this period, giving you an AI Visibility Index of {avi}/100.")

    # --- Headline ---
    if view_delta_pct is not None and abs(view_delta_pct) >= 5:
        direction = "up" if view_delta_pct > 0 else "down"
        headline = f"Traffic {direction} {abs(view_delta_pct)}% — {views:,} page views this {period_label}"
    elif views > 0:
        headline = f"{views:,} page views this {period_label}"
    else:
        headline = f"No data yet for this {period_label}"

    return {
        "headline": headline,
        "narrative": " ".join(sentences),
        "stats": {
            "views": views,
            "visitors": visitors,
            "sessions": sessions,
            "bounce_rate": bounce_rate,
            "view_delta_pct": view_delta_pct,
            "ai_visibility_index": avi,
            "ai_crawler_systems": len(ai_bots),
        },
        "period_days": days,
        "generated_at": now.isoformat(),
    }
