"""Read APIs and persistence adapter for the optional walk-detection layer."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database import get_db
from models.behavior import BehaviorEvent
from models.bot_visit import BotVisit
from models.session import Session
from models.site import Site
from models.walk_detection import WalkDetectionRun
from routers.analytics import clean_site_id
from routers.auth import get_current_user
from services.walk_detection import DetectionResult, engagement_absence_signal


router = APIRouter()


def _required_site_id(site_id: str):
    value = clean_site_id(site_id)
    if value is None:
        raise HTTPException(status_code=422, detail="site_id must be a valid site UUID")
    return value


def _run_dict(run: WalkDetectionRun) -> dict:
    return {
        "id": str(run.id),
        "site_id": str(run.site_id),
        "window_start": run.window_start.isoformat(),
        "window_end": run.window_end.isoformat(),
        "verdict": run.verdict,
        "headline": run.headline,
        "score": run.score,
        "triggers": run.triggers or [],
        "signals": run.signals or [],
        "records_taken": run.records_taken,
        "total_content_requests": run.total_content_requests,
        "distinct_identities": run.distinct_identities,
        "shape_oneshot_identities": run.shape_oneshot_identities,
        "shape_share": run.shape_share,
        "order_pairs": run.order_pairs,
        "order_ratio": run.order_ratio,
        "content_responses": run.content_responses,
        "asset_responses": run.asset_responses,
        "assetless_identity_share": run.assetless_identity_share,
        "referer_absence_ratio": run.referer_absence_ratio,
        "shared_queue_pairs": run.shared_queue_pairs,
        "shared_queue_ratio": run.shared_queue_ratio,
        "median_requests_per_address_day": run.median_requests_per_address_day,
        "p95_requests_per_address_day": run.p95_requests_per_address_day,
        "singleton_address_share": run.singleton_address_share,
        "rate_blind_spot": run.rate_blind_spot,
        "forged_claims": run.forged_claims,
        "verified_claims": run.verified_claims,
        "unverified_claims": run.unverified_claims,
        "engagement_absence_ratio": run.engagement_absence_ratio,
    }


async def persist_detection_results(
    db_url: str,
    site_id,
    results: list[DetectionResult],
) -> int:
    """Persist pure results; no address or unsalted identity enters this table."""
    if not results:
        return 0
    engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(WalkDetectionRun.__table__.create, checkfirst=True)

        async with SessionLocal() as db:
            stored = 0
            for result in results:
                session_count = (
                    await db.execute(
                        select(func.count(distinct(Session.id))).where(
                            Session.site_id == site_id,
                            Session.started_at >= result.window_start,
                            Session.started_at <= result.window_end,
                        )
                    )
                ).scalar() or 0
                engaged_count = (
                    await db.execute(
                        select(func.count(distinct(BehaviorEvent.session_id))).where(
                            BehaviorEvent.site_id == site_id,
                            BehaviorEvent.timestamp >= result.window_start,
                            BehaviorEvent.timestamp <= result.window_end,
                        )
                    )
                ).scalar() or 0
                engagement_absence = engagement_absence_signal(session_count, engaged_count)
                signals = list(result.signals)
                if engagement_absence is not None and engagement_absence >= 0.90:
                    signals.append("engagement_absence")

                # Re-importing the same cursor window replaces the analysis
                # instead of double-counting it on the dashboard.
                await db.execute(
                    delete(WalkDetectionRun).where(
                        WalkDetectionRun.site_id == site_id,
                        WalkDetectionRun.window_start == result.window_start,
                        WalkDetectionRun.window_end == result.window_end,
                    )
                )
                payload = result.to_dict()
                payload.pop("window_start")
                payload.pop("window_end")
                payload["triggers"] = list(result.triggers)
                payload["signals"] = sorted(set(signals))
                payload["engagement_absence_ratio"] = engagement_absence
                db.add(WalkDetectionRun(
                    site_id=site_id,
                    window_start=result.window_start,
                    window_end=result.window_end,
                    **payload,
                ))
                stored += 1
            await db.commit()
            return stored
    finally:
        await engine.dispose()


@router.get("/overview")
async def walk_overview(
    site_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site_uuid = _required_site_id(site_id)
    site = (await db.execute(select(Site).where(Site.id == site_uuid))).scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    runs = (
        await db.execute(
            select(WalkDetectionRun)
            .where(
                WalkDetectionRun.site_id == site_uuid,
                WalkDetectionRun.window_end >= since,
            )
            .order_by(WalkDetectionRun.window_end.desc())
        )
    ).scalars().all()

    if not runs:
        return {
            "site_id": str(site_uuid),
            "days": days,
            "verdict": "no_data",
            "headline": "Import an access log to check this catalogue for walking.",
            "score": 0,
            "windows_analyzed": 0,
            "walk_windows": 0,
            "suspicious_windows": 0,
            "records_taken": 0,
            "evidence": {},
            "rate_warning": None,
        }

    worst = max(runs, key=lambda run: run.score)
    walk_windows = sum(run.verdict == "walk_detected" for run in runs)
    suspicious_windows = sum(run.verdict == "suspicious" for run in runs)
    if walk_windows:
        verdict = "walk_detected"
        headline = f"Catalogue walking was detected in {walk_windows} log window{'s' if walk_windows != 1 else ''}."
    elif suspicious_windows:
        verdict = "suspicious"
        headline = "Suspicious catalogue access was found, but no walk pattern was proven."
    else:
        verdict = "no_walk_detected"
        headline = "No catalogue walk was detected in the analyzed log windows."

    trigger_counts = Counter(trigger for run in runs for trigger in (run.triggers or []))
    signal_counts = Counter(signal for run in runs for signal in (run.signals or []))
    rate_blind_spot = any(run.rate_blind_spot for run in runs)
    return {
        "site_id": str(site_uuid),
        "days": days,
        "verdict": verdict,
        "headline": headline,
        "score": worst.score,
        "windows_analyzed": len(runs),
        "walk_windows": walk_windows,
        "suspicious_windows": suspicious_windows,
        "records_taken": sum(run.records_taken for run in runs),
        "first_seen": min(run.window_start for run in runs).isoformat(),
        "last_seen": max(run.window_end for run in runs).isoformat(),
        "evidence": {
            "triggers": dict(trigger_counts),
            "signals": dict(signal_counts),
            "max_oneshot_identities": max(run.shape_oneshot_identities for run in runs),
            "max_shape_share": max(run.shape_share for run in runs),
            "max_order_ratio": max(run.order_ratio for run in runs),
            "max_assetless_share": max(run.assetless_identity_share for run in runs),
            "max_referer_absence": max(run.referer_absence_ratio for run in runs),
            "max_shared_queue_ratio": max(run.shared_queue_ratio for run in runs),
            "max_engagement_absence": max(
                (run.engagement_absence_ratio for run in runs if run.engagement_absence_ratio is not None),
                default=None,
            ),
            "median_requests_per_address_day": worst.median_requests_per_address_day,
            "p95_requests_per_address_day": max(run.p95_requests_per_address_day for run in runs),
            "forged_claims": sum(run.forged_claims for run in runs),
            "verified_claims": sum(run.verified_claims for run in runs),
            "unverified_claims": sum(run.unverified_claims for run in runs),
        },
        "rate_warning": (
            "Most addresses made one request. Per-address rates are blind to a rotating pool and should not be read as reassuring."
            if rate_blind_spot else None
        ),
    }


@router.get("/runs")
async def detection_runs(
    site_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site_uuid = _required_site_id(site_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(WalkDetectionRun)
            .where(
                WalkDetectionRun.site_id == site_uuid,
                WalkDetectionRun.window_end >= since,
            )
            .order_by(WalkDetectionRun.window_end.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_run_dict(row) for row in rows]


@router.get("/crawler-claims")
async def crawler_claims(
    site_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    site_uuid = _required_site_id(site_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                BotVisit.bot_name,
                BotVisit.verification_state,
                func.count(BotVisit.id).label("requests"),
                func.count(distinct(BotVisit.ip_hash)).label("addresses"),
                func.max(BotVisit.timestamp).label("last_seen"),
            )
            .where(BotVisit.site_id == site_uuid, BotVisit.timestamp >= since)
            .group_by(BotVisit.bot_name, BotVisit.verification_state)
            .order_by(func.count(BotVisit.id).desc())
        )
    ).all()
    return [
        {
            "bot_name": row.bot_name,
            "verification_state": row.verification_state or "unverified",
            "requests": row.requests,
            "addresses": row.addresses,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in rows
    ]
