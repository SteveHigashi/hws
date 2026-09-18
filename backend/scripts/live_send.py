#!/usr/bin/env python3
"""
Send today's counts bundle to Higashi Live and store the reading — run via cron.

No-op if no Live key is configured. Sends for the first active site only; see
docs/LIVE_STEP2_NOTES.md for why (a Live key registers to one site_id).

Cron example (once a day, 07:00):
    0 7 * * * /path/to/venv/bin/python /app/scripts/live_send.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from config import get_settings
from models.site import Site
from models.live_reading import LiveReading
from services.live_client import send_report
from services.live_report import build_report

# Optional layer-2 feature (see backend/main.py) — this script still runs
# without it, just always reporting "Insufficient data" for the walk.
try:
    from models.walk_detection import WalkDetectionRun
except ImportError:
    WalkDetectionRun = None


async def _latest_walk_run(db, site_id):
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


async def run():
    settings = get_settings()
    if not settings.live_key:
        print("[live_send] No Live key configured. Nothing to do.")
        return

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        site = (await db.execute(select(Site).where(Site.active == True).limit(1))).scalar_one_or_none()
        if site is None:
            print("[live_send] No active site configured. Nothing to do.")
            await engine.dispose()
            return

        walk_run = await _latest_walk_run(db, site.id)
        report = await build_report(db, site, walk_run=walk_run)
        result = await send_report(settings.live_url, settings.live_key, report)
        if "error" in result:
            print(f"[live_send] Send failed: {result['error']}")
            await engine.dispose()
            return

        reading = result.get("reading", {})
        db.add(LiveReading(
            site_id=site.id,
            live_reading_id=result.get("reading_id"),
            headline=reading.get("headline", ""),
            paragraphs=reading.get("paragraphs", []),
            verdict=reading.get("verdict", ""),
            changes=reading.get("changes", []),
            benchmarks=reading.get("benchmarks", []),
        ))
        await db.commit()
        print(f"[live_send] Sent. Reading: {reading.get('headline', '(no headline)')}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
