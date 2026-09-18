#!/usr/bin/env python3
"""
Retention cleanup script — run via cron or manually.

Deletes raw events older than RAW_EVENT_RETENTION_DAYS (default 90).
Aggregated daily summaries are preserved forever.

Cron example (runs daily at 3am):
    0 3 * * * /path/to/venv/bin/python /app/scripts/retention_cleanup.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import delete, select, func, text

from config import get_settings
from models.event import Event


async def run():
    settings = get_settings()
    cutoff = datetime.utcnow() - timedelta(days=settings.raw_event_retention_days)

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        count_result = await db.execute(
            select(func.count(Event.id)).where(Event.timestamp < cutoff)
        )
        count = count_result.scalar() or 0

        if count == 0:
            print(f"[retention] No events older than {settings.raw_event_retention_days} days. Nothing to do.")
            return

        print(f"[retention] Deleting {count:,} events older than {cutoff.date()} ...")
        await db.execute(delete(Event).where(Event.timestamp < cutoff))
        await db.commit()
        print(f"[retention] Done. {count:,} events removed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
