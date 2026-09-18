from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, select, func, distinct
from datetime import datetime, timedelta
from typing import Optional
import uuid as _uuid

from database import get_db
from models.bot_visit import BotVisit
from models.event import Event
from models.site import Site
from routers.auth import get_current_user
from services.bot import calc_avi, calc_shadow_reach

router = APIRouter()

CATEGORY_LABELS = {
    "ai_crawler":     "AI Crawler",
    "seo_crawler":    "SEO Crawler",
    "seo_audit":      "SEO Audit Tool",
    "social_crawler": "Social Preview",
    "generic_bot":    "Generic Bot",
    # Traffic whose self-description is internally contradictory (see
    # services/deception.py). Not a named crawler — these carry no bot name at
    # all, which is precisely why the name registry cannot see them.
    "deceptive":      "Disguised Bot",
}


async def _get_site(db: AsyncSession, site_id: Optional[str] = None) -> Site | None:
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


async def _crawler_rows(db: AsyncSession, site_id, since: datetime) -> list[dict]:
    """Per-bot aggregates: total visits, unique pages, last seen."""
    rows = await db.execute(
        select(
            BotVisit.bot_name,
            BotVisit.bot_category,
            func.count(BotVisit.id).label("total"),
            func.count(distinct(BotVisit.page_path)).label("unique_pages"),
            func.count(distinct(case(
                (BotVisit.verification_state == "verified", BotVisit.page_path),
                else_=None,
            ))).label("verified_unique_pages"),
            func.max(BotVisit.timestamp).label("last_seen"),
            func.sum(case((BotVisit.verification_state == "verified", 1), else_=0)).label("verified"),
            func.sum(case((BotVisit.verification_state == "unverified", 1), else_=0)).label("unverified"),
            func.sum(case((BotVisit.verification_state == "forged", 1), else_=0)).label("forged"),
        )
        .where(BotVisit.site_id == site_id, BotVisit.timestamp >= since)
        .group_by(BotVisit.bot_name, BotVisit.bot_category)
        .order_by(func.count(BotVisit.id).desc())
    )
    return [
        {
            "name":         r.bot_name,
            "category":     r.bot_category,
            "category_label": CATEGORY_LABELS.get(r.bot_category, r.bot_category),
            "total":        r.total,
            "unique_pages": r.unique_pages,
            "verified_unique_pages": r.verified_unique_pages,
            "last_seen":    r.last_seen.isoformat() if r.last_seen else None,
            "verification": {
                "verified": r.verified or 0,
                "unverified": r.unverified or 0,
                "forged": r.forged or 0,
            },
        }
        for r in rows.all()
    ]


@router.get("/overview")
async def ai_crawler_overview(
    days: int = Query(30, ge=1, le=365),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site = await _get_site(db, site_id)
    if not site:
        return {}

    since = datetime.utcnow() - timedelta(days=days)
    crawlers = await _crawler_rows(db, site.id, since)
    ai_crawlers = [c for c in crawlers if c["category"] == "ai_crawler"]

    # Total bot visits
    total_bot_claims = sum(c["total"] for c in crawlers)
    total_ai_claims = sum(c["total"] for c in ai_crawlers)
    total_bot_visits = sum(c["verification"]["verified"] for c in crawlers)
    total_ai_visits = sum(c["verification"]["verified"] for c in ai_crawlers)
    verified_ai_crawlers = [
        {
            **crawler,
            "total": crawler["verification"]["verified"],
            "unique_pages": crawler["verified_unique_pages"],
        }
        for crawler in ai_crawlers
        if crawler["verification"]["verified"] > 0
    ]
    verified_claims = sum(c["verification"]["verified"] for c in crawlers)
    unverified_claims = sum(c["verification"]["unverified"] for c in crawlers)
    forged_claims = sum(c["verification"]["forged"] for c in crawlers)

    # Unique pages touched by any bot
    result = await db.execute(
        select(func.count(distinct(BotVisit.page_path)))
        .where(
            BotVisit.site_id == site.id,
            BotVisit.timestamp >= since,
            BotVisit.verification_state == "verified",
        )
    )
    unique_pages_crawled = result.scalar() or 0

    # Human visits for ratio
    result = await db.execute(
        select(func.count(Event.id))
        .where(Event.site_id == site.id, Event.timestamp >= since, Event.is_bot == False)
    )
    human_visits = result.scalar() or 0

    total_all = human_visits + total_bot_visits
    ai_human_ratio = round(total_ai_visits / total_all * 100, 1) if total_all > 0 else 0

    return {
        "total_bot_visits":     total_bot_visits,
        "total_ai_visits":      total_ai_visits,
        "total_bot_claims":     total_bot_claims,
        "total_ai_claims":      total_ai_claims,
        "unique_pages_crawled": unique_pages_crawled,
        "human_visits":         human_visits,
        "ai_human_ratio":       ai_human_ratio,
        "ai_visibility_index":  calc_avi(verified_ai_crawlers),
        "shadow_reach_index":   calc_shadow_reach(verified_ai_crawlers),
        "crawler_verification": {
            "verified": verified_claims,
            "unverified": unverified_claims,
            "forged": forged_claims,
        },
        "days":                 days,
    }


@router.get("/crawlers")
async def crawler_breakdown(
    days: int = Query(30, ge=1, le=365),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site = await _get_site(db, site_id)
    if not site:
        return []
    since = datetime.utcnow() - timedelta(days=days)
    return await _crawler_rows(db, site.id, since)


@router.get("/pages")
async def top_crawled_pages(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(25, ge=1, le=100),
    category: str = Query("ai_crawler"),
    verification: str = Query("verified", pattern="^(verified|unverified|forged|all)$"),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Top pages crawled by AI systems, with Content Magnetism Score.
    Magnetism = crawls per day — shows pages AI systems keep returning to.
    """
    site = await _get_site(db, site_id)
    if not site:
        return []

    since = datetime.utcnow() - timedelta(days=days)
    where = [BotVisit.site_id == site.id, BotVisit.timestamp >= since]
    if category != "all":
        where.append(BotVisit.bot_category == category)
    if verification != "all":
        where.append(BotVisit.verification_state == verification)

    rows = await db.execute(
        select(
            BotVisit.page_path,
            func.count(BotVisit.id).label("total_crawls"),
            func.count(distinct(BotVisit.bot_name)).label("unique_bots"),
            func.min(BotVisit.timestamp).label("first_crawled"),
            func.max(BotVisit.timestamp).label("last_crawled"),
        )
        .where(*where)
        .group_by(BotVisit.page_path)
        .order_by(func.count(BotVisit.id).desc())
        .limit(limit)
    )

    results = []
    for r in rows.all():
        days_active = max(1, (datetime.utcnow() - r.first_crawled.replace(tzinfo=None)).days)
        magnetism = min(100, round(r.total_crawls / days_active * 10, 1))
        results.append({
            "page_path":    r.page_path,
            "total_crawls": r.total_crawls,
            "unique_bots":  r.unique_bots,
            "first_crawled": r.first_crawled.isoformat() if r.first_crawled else None,
            "last_crawled":  r.last_crawled.isoformat()  if r.last_crawled  else None,
            "magnetism_score": magnetism,
        })
    return results


@router.get("/ratio-by-page")
async def ai_human_ratio_by_page(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Per-page AI-to-Human ratio. Pages where AI reads > human reads are
    'shadow content' — valuable to AI systems, possibly under-served to humans.
    """
    site = await _get_site(db, site_id)
    if not site:
        return []

    since = datetime.utcnow() - timedelta(days=days)

    bot_rows = await db.execute(
        select(BotVisit.page_path, func.count(BotVisit.id).label("bot_visits"))
        .where(
            BotVisit.site_id == site.id,
            BotVisit.timestamp >= since,
            BotVisit.bot_category == "ai_crawler",
        )
        .group_by(BotVisit.page_path)
    )
    bot_map = {r.page_path: r.bot_visits for r in bot_rows.all()}

    human_rows = await db.execute(
        select(Event.page_url, func.count(Event.id).label("human_visits"))
        .where(Event.site_id == site.id, Event.timestamp >= since, Event.is_bot == False)
        .group_by(Event.page_url)
    )
    human_map = {r.page_url: r.human_visits for r in human_rows.all()}

    all_pages = set(bot_map) | set(human_map)
    results = []
    for page in all_pages:
        bots   = bot_map.get(page, 0)
        humans = human_map.get(page, 0)
        total  = bots + humans
        if total == 0:
            continue
        results.append({
            "page":         page,
            "ai_visits":    bots,
            "human_visits": humans,
            "ai_ratio":     round(bots / total * 100, 1),
            "shadow":       bots > humans,
        })

    results.sort(key=lambda x: x["ai_visits"], reverse=True)
    return results[:limit]


@router.get("/site/profile")
async def site_profile(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Lightweight endpoint for the desktop multi-site panel."""
    site = await _get_site(db, site_id)
    if not site:
        return {}

    since_30 = datetime.utcnow() - timedelta(days=30)

    pv_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.site_id == site.id, Event.timestamp >= since_30, Event.is_bot == False)
    )
    bot_result = await db.execute(
        select(func.count(BotVisit.id))
        .where(BotVisit.site_id == site.id, BotVisit.timestamp >= since_30)
    )
    ai_rows = await db.execute(
        select(BotVisit.bot_name, func.count(BotVisit.id).label("t"), func.count(distinct(BotVisit.page_path)).label("up"))
        .where(BotVisit.site_id == site.id, BotVisit.timestamp >= since_30, BotVisit.bot_category == "ai_crawler")
        .group_by(BotVisit.bot_name)
    )
    ai_bots = [{"name": r.bot_name, "total": r.t, "unique_pages": r.up} for r in ai_rows.all()]

    return {
        "name":    site.name,
        "domain":  site.domain,
        "version": "0.1.0",
        "stats_30d": {
            "page_views":          pv_result.scalar() or 0,
            "bot_visits":          bot_result.scalar() or 0,
            "ai_visibility_index": calc_avi(ai_bots),
            "ai_crawler_count":    len(ai_bots),
        },
    }
