from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
import uuid as _uuid

from database import get_db
from models.site import Site
from models.event import Event
from models.bot_visit import BotVisit
from routers.auth import get_current_user, require_admin
from services.app_config import build_snippet_for

router = APIRouter()


class SiteCreate(BaseModel):
    domain: str
    name: Optional[str] = None
    timezone: str = "UTC"


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    active: Optional[bool] = None


@router.get("")
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Return all sites with a quick stats summary (last 30 days)."""
    result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    sites = result.scalars().all()

    since = datetime.utcnow() - timedelta(days=30)
    out = []
    for s in sites:
        views_r = await db.execute(
            select(func.count(Event.id))
            .where(Event.site_id == s.id, Event.timestamp >= since, Event.is_bot == False)
        )
        visitors_r = await db.execute(
            select(func.count(func.distinct(Event.ip_hash)))
            .where(Event.site_id == s.id, Event.timestamp >= since, Event.is_bot == False)
        )
        bots_r = await db.execute(
            select(func.count(BotVisit.id))
            .where(BotVisit.site_id == s.id, BotVisit.timestamp >= since)
        )
        ai_r = await db.execute(
            select(func.count(func.distinct(BotVisit.bot_name)))
            .where(BotVisit.site_id == s.id, BotVisit.timestamp >= since, BotVisit.bot_category == "ai_crawler")
        )
        out.append({
            "id": str(s.id),
            "domain": s.domain,
            "name": s.name,
            "timezone": s.timezone,
            "tracker_key": s.tracker_key,
            "active": s.active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "stats_30d": {
                "page_views": views_r.scalar() or 0,
                "visitors": visitors_r.scalar() or 0,
                "bot_visits": bots_r.scalar() or 0,
                "ai_crawlers": ai_r.scalar() or 0,
            },
        })
    return out


@router.post("")
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    domain = payload.domain.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
    if not domain or "." not in domain:
        raise HTTPException(status_code=400, detail="Please provide a valid domain (e.g. mysite.com)")

    existing = await db.execute(select(Site).where(Site.domain == domain))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"A site with domain {domain} already exists")

    site = Site(
        domain=domain,
        name=payload.name or domain,
        timezone=payload.timezone,
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return {
        "id": str(site.id),
        "domain": site.domain,
        "name": site.name,
        "tracker_key": site.tracker_key,
        "tracker_snippet": await build_snippet_for(db, site.tracker_key),
    }


@router.patch("/{site_id}")
async def update_site(
    site_id: str,
    payload: SiteUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    try:
        uid = _uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site id")
    result = await db.execute(select(Site).where(Site.id == uid))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    if payload.name is not None:
        site.name = payload.name
    if payload.timezone is not None:
        site.timezone = payload.timezone
    if payload.active is not None:
        site.active = payload.active
    await db.commit()
    return {"ok": True}


@router.delete("/{site_id}")
async def delete_site(
    site_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    try:
        uid = _uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site id")
    result = await db.execute(select(Site).where(Site.id == uid))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await db.delete(site)
    await db.commit()
    return {"ok": True}


@router.get("/{site_id}/tracker")
async def get_tracker_snippet(
    site_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    try:
        uid = _uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site id")
    result = await db.execute(select(Site).where(Site.id == uid))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return {
        "tracker_key": site.tracker_key,
        "snippet": await build_snippet_for(db, site.tracker_key),
    }
