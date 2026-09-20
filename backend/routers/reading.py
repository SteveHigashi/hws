"""GET /api/reading — the walk reading for the dashboard, from whichever provider is set.

  provider=local  the fixed rules on this install (free, nothing leaves the box)
  provider=byok   the same prompt through the customer's own model key (still local)
  provider=live   Higashi Live's stored reading (history, comparisons, weekly email)

The rules are the ceiling for all three. Defaults to settings.walk_reading_provider.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from routers.auth import get_current_user
from routers.live import _latest_row, _latest_walk_run, _reading_dict, _resolve_site
from services.live_report import build_report
from services.walk_reading import PROVIDERS, byok_reading, local_reading

router = APIRouter()

PROVIDER_LABELS = {"local": "Higashi rules", "byok": "Your AI key", "live": "Higashi Live"}


@router.get("")
async def reading(
    site_id: Optional[str] = Query(None),
    provider: Optional[str] = Query(None, pattern="^(local|byok|live)$"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    settings = get_settings()
    chosen = provider or settings.walk_reading_provider
    if chosen not in PROVIDERS:
        chosen = "local"
    site = await _resolve_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="No site found")

    if chosen == "live":
        row = await _latest_row(db, site.id)
        if row is None:
            raise HTTPException(status_code=404, detail="No Live reading yet")
        body = _reading_dict(row)
        return {"provider": "live", "provider_used": "live", "label": PROVIDER_LABELS["live"],
                "reading": body, "generated_at": body.get("created_at"), "note": None}

    walk_run = await _latest_walk_run(db, site.id)
    report = await build_report(db, site, walk_run=walk_run)
    note = None
    used = "local"
    if chosen == "byok":
        api_keys = {
            "anthropic": settings.anthropic_api_key,
            "openai": settings.openai_api_key,
            "google": settings.google_api_key,
        }
        model = settings.walk_reading_model or settings.ai_default_model
        body, used, note = await byok_reading(report, model, api_keys)
    else:
        body = local_reading(report)
    return {
        "provider": chosen,
        "provider_used": used,
        "label": PROVIDER_LABELS[used],
        "reading": body.model_dump(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
