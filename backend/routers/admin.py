import csv
import io
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from higashi_reading.crawlers import LEGACY_TO_STANCE, STANCES, legacy_value
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from database import get_db
from models.event import Event
from models.session import Session
from models.site import Site
from routers.auth import require_admin
from config import get_settings
from services.app_config import (
    PUBLIC_URL_KEY,
    SNIPPET_MODE_KEY,
    get_value as get_app_value,
    set_value as set_app_value,
    normalize_public_url,
    probe_snippet_mode,
)

router = APIRouter()

# Same file the settings loader reads; see config.env_file_path().
def _env_path() -> str:
    from config import env_file_path
    return env_file_path()


def dotenv_set_key(path: str, key: str, value: str):
    """Write one setting and keep the file owner-only — it holds API keys."""
    from dotenv import set_key
    set_key(path, key, value)
    os.chmod(path, 0o600)


def _key_tail(k: str) -> str:
    return "…" + k[-4:] if len(k) > 12 else "****"


# --- AI Settings ---

class AIKeyRequest(BaseModel):
    anthropic_api_key: str


@router.get("/settings/ai")
async def get_ai_settings(_=Depends(require_admin)):
    settings = get_settings()
    configured = bool(settings.anthropic_api_key)
    preview = None
    if configured:
        k = settings.anthropic_api_key
        preview = _key_tail(k)
    return {"configured": configured, "key_preview": preview}


@router.post("/settings/ai")
async def save_ai_key(body: AIKeyRequest, _=Depends(require_admin)):
    key = body.anthropic_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # Validate key against Anthropic before saving
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=key)
        await client.models.list()
    except Exception as e:
        status = getattr(e, "status_code", None)
        reason = "Anthropic rejected this key" if status in (401, 403) else "Could not reach Anthropic to check this key"
        raise HTTPException(status_code=400, detail=f"Key validation failed: {reason}.")

    # Persist to .env
    try:
        dotenv_set_key(_env_path(), "ANTHROPIC_API_KEY", key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")

    # Clear the settings cache so the new key is picked up immediately
    get_settings.cache_clear()

    return {"ok": True}


@router.delete("/settings/ai")
async def remove_ai_key(_=Depends(require_admin)):
    try:
        dotenv_set_key(_env_path(), "ANTHROPIC_API_KEY", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


@router.get("/settings/ai/models")
async def get_ai_models(_=Depends(require_admin)):
    from services.ai_cost import MODEL_CATALOG
    s = get_settings()
    configured_providers = {
        p for p, key in [
            ("anthropic", s.anthropic_api_key),
            ("openai", s.openai_api_key),
            ("google", s.google_api_key),
        ] if key
    }
    return {
        "models": [
            {
                "id": model_id,
                **info,
                "is_default": model_id == s.ai_default_model,
                "provider_configured": info["provider"] in configured_providers,
            }
            for model_id, info in MODEL_CATALOG.items()
        ],
        "default_model": s.ai_default_model,
        "monthly_budget_usd": s.ai_monthly_budget_usd,
        "configured_providers": list(configured_providers),
    }


class AIProviderKeyRequest(BaseModel):
    provider: str
    api_key: str


@router.post("/settings/ai/provider-key")
async def save_provider_key(body: AIProviderKeyRequest, _=Depends(require_admin)):
    provider_env = {
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if body.provider not in provider_env:
        raise HTTPException(status_code=400, detail="Unknown provider")
    key = body.api_key.strip()
    try:
        dotenv_set_key(_env_path(), provider_env[body.provider], key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


@router.delete("/settings/ai/provider-key/{provider}")
async def remove_provider_key(provider: str, _=Depends(require_admin)):
    provider_env = {"openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    if provider not in provider_env:
        raise HTTPException(status_code=400, detail="Unknown provider")
    try:
        dotenv_set_key(_env_path(), provider_env[provider], "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


class AIBudgetRequest(BaseModel):
    monthly_budget_usd: float = 0.0
    default_model: str = "claude-haiku-4-5-20251001"


# --- Public URL / snippet mode (used by tracker snippet generator) ---

class PublicUrlPayload(BaseModel):
    public_url: str
    snippet_mode: str = ""  # "clean" | "php" | "" (empty -> auto-probe)


@router.get("/settings/public-url")
async def get_public_url(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    return {
        "public_url": await get_app_value(db, PUBLIC_URL_KEY) or "",
        "snippet_mode": await get_app_value(db, SNIPPET_MODE_KEY) or "",
    }


@router.put("/settings/public-url")
async def save_public_url(
    body: PublicUrlPayload,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    url = normalize_public_url(body.public_url)
    if not url:
        raise HTTPException(status_code=400, detail="Public URL is required")
    mode = body.snippet_mode or await probe_snippet_mode(url) or "clean"
    if mode not in ("clean", "php"):
        raise HTTPException(status_code=400, detail="snippet_mode must be 'clean' or 'php'")
    await set_app_value(db, PUBLIC_URL_KEY, url)
    await set_app_value(db, SNIPPET_MODE_KEY, mode)
    await db.commit()
    return {"public_url": url, "snippet_mode": mode}


@router.post("/settings/ai/budget")
async def save_ai_budget(body: AIBudgetRequest, _=Depends(require_admin)):
    from services.ai_cost import MODEL_CATALOG
    if body.default_model not in MODEL_CATALOG:
        raise HTTPException(status_code=400, detail="Unknown model ID")
    try:
        dotenv_set_key(_env_path(), "AI_MONTHLY_BUDGET_USD", str(body.monthly_budget_usd))
        dotenv_set_key(_env_path(), "AI_DEFAULT_MODEL", body.default_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


class LiveSettingsRequest(BaseModel):
    live_key: str = ""  # blank keeps the existing key — it's never sent back to the browser
    live_url: str = ""
    site_type: str = "other"
    ai_stance: str = "search_only"


_SITE_TYPES = {"business", "blog", "shop", "directory", "other"}
_AI_STANCES = {"found", "search_only", "block_all"}
_STANCE_OPTIONS = [
    {"value": sid, "label": st["label"], "does": st["does"], "does_not": st["does_not"], "cost": st["cost"]}
    for sid, st in STANCES.items()
]


@router.get("/settings/live")
async def get_live_settings(_=Depends(require_admin)):
    settings = get_settings()
    return {
        "live_key_set": bool(settings.live_key),
        "live_url": settings.live_url,
        "site_type": settings.live_site_type,
        "ai_stance": settings.live_ai_stance,
        "stance": settings.live_stance if settings.live_stance in STANCES else LEGACY_TO_STANCE.get(settings.live_ai_stance, "allow_all"),
        "stance_options": _STANCE_OPTIONS,
    }


@router.post("/settings/live")
async def save_live_settings(body: LiveSettingsRequest, _=Depends(require_admin)):
    settings = get_settings()
    key = body.live_key.strip()
    if not key and not settings.live_key:
        raise HTTPException(status_code=400, detail="Live key cannot be empty")
    if body.site_type not in _SITE_TYPES:
        raise HTTPException(status_code=400, detail="Unknown site_type")
    # The card sends the five-way id; the three-way value is kept in step for older readers.
    if body.ai_stance in STANCES:
        stance, ai_stance = body.ai_stance, legacy_value(body.ai_stance)
    elif body.ai_stance in _AI_STANCES:
        stance, ai_stance = LEGACY_TO_STANCE[body.ai_stance], body.ai_stance
    else:
        raise HTTPException(status_code=400, detail="Unknown ai_stance")
    try:
        if key:
            dotenv_set_key(_env_path(), "LIVE_KEY", key)
        if body.live_url.strip():
            dotenv_set_key(_env_path(), "LIVE_URL", body.live_url.strip())
        dotenv_set_key(_env_path(), "LIVE_SITE_TYPE", body.site_type)
        dotenv_set_key(_env_path(), "LIVE_AI_STANCE", ai_stance)
        dotenv_set_key(_env_path(), "LIVE_STANCE", stance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


@router.delete("/settings/live")
async def remove_live_settings(_=Depends(require_admin)):
    try:
        dotenv_set_key(_env_path(), "LIVE_KEY", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


_READING_PROVIDERS = {"local", "byok", "live"}


class ReadingSettingsRequest(BaseModel):
    provider: str
    model: str = ""


@router.get("/settings/reading")
async def get_reading_settings(_=Depends(require_admin)):
    settings = get_settings()
    return {
        "provider": settings.walk_reading_provider if settings.walk_reading_provider in _READING_PROVIDERS else "local",
        "model": settings.walk_reading_model or settings.ai_default_model,
        "live_key_set": bool(settings.live_key),
        "keys_set": {
            "anthropic": bool(settings.anthropic_api_key),
            "openai": bool(settings.openai_api_key),
            "google": bool(settings.google_api_key),
        },
    }


@router.post("/settings/reading")
async def save_reading_settings(body: ReadingSettingsRequest, _=Depends(require_admin)):
    """Which provider writes the walk reading. Rules stay the ceiling whichever is chosen."""
    if body.provider not in _READING_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unknown provider")
    settings = get_settings()
    if body.provider == "live" and not settings.live_key:
        raise HTTPException(status_code=400, detail="Add a Live key first")
    try:
        dotenv_set_key(_env_path(), "WALK_READING_PROVIDER", body.provider)
        dotenv_set_key(_env_path(), "WALK_READING_MODEL", body.model.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {e}")
    get_settings.cache_clear()
    return {"ok": True}


@router.get("/settings/ai/usage")
async def get_ai_usage(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    from models.ai_usage import AIUsageLog
    settings = get_settings()
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(
            func.sum(AIUsageLog.estimated_cost_usd).label("spend"),
            func.count(AIUsageLog.id).label("calls"),
        ).where(AIUsageLog.created_at >= month_start)
    )
    row = result.one()
    monthly_spend = round(row.spend or 0.0, 4)
    budget = settings.ai_monthly_budget_usd
    return {
        "monthly_spend_usd": monthly_spend,
        "monthly_budget_usd": budget,
        "budget_remaining_usd": max(0.0, round(budget - monthly_spend, 4)) if budget > 0 else None,
        "calls_this_month": row.calls or 0,
        "budget_set": budget > 0,
    }


# Everything below is existing admin code
settings = get_settings()


# --- Export ---

@router.get("/export/events")
async def export_events(
    format: str = Query("csv", regex="^(csv|json)$"),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Event)
        .where(Event.timestamp >= since, Event.is_bot == False)
        .order_by(Event.timestamp.desc())
        .limit(100_000)
    )
    events = result.scalars().all()

    if format == "json":
        data = [
            {
                "timestamp": e.timestamp.isoformat(),
                "page_url": e.page_url,
                "referrer": e.referrer,
                "country": e.country,
                "region": e.region,
                "city": e.city,
                "browser": e.browser,
                "os": e.os,
                "device_type": e.device_type,
                "duration_seconds": e.duration_seconds,
                "scroll_depth": e.scroll_depth,
            }
            for e in events
        ]
        return StreamingResponse(
            iter([json.dumps(data, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=events_{days}d.json"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "page_url", "referrer", "country", "region", "city", "browser", "os", "device_type", "duration_seconds", "scroll_depth"])
    for e in events:
        writer.writerow([
            e.timestamp.isoformat(), e.page_url, e.referrer or "",
            e.country or "", e.region or "", e.city or "",
            e.browser or "", e.os or "", e.device_type or "",
            e.duration_seconds or "", e.scroll_depth or "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=events_{days}d.csv"},
    )


@router.get("/export/summary")
async def export_summary(
    format: str = Query("json", regex="^(csv|json)$"),
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", Event.timestamp).label("day"),
            func.count(Event.id).label("views"),
            func.count(func.distinct(Event.ip_hash)).label("visitors"),
            func.count(func.distinct(Event.session_id)).label("sessions"),
        )
        .where(Event.timestamp >= since, Event.is_bot == False)
        .group_by("day")
        .order_by("day")
    )
    rows = result.all()

    if format == "json":
        data = [{"date": str(r.day.date()), "views": r.views, "visitors": r.visitors, "sessions": r.sessions} for r in rows]
        return StreamingResponse(
            iter([json.dumps(data, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=summary_{days}d.json"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "views", "visitors", "sessions"])
    for r in rows:
        writer.writerow([str(r.day.date()), r.views, r.visitors, r.sessions])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=summary_{days}d.csv"},
    )


# --- Retention / Cleanup ---

@router.get("/storage")
async def storage_stats(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    total_events = await db.execute(select(func.count(Event.id)))
    total_sessions = await db.execute(select(func.count(Session.id)))
    oldest = await db.execute(select(func.min(Event.timestamp)))
    return {
        "total_events": total_events.scalar() or 0,
        "total_sessions": total_sessions.scalar() or 0,
        "oldest_event": str(oldest.scalar()),
        "retention_days": settings.raw_event_retention_days,
    }


@router.delete("/purge/old-events")
async def purge_old_events(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    cutoff = datetime.utcnow() - timedelta(days=settings.raw_event_retention_days)
    count_result = await db.execute(
        select(func.count(Event.id)).where(Event.timestamp < cutoff)
    )
    count = count_result.scalar() or 0

    async def do_purge():
        async with db.begin():
            await db.execute(delete(Event).where(Event.timestamp < cutoff))

    background_tasks.add_task(do_purge)
    return {"message": f"Purging {count} events older than {settings.raw_event_retention_days} days", "count": count}


@router.delete("/purge/date-range")
async def purge_date_range(
    start: str = Query(..., description="ISO date, e.g. 2025-01-01"),
    end: str = Query(..., description="ISO date, e.g. 2025-03-01"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    count_result = await db.execute(
        select(func.count(Event.id)).where(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
    )
    count = count_result.scalar() or 0
    await db.execute(delete(Event).where(Event.timestamp >= start_dt, Event.timestamp <= end_dt))
    await db.commit()
    return {"message": f"Deleted {count} events between {start} and {end}", "count": count}


@router.delete("/purge/all")
async def purge_all(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    await db.execute(delete(Event))
    await db.execute(delete(Session))
    await db.commit()
    return {"message": "All analytics data deleted"}
