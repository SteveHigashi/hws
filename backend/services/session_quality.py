"""Classify sessions once, when their events land, and store the verdict.

The verdict is a pure function of the session's events (services.traffic_quality),
so it is recomputed for a session whenever that session receives something new:
a tracker pageview, a behaviour batch, or a log-import flush. A session can
therefore move up over its lifetime (a log-only "unknown" becomes "verified_human"
when the JS beacon arrives) but never has to be recomputed for a dashboard read.

`backfill()` fills the columns for sessions written before m004; it runs in the
background at startup, newest sessions first, so the dashboard window is served
first, and it yields between batches so requests keep flowing.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, update, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.behavior import BehaviorEvent
from models.event import Event
from models.session import Session
from services.traffic_quality import classify_session

log = logging.getLogger("higashi.session_quality")

_EVENT_COLS = (
    Event.session_id, Event.page_url, Event.referrer, Event.user_agent, Event.is_404,
    Event.duration_seconds, Event.scroll_depth, Event.screen_width, Event.screen_height,
    Event.language, Event.lcp, Event.fcp, Event.ttfb, Event.meta,
)
_CHUNK = 500  # SQLite bind-parameter limit is 999 on older builds


def _chunks(items: list, size: int = _CHUNK):
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def classify_sessions(db: AsyncSession, session_ids) -> int:
    """(Re)classify the given sessions from their stored events and write the verdict.

    Commits nothing: the caller owns the transaction. Returns the number of rows written.
    """
    ids = sorted({sid for sid in session_ids if sid})
    if not ids:
        return 0

    written = 0
    for chunk in _chunks(ids):
        sessions = (await db.execute(
            select(Session.id, Session.page_count, Session.referrer_domain)
            .where(Session.id.in_(chunk))
        )).all()
        if not sessions:
            continue

        events_by_session = defaultdict(list)
        rows = (await db.execute(
            select(*_EVENT_COLS).where(Event.session_id.in_(chunk)).order_by(Event.session_id, Event.timestamp)
        )).all()
        for row in rows:
            events_by_session[row.session_id].append(row)

        with_behavior = {
            row[0] for row in (await db.execute(
                select(distinct(BehaviorEvent.session_id)).where(BehaviorEvent.session_id.in_(chunk))
            )).all()
        }

        now = datetime.now(timezone.utc)
        for session in sessions:
            quality = classify_session(session, events_by_session.get(session.id, []), session.id in with_behavior)
            await db.execute(
                update(Session)
                .where(Session.id == session.id)
                .values(
                    traffic_class=quality["traffic_class"],
                    quality_confidence=quality["confidence"],
                    quality_reasons=quality["reasons"],
                    quality_at=now,
                )
            )
            written += 1
    return written


async def classify_and_commit(db: AsyncSession, session_ids) -> int:
    """Convenience for request handlers: classify, commit, never raise into the response."""
    try:
        n = await classify_sessions(db, session_ids)
        await db.commit()
        return n
    except Exception:  # the pageview is already stored; a failed verdict must not 500 the beacon
        log.exception("session classification failed")
        await db.rollback()
        return 0


async def count_unclassified(db: AsyncSession) -> int:
    return (await db.execute(
        select(func.count(Session.id)).where(Session.traffic_class.is_(None))
    )).scalar() or 0


async def backfill(session_factory, batch: int = 1000, pause: float = 0.05, limit: int | None = None) -> int:
    """Classify every session that has no verdict yet, newest first. Returns rows written."""
    total = 0
    while True:
        async with session_factory() as db:
            ids = [row[0] for row in (await db.execute(
                select(Session.id)
                .where(Session.traffic_class.is_(None))
                .order_by(Session.started_at.desc())
                .limit(batch)
            )).all()]
            if not ids:
                break
            n = await classify_sessions(db, ids)
            await db.commit()
        total += n
        if limit is not None and total >= limit:
            break
        if n < len(ids):  # rows vanished under us; avoid a hot loop on the same ids
            break
        await asyncio.sleep(pause)  # let requests through between batches
    return total


async def backfill_in_background(session_factory) -> None:
    """Startup task: log progress, never crash the app."""
    try:
        async with session_factory() as db:
            pending = await count_unclassified(db)
        if not pending:
            return
        log.info("session quality backfill: %d sessions to classify", pending)
        started = asyncio.get_event_loop().time()
        # 250 per batch: ~1 s of CPU between yields on the 1-vCPU box (measured 6.7 ms/session).
        done = await backfill(session_factory, batch=250, pause=0.1)
        log.info("session quality backfill: %d sessions classified in %.0f s",
                 done, asyncio.get_event_loop().time() - started)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("session quality backfill failed; the next start resumes it")
