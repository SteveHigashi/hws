import json
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from database import get_db
from models.site import Site
from models.geo_probe import GeoProbeQuery, GeoProbeResult
from models.ai_usage import AIUsageLog
from routers.auth import get_current_user, require_admin
from services.ai_cost import MODEL_CATALOG, estimate_cost
from services.ai_providers import call_model, get_provider
from config import get_settings

router = APIRouter()

_PROBE_SYSTEM = """You are a helpful assistant answering questions about software tools and services. Give honest, specific recommendations using real product names. Do not be influenced by what the asker might want to hear."""


def _extract_excerpt(text: str, brand: str, max_sentences: int = 2) -> str:
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    hits = [s for s in sentences if brand.lower() in s.lower()]
    return ". ".join(hits[:max_sentences]) + ("." if hits else "") if hits else ""


async def _resolve_site(db: AsyncSession, site_id: Optional[str]) -> Optional[Site]:
    if site_id:
        try:
            uid = _uuid.UUID(site_id)
            r = await db.execute(select(Site).where(Site.id == uid))
            s = r.scalar_one_or_none()
            if s:
                return s
        except ValueError:
            pass
    r = await db.execute(select(Site).limit(1))
    return r.scalar_one_or_none()


# --- Query management ---

class ProbeQueryCreate(BaseModel):
    query_text: str
    brand_name: str
    site_id: Optional[str] = None


@router.get("/queries")
async def list_queries(
    site_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site = await _resolve_site(db, site_id)
    if not site:
        return []
    result = await db.execute(
        select(GeoProbeQuery)
        .where(GeoProbeQuery.site_id == site.id)
        .order_by(GeoProbeQuery.created_at)
    )
    queries = result.scalars().all()

    out = []
    for q in queries:
        # get last 10 results for trend
        res_r = await db.execute(
            select(GeoProbeResult)
            .where(GeoProbeResult.probe_id == q.id)
            .order_by(desc(GeoProbeResult.ran_at))
            .limit(10)
        )
        results = res_r.scalars().all()
        mention_rate = (
            round(sum(1 for r in results if r.mentioned) / len(results) * 100)
            if results else None
        )
        out.append({
            "id": str(q.id),
            "query_text": q.query_text,
            "brand_name": q.brand_name,
            "is_active": q.is_active,
            "last_run_at": q.last_run_at.isoformat() if q.last_run_at else None,
            "mention_rate": mention_rate,
            "result_count": len(results),
            "latest_mentioned": results[0].mentioned if results else None,
            "latest_excerpt": results[0].mention_excerpt if results else None,
        })
    return out


@router.post("/queries")
async def create_query(
    body: ProbeQueryCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    site = await _resolve_site(db, body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="No site found")
    # Limit to 5 active probes per site
    count_r = await db.execute(
        select(func.count(GeoProbeQuery.id))
        .where(GeoProbeQuery.site_id == site.id, GeoProbeQuery.is_active == True)
    )
    if (count_r.scalar() or 0) >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 active probes per site")
    q = GeoProbeQuery(
        site_id=site.id,
        query_text=body.query_text.strip(),
        brand_name=body.brand_name.strip(),
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return {"id": str(q.id), "query_text": q.query_text, "brand_name": q.brand_name}


@router.delete("/queries/{probe_id}")
async def delete_query(
    probe_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    uid = _uuid.UUID(probe_id)
    r = await db.execute(select(GeoProbeQuery).where(GeoProbeQuery.id == uid))
    q = r.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Probe not found")
    await db.delete(q)
    await db.commit()
    return {"ok": True}


# --- Results ---

@router.get("/results")
async def get_results(
    probe_id: str = Query(...),
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    uid = _uuid.UUID(probe_id)
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(GeoProbeResult)
        .where(GeoProbeResult.probe_id == uid, GeoProbeResult.ran_at >= since)
        .order_by(GeoProbeResult.ran_at)
    )
    rows = result.scalars().all()
    return [
        {
            "ran_at": r.ran_at.isoformat(),
            "mentioned": r.mentioned,
            "mention_excerpt": r.mention_excerpt,
            "model": r.model,
            "estimated_cost_usd": r.estimated_cost_usd,
        }
        for r in rows
    ]


# --- Run probes ---

class RunRequest(BaseModel):
    site_id: Optional[str] = None
    probe_id: Optional[str] = None  # run only this probe if set


@router.post("/run")
async def run_probes(
    body: RunRequest,
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
        raise HTTPException(status_code=400, detail=f"No API key configured for {provider}")

    site = await _resolve_site(db, body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="No site found")

    # Budget check
    if settings.ai_monthly_budget_usd > 0:
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spend_r = await db.execute(
            select(func.sum(AIUsageLog.estimated_cost_usd)).where(AIUsageLog.created_at >= month_start)
        )
        if (spend_r.scalar() or 0.0) >= settings.ai_monthly_budget_usd:
            raise HTTPException(status_code=402, detail="Monthly AI budget exceeded")

    # Fetch queries to run
    q_filter = [GeoProbeQuery.site_id == site.id, GeoProbeQuery.is_active == True]
    if body.probe_id:
        q_filter.append(GeoProbeQuery.id == _uuid.UUID(body.probe_id))
    q_result = await db.execute(select(GeoProbeQuery).where(*q_filter))
    queries = q_result.scalars().all()

    if not queries:
        raise HTTPException(status_code=404, detail="No active probes found")

    ran = []
    for q in queries:
        user_msg = (
            f"{q.query_text}\n\n"
            f"Please list at least 3-5 specific options with real product or service names and brief explanations."
        )
        try:
            text, in_tok, out_tok = await call_model(
                model, _PROBE_SYSTEM, user_msg, api_keys, max_tokens=800
            )
            mentioned = q.brand_name.lower() in text.lower()
            excerpt = _extract_excerpt(text, q.brand_name) if mentioned else ""
            cost = estimate_cost(model, in_tok, out_tok)

            result_row = GeoProbeResult(
                probe_id=q.id,
                site_id=site.id,
                model=model,
                mentioned=mentioned,
                mention_excerpt=excerpt,
                full_response=text,
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_cost_usd=cost,
            )
            db.add(result_row)

            db.add(AIUsageLog(
                site_id=site.id,
                user_id=current_user.id,
                endpoint="geo_probe",
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_cost_usd=cost,
            ))

            q.last_run_at = datetime.utcnow()

            ran.append({
                "probe_id": str(q.id),
                "query_text": q.query_text,
                "mentioned": mentioned,
                "excerpt": excerpt,
                "cost": cost,
            })
        except Exception as exc:
            ran.append({"probe_id": str(q.id), "error": str(exc)})

    await db.commit()
    return {"ran": ran, "model_used": model}
