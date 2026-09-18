from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import json
import uuid as _uuid

from pydantic import BaseModel
from database import get_db
from models.site import Site
from models.event import Event
from models.session import Session
from models.bot_visit import BotVisit
from models.ai_usage import AIUsageLog
from models.geo_probe import GeoProbeQuery, GeoProbeResult

# Optional layer-2 feature (see main.py) — this core router never depends on
# it directly, so the chat still boots when it's removed.
try:
    from models.walk_detection import WalkDetectionRun
except ImportError:
    WalkDetectionRun = None
from routers.auth import get_current_user
from services.insights import generate_insights, generate_summary
from services.paths import get_session_paths
from services.ai_cost import MODEL_CATALOG, estimate_cost
from services.ai_providers import get_provider, call_model, stream_model
from config import get_settings

router = APIRouter()


async def _resolve_site(db: AsyncSession, site_id: Optional[str]) -> Optional[Site]:
    if site_id:
        try:
            uid = _uuid.UUID(site_id)
            result = await db.execute(select(Site).where(Site.id == uid))
            site = result.scalar_one_or_none()
            if site:
                return site
        except ValueError:
            pass
    result = await db.execute(select(Site).limit(1))
    return result.scalar_one_or_none()


@router.get("/summary")
async def summary(
    days: int = Query(7, ge=1, le=90),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    site = await _resolve_site(db, site_id)
    if not site:
        return {"headline": "No site configured", "narrative": "", "stats": {}, "period_days": days}
    return await generate_summary(db, site.id, days=days)


@router.get("/insights")
async def insights(
    days: int = Query(7, ge=1, le=90),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    site = await _resolve_site(db, site_id)
    if not site:
        return []
    return await generate_insights(db, site.id, days=days)


@router.get("/paths")
async def session_paths(
    days: int = Query(30, ge=1, le=90),
    min_weight: int = Query(1, ge=1, le=20),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site = await _resolve_site(db, site_id)
    if not site:
        return {"nodes": [], "links": []}
    return await get_session_paths(db, site.id, days=days, min_weight=min_weight)


@router.get("/active-stats")
async def active_stats(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Snapshot of live activity — designed to be polled every 5 seconds."""
    site = await _resolve_site(db, site_id)
    if not site:
        return {}

    now = datetime.utcnow()
    five_min_ago = now - timedelta(minutes=5)
    one_min_ago  = now - timedelta(seconds=60)

    # Active sessions (last seen within 5 minutes)
    active_r = await db.execute(
        select(func.count(Session.id))
        .where(Session.site_id == site.id, Session.last_seen_at >= five_min_ago)
    )

    # Pageviews last 60 seconds
    pv_60s_r = await db.execute(
        select(func.count(Event.id))
        .where(Event.site_id == site.id, Event.timestamp >= one_min_ago, Event.is_bot == False)
    )

    # Pageviews last 5 minutes
    pv_5m_r = await db.execute(
        select(func.count(Event.id))
        .where(Event.site_id == site.id, Event.timestamp >= five_min_ago, Event.is_bot == False)
    )

    # Top pages active in last 5 minutes
    top_pages_r = await db.execute(
        select(Event.page_url, func.count(Event.id).label("hits"))
        .where(Event.site_id == site.id, Event.timestamp >= five_min_ago, Event.is_bot == False)
        .group_by(Event.page_url)
        .order_by(desc("hits"))
        .limit(8)
    )

    # Top countries active in last 5 minutes
    top_countries_r = await db.execute(
        select(Event.country, func.count(func.distinct(Event.ip_hash)).label("visitors"))
        .where(Event.site_id == site.id, Event.timestamp >= five_min_ago, Event.is_bot == False, Event.country.isnot(None))
        .group_by(Event.country)
        .order_by(desc("visitors"))
        .limit(6)
    )

    # Device breakdown last 5 minutes
    devices_r = await db.execute(
        select(Event.device_type, func.count(Event.id).label("hits"))
        .where(Event.site_id == site.id, Event.timestamp >= five_min_ago, Event.is_bot == False, Event.device_type.isnot(None))
        .group_by(Event.device_type)
    )

    def _path(url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).path or url
        except Exception:
            return url

    top_pages = [{"page": _path(r.page_url), "hits": r.hits} for r in top_pages_r.all()]
    devices   = {r.device_type: r.hits for r in devices_r.all()}
    total_dev = sum(devices.values()) or 1

    return {
        "active_sessions":    active_r.scalar()  or 0,
        "pageviews_last_60s": pv_60s_r.scalar()  or 0,
        "pageviews_last_5m":  pv_5m_r.scalar()   or 0,
        "top_pages":    top_pages,
        "top_countries": [{"country": r.country, "visitors": r.visitors} for r in top_countries_r.all()],
        "devices": {k: round(v / total_dev * 100) for k, v in devices.items()},
        "as_of": now.isoformat(),
    }


@router.get("/realtime")
async def realtime_stream(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Server-Sent Events stream of live visitor activity."""
    site = await _resolve_site(db, site_id)

    async def event_stream():
        from datetime import datetime, timedelta
        last_id = None
        while True:
            since = datetime.utcnow() - timedelta(seconds=30)
            conds = [Event.timestamp >= since, Event.is_bot == False]
            if site:
                conds.append(Event.site_id == site.id)
            result = await db.execute(
                select(Event.id, Event.page_url, Event.country, Event.device_type, Event.timestamp)
                .where(*conds)
                .order_by(Event.timestamp.desc())
                .limit(20)
            )
            events = result.all()
            if events:
                payload = [
                    {
                        "id": str(e.id),
                        "page": e.page_url,
                        "country": e.country,
                        "device": e.device_type,
                        "time": e.timestamp.isoformat(),
                    }
                    for e in events
                ]
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                yield "data: []\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class AskRequest(BaseModel):
    question: str
    days: int = 7
    site_id: Optional[str] = None


def _path(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).path or url
    except Exception:
        return url


async def _build_analytics_context(db: AsyncSession, site: Site, days: int) -> str:
    from services.insights import generate_summary, generate_insights

    summary = await generate_summary(db, site.id, days=days)
    insights = await generate_insights(db, site.id, days=days)

    now = datetime.utcnow()
    start = now - timedelta(days=days)

    pages_r = await db.execute(
        select(Event.page_url, func.count(Event.id).label("v"), func.avg(Event.duration_seconds).label("dur"))
        .where(Event.site_id == site.id, Event.timestamp >= start, Event.is_bot == False, Event.is_404 == False)
        .group_by(Event.page_url)
        .order_by(desc("v"))
        .limit(10)
    )
    sources_r = await db.execute(
        select(Session.referrer_domain, func.count(Session.id).label("s"))
        .where(Session.site_id == site.id, Session.started_at >= start, Session.referrer_domain.isnot(None))
        .group_by(Session.referrer_domain)
        .order_by(desc("s"))
        .limit(10)
    )
    countries_r = await db.execute(
        select(Event.country, func.count(func.distinct(Event.ip_hash)).label("v"))
        .where(Event.site_id == site.id, Event.timestamp >= start, Event.is_bot == False, Event.country.isnot(None))
        .group_by(Event.country)
        .order_by(desc("v"))
        .limit(8)
    )
    devices_r = await db.execute(
        select(Event.device_type, func.count(Event.id).label("h"))
        .where(Event.site_id == site.id, Event.timestamp >= start, Event.is_bot == False, Event.device_type.isnot(None))
        .group_by(Event.device_type)
    )

    pages = pages_r.all()
    sources = sources_r.all()
    countries = countries_r.all()
    devices = devices_r.all()
    stats = summary["stats"]

    top_pages_str = "\n".join(
        f"  {_path(r.page_url)}: {r.v:,} views" + (f", avg {round(r.dur)}s" if r.dur else "")
        for r in pages
    ) or "  (none)"
    top_sources_str = "\n".join(
        f"  {r.referrer_domain}: {r.s:,} sessions" for r in sources
    ) or "  (mostly direct traffic)"
    top_countries_str = "\n".join(
        f"  {r.country}: {r.v:,} visitors" for r in countries
    ) or "  (none)"
    total_dev = sum(r.h for r in devices) or 1
    devices_str = "\n".join(
        f"  {r.device_type}: {round(r.h / total_dev * 100)}%"
        for r in sorted(devices, key=lambda x: x.h, reverse=True)
    ) or "  (none)"
    delta_str = f"{stats['view_delta_pct']:+}%" if stats.get("view_delta_pct") is not None else "unknown (first period)"
    insights_str = "\n".join(
        f"  [{ins['severity'].upper()}] {ins['text']}" for ins in insights[:8]
    ) or "  No notable signals detected."

    crawler_rows = await db.execute(
        select(BotVisit.bot_name, BotVisit.verification_state, func.count(BotVisit.id).label("n"))
        .where(BotVisit.site_id == site.id, BotVisit.timestamp >= start)
        .group_by(BotVisit.bot_name, BotVisit.verification_state)
        .order_by(desc("n"))
        .limit(15)
    )
    crawlers_str = "\n".join(
        f"  {r.bot_name} ({r.verification_state}): {r.n:,} hits" for r in crawler_rows
    ) or "  No AI crawlers seen."

    walk_run = None
    if WalkDetectionRun is not None:
        walk_run = (
            await db.execute(
                select(WalkDetectionRun)
                .where(WalkDetectionRun.site_id == site.id)
                .order_by(WalkDetectionRun.window_end.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    walk_str = walk_run.headline if walk_run else "No log windows analyzed yet."

    geo_rows = (
        await db.execute(
            select(GeoProbeResult.mentioned, GeoProbeQuery.query_text)
            .join(GeoProbeQuery, GeoProbeQuery.id == GeoProbeResult.probe_id)
            .where(GeoProbeResult.site_id == site.id)
            .order_by(GeoProbeResult.ran_at.desc())
            .limit(10)
        )
    ).all()
    geo_str = "\n".join(
        f'  "{r.query_text}": {"mentioned" if r.mentioned else "not mentioned"}' for r in geo_rows
    ) or "  No GEO probes run yet."

    return f"""SITE: {site.name} ({site.domain})
PERIOD: Last {days} days

TRAFFIC OVERVIEW:
  Page views: {stats['views']:,}
  Unique visitors: {stats['visitors']:,}
  Sessions: {stats['sessions']:,}
  Bounce rate: {stats['bounce_rate']}%
  Change vs prior period: {delta_str}
  AI Visibility Index: {stats.get('ai_visibility_index', 0)}/100

TOP PAGES (by views):
{top_pages_str}

TOP TRAFFIC SOURCES:
{top_sources_str}

TOP COUNTRIES:
{top_countries_str}

DEVICE BREAKDOWN:
{devices_str}

DETECTED SIGNALS & ANOMALIES:
{insights_str}

AI CRAWLERS (name, verification state, hits this period):
{crawlers_str}

CATALOGUE WALK STATUS:
{walk_str}

AI VISIBILITY (does AI mention you when asked):
{geo_str}"""


_ASK_SYSTEM = """You are an analytics assistant built into Higashi Analytics, a privacy-focused self-hosted web analytics platform. You have real data from the user's website and help them understand what's happening with their traffic.

Be concise and direct. When you see a problem, name it and suggest a specific fix. When you see an opportunity, explain how to act on it. Avoid hedging — give your best interpretation of the data. Use plain prose, not markdown headers or bullet lists. Keep responses under 200 words unless the question genuinely requires more detail."""


@router.post("/ask")
async def ask(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    settings = get_settings()
    model = settings.ai_default_model
    api_keys = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
    }
    provider = get_provider(model)
    if not api_keys.get(provider):
        async def _no_key():
            yield f"No API key configured for {provider}. Add one in Intelligence → AI Enrichment Settings.".encode()
        return StreamingResponse(_no_key(), media_type="text/plain; charset=utf-8")

    site = await _resolve_site(db, body.site_id)
    if not site:
        async def _no_site():
            yield b"No site is configured. Complete setup first."
        return StreamingResponse(_no_site(), media_type="text/plain; charset=utf-8")

    context = await _build_analytics_context(db, site, body.days)
    full_system = f"{_ASK_SYSTEM}\n\nCURRENT ANALYTICS DATA:\n{context}"

    async def stream_response():
        try:
            async for chunk in stream_model(model, full_system, body.question, api_keys):
                yield chunk.encode("utf-8")
        except Exception as e:
            yield f"\n\n[Error: {e}]".encode("utf-8")

    return StreamingResponse(stream_response(), media_type="text/plain; charset=utf-8")


class EnrichRequest(BaseModel):
    insights: list
    site_id: Optional[str] = None
    days: int = 7
    model: Optional[str] = None


_ENRICH_SYSTEM = """You are a web analytics advisor reviewing detected signals. For each signal, give the site owner what they need to make their own informed decision.

For each signal provide:
- "interpretation": One plain sentence explaining what likely caused this or why it matters in context
- "options": 2-3 things the site owner could investigate or try, ordered low to high effort. Start each with "You could". One sentence each. Do not recommend one over the others.

Return ONLY a valid JSON array with no other text:
[{"index": 0, "interpretation": "...", "options": ["You could...", "You could...", "You could..."]}, ...]"""


@router.post("/enrich")
async def enrich_insights(
    body: EnrichRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    settings = get_settings()
    if not body.insights:
        return {"enriched": body.insights, "skipped": True}

    model = body.model or settings.ai_default_model
    if model not in MODEL_CATALOG:
        model = "claude-haiku-4-5-20251001"

    api_keys = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
    }
    provider = get_provider(model)
    if not api_keys.get(provider):
        return {"enriched": body.insights, "skipped": True, "reason": f"no_{provider}_key"}

    # Budget gate
    if settings.ai_monthly_budget_usd > 0:
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spend_r = await db.execute(
            select(func.sum(AIUsageLog.estimated_cost_usd)).where(AIUsageLog.created_at >= month_start)
        )
        current_spend = spend_r.scalar() or 0.0
        if current_spend >= settings.ai_monthly_budget_usd:
            return {
                "enriched": body.insights,
                "budget_exceeded": True,
                "monthly_spend_usd": round(current_spend, 4),
                "monthly_budget_usd": settings.ai_monthly_budget_usd,
            }

    site = await _resolve_site(db, body.site_id)

    numbered = "\n".join(
        f"{i}. [{ins['type'].replace('_', ' ').upper()}] {ins['text']}"
        for i, ins in enumerate(body.insights)
    )

    try:
        raw, input_tok, output_tok = await call_model(
            model, _ENRICH_SYSTEM, f"SIGNALS:\n{numbered}", api_keys, max_tokens=1500
        )
        raw = raw.strip()
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json\n"):
                raw = raw[5:]

        enrichments = json.loads(raw)
        enriched = list(body.insights)
        for e in enrichments:
            idx = e.get("index", -1)
            if 0 <= idx < len(enriched):
                enriched[idx] = {
                    **enriched[idx],
                    "interpretation": e.get("interpretation", ""),
                    "options": e.get("options", []),
                }

        cost = estimate_cost(model, input_tok, output_tok)

        db.add(AIUsageLog(
            site_id=site.id if site else None,
            user_id=current_user.id,
            endpoint="enrich",
            model=model,
            input_tokens=input_tok,
            output_tokens=output_tok,
            estimated_cost_usd=cost,
        ))
        await db.commit()

        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spend_r = await db.execute(
            select(func.sum(AIUsageLog.estimated_cost_usd)).where(AIUsageLog.created_at >= month_start)
        )
        monthly_spend = round(spend_r.scalar() or 0.0, 4)

        return {
            "enriched": enriched,
            "model_used": model,
            "model_display_name": MODEL_CATALOG[model]["display_name"],
            "input_tokens": input_tok,
            "output_tokens": output_tok,
            "estimated_cost_usd": cost,
            "monthly_spend_usd": monthly_spend,
            "monthly_budget_usd": settings.ai_monthly_budget_usd,
        }

    except Exception as exc:
        return {"enriched": body.insights, "error": str(exc)}
