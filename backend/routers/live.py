import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.live_reading import LiveReading
from models.site import Site
from routers.auth import get_current_user
from services.live_client import send_report, latest_reading as fetch_latest_reading
from services.live_report import build_report

# Optional layer-2 feature (see main.py) — core services never import it, but
# a router is allowed to reach for it when present.
try:
    from models.walk_detection import WalkDetectionRun
except ImportError:
    WalkDetectionRun = None

router = APIRouter()


async def _latest_walk_run(db: AsyncSession, site_id):
    if WalkDetectionRun is None:
        return None
    return (
        await db.execute(
            select(WalkDetectionRun)
            .where(WalkDetectionRun.site_id == site_id)
            .order_by(WalkDetectionRun.window_end.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


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


def _reading_dict(row: LiveReading) -> dict:
    return {
        "reading_id": row.live_reading_id,
        "headline": row.headline,
        "paragraphs": row.paragraphs or [],
        "verdict": row.verdict,
        "changes": row.changes or [],
        "benchmarks": row.benchmarks or [],
        "recommendation": row.recommendation,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _latest_row(db: AsyncSession, site_id) -> Optional[LiveReading]:
    return (
        await db.execute(
            select(LiveReading)
            .where(LiveReading.site_id == site_id)
            .order_by(LiveReading.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("/watch")
async def watch_site(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    settings = get_settings()
    if not settings.live_key:
        raise HTTPException(status_code=404, detail="No Live key configured")

    site = await _resolve_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="No site found")

    walk_run = await _latest_walk_run(db, site.id)
    report = await build_report(db, site, walk_run=walk_run)
    result = await send_report(settings.live_url, settings.live_key, report)
    if "error" in result:
        return JSONResponse(status_code=502, content={"error": result["error"]})

    reading = result.get("reading", {})
    row = LiveReading(
        site_id=site.id,
        live_reading_id=result.get("reading_id"),
        headline=reading.get("headline", ""),
        paragraphs=reading.get("paragraphs", []),
        verdict=reading.get("verdict", ""),
        changes=reading.get("changes", []),
        benchmarks=reading.get("benchmarks", []),
        recommendation=reading.get("recommendation"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _reading_dict(row)


@router.get("/reading")
async def reading(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site = await _resolve_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="No site found")
    row = await _latest_row(db, site.id)
    if row is None:
        raise HTTPException(status_code=404, detail="No reading yet")
    return _reading_dict(row)


@router.get("/status")
async def status(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    settings = get_settings()
    site = await _resolve_site(db, site_id)
    row = await _latest_row(db, site.id) if site else None
    last_at = row.created_at.isoformat() if row and row.created_at else None
    return {
        "key_set": bool(settings.live_key),
        "last_send": last_at,
        "last_reading_at": last_at,
    }
