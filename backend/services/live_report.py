"""Build the privacy-safe counts bundle this install sends to Higashi Live.

Only aggregate numbers, names, and enum states leave this function — never an
IP address, a path, a URL, a user agent, or page content. See
docs/LIVE_STEP1_CODEX_PROMPT.md for the body Live expects and
docs/LIVE_STEP2_NOTES.md for what this build deliberately leaves out.
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.bot_visit import BotVisit
from models.event import Event
from models.geo_probe import GeoProbeResult
from models.session import Session as SessionModel
from models.behavior import BehaviorEvent
from models.site import Site

_VERDICT_MAP = {
    "walk_detected": "Catalogue walk detected",
    "suspicious": "Suspicious",
    "no_walk_detected": "No walk detected",
}

_INSUFFICIENT_WALK = {
    "verdict": "Insufficient data",
    "shape_triggered": False,
    "order_triggered": False,
    "distributed_signal": False,
    "asset_fetch_signal": False,
    "per_address_rate": 0.0,
    "records_taken_estimate": 0,
}


def _map_walk_run(run) -> dict:
    """Pure mapping from a WalkDetectionRun row to the bundle's walk shape.

    Catalogue walk detection is an optional layer-2 feature (see main.py);
    core services never import that model directly, so callers fetch the row
    themselves (if the feature is even installed) and hand it here duck-typed.
    """
    if run is None:
        return dict(_INSUFFICIENT_WALK)
    triggers = run.triggers or []
    signals = run.signals or []
    return {
        "verdict": _VERDICT_MAP.get(run.verdict, "Insufficient data"),
        "shape_triggered": "shape" in triggers,
        "order_triggered": "order" in triggers,
        "distributed_signal": "referer_absence" in signals or "shared_queue_fingerprint" in signals,
        "asset_fetch_signal": "asset_fetch_absence" in signals,
        "per_address_rate": run.median_requests_per_address_day or 0.0,
        "records_taken_estimate": run.records_taken or 0,
    }


async def _crawlers_bundle(db: AsyncSession, site_id, since: datetime) -> list[dict]:
    rows = await db.execute(
        select(
            BotVisit.bot_name,
            BotVisit.verification_state,
            func.count(BotVisit.id).label("hits"),
            func.coalesce(func.sum(BotVisit.response_bytes), 0).label("bytes"),
        )
        .where(BotVisit.site_id == site_id, BotVisit.timestamp >= since)
        .group_by(BotVisit.bot_name, BotVisit.verification_state)
    )
    return [
        {
            "name": row.bot_name,
            "verified": row.verification_state or "unverified",
            "hits": row.hits,
            "bytes": int(row.bytes or 0),
            # WalkDetectionRun tracks records taken per site/window, not per
            # crawler name — there is no honest non-zero figure to put here yet.
            "records_taken": 0,
        }
        for row in rows.all()
    ]


async def _geo_bundle(db: AsyncSession, site_id, since: datetime) -> list[dict] | None:
    rows = await db.execute(
        select(GeoProbeResult)
        .where(GeoProbeResult.site_id == site_id, GeoProbeResult.ran_at >= since)
        .order_by(GeoProbeResult.ran_at.desc())
        .limit(50)
    )
    results = rows.scalars().all()
    if not results:
        return None
    return [
        {
            # The product runs one configured model per probe today, not
            # separate named engines — the model id is the closest honest label.
            "engine": r.model,
            "query_id": str(r.probe_id),
            "mentioned": bool(r.mentioned),
            "cited": False,
        }
        for r in results
    ]


async def build_report(db: AsyncSession, site: Site, period_days: int = 1, walk_run=None) -> dict:
    settings = get_settings()
    period_end = date.today()
    period_start = period_end - timedelta(days=max(period_days, 1) - 1)
    since = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)

    pageviews_human = (
        await db.execute(
            select(func.count(Event.id)).where(
                Event.site_id == site.id, Event.timestamp >= since, Event.is_bot == False
            )
        )
    ).scalar() or 0
    sessions_human = (
        await db.execute(
            select(func.count(SessionModel.id)).where(
                SessionModel.site_id == site.id, SessionModel.started_at >= since
            )
        )
    ).scalar() or 0
    engaged_sessions = (
        await db.execute(
            select(func.count(func.distinct(BehaviorEvent.session_id))).where(
                BehaviorEvent.site_id == site.id, BehaviorEvent.timestamp >= since
            )
        )
    ).scalar() or 0
    engaged_sessions = min(engaged_sessions, sessions_human)

    return {
        "site_id": str(site.id),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "site_type": settings.live_site_type,
        "ai_stance": settings.live_ai_stance,
        "pageviews_human": pageviews_human,
        "sessions_human": sessions_human,
        "engaged_sessions": engaged_sessions,
        "crawlers": await _crawlers_bundle(db, site.id, since),
        "walk": _map_walk_run(walk_run),
        "geo": await _geo_bundle(db, site.id, since),
    }
