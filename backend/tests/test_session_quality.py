"""Traffic-quality verdicts are stored when events land and read back, never recomputed.

Each test names the promise it holds; remove the matching hook and it must fail.
"""
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, delete, inspect, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from database import Base  # noqa: E402
from migrations.m004_session_quality import upgrade as m004  # noqa: E402
from models.behavior import BehaviorEvent  # noqa: E402
from models.event import Event  # noqa: E402
from models.session import Session  # noqa: E402
from models.site import Site  # noqa: E402
from routers.analytics import _traffic_quality_context, _quality_payload  # noqa: E402
from services.log_importer import import_log_file  # noqa: E402
from services.session_quality import backfill, classify_sessions, count_unclassified  # noqa: E402
from services.traffic_quality import classify_session  # noqa: E402

BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"


async def no_geo(_ip):
    return {}


class _DbCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "q.db"
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"
        self.engine = create_async_engine(self.db_url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.site_id = uuid.uuid4()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            db.add(Site(id=self.site_id, domain="q.example", name="Q"))
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    def _session(self, sid, page_count=1, referrer_domain=None, minutes_ago=5, traffic_class=None):
        return Session(
            id=sid, site_id=self.site_id, page_count=page_count, referrer_domain=referrer_domain,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            traffic_class=traffic_class,
        )

    def _event(self, sid, path="/page", ua=BROWSER_UA, **extra):
        return Event(
            site_id=self.site_id, session_id=sid, page_url=f"https://q.example{path}",
            user_agent=ua, ip_hash="h", is_bot=False, is_404=False,
            timestamp=datetime.now(timezone.utc), **extra,
        )


class MigrationTests(_DbCase):
    async def test_m004_adds_columns_and_is_idempotent(self):
        async with self.engine.begin() as conn:  # a pre-m004 sessions table
            await conn.execute(text("DROP TABLE sessions"))
            await conn.execute(text("CREATE TABLE sessions (id VARCHAR(64) PRIMARY KEY, site_id CHAR(32), started_at TIMESTAMP)"))
        async with self.engine.begin() as conn:
            await conn.run_sync(m004)
            await conn.run_sync(m004)  # second run must not raise on existing columns/indexes
            columns = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("sessions")})
            indexes = await conn.run_sync(lambda c: {ix["name"] for ix in inspect(c).get_indexes("sessions")})
        self.assertTrue({"traffic_class", "quality_confidence", "quality_reasons", "quality_at"} <= columns)
        self.assertIn("ix_sessions_site_started_class", indexes)


class StoreOnWriteTests(_DbCase):
    async def test_classify_sessions_matches_the_pure_classifier(self):
        async with self.sessions() as db:
            db.add(self._session("s1", page_count=2, referrer_domain="www.google.com"))
            db.add(self._event("s1", "/a"))
            db.add(self._event("s1", "/b"))
            db.add(self._session("s2"))
            db.add(self._event("s2", "/wp-login.php"))
            await db.commit()
            written = await classify_sessions(db, ["s1", "s2", "missing"])
            await db.commit()
            rows = {r.id: r for r in (await db.execute(select(Session))).scalars().all()}
        self.assertEqual(written, 2)
        self.assertEqual(rows["s1"].traffic_class, "likely_human")
        self.assertEqual(rows["s2"].traffic_class, "suspicious")
        self.assertIn("scanner/security path", rows["s2"].quality_reasons)
        self.assertIsNotNone(rows["s1"].quality_at)
        expected = classify_session(rows["s1"], [self._event("s1", "/a"), self._event("s1", "/b")])
        self.assertEqual(rows["s1"].quality_confidence, expected["confidence"])

    async def test_new_evidence_upgrades_the_stored_verdict(self):
        async with self.sessions() as db:
            db.add(self._session("s1"))
            db.add(self._event("s1", "/a"))
            await db.commit()
            await classify_sessions(db, ["s1"])
            await db.commit()
            self.assertEqual((await db.get(Session, "s1")).traffic_class, "unknown")

            db.add(self._event("s1", "/b", screen_width=1440, language="en"))  # the JS beacon arrives
            await db.commit()
            await classify_sessions(db, ["s1"])
            await db.commit()
            db.expire_all()
            self.assertEqual((await db.get(Session, "s1")).traffic_class, "verified_human")

    async def test_behaviour_events_count_as_proof(self):
        async with self.sessions() as db:
            db.add(self._session("s1"))
            db.add(self._event("s1", "/a"))
            db.add(BehaviorEvent(site_id=self.site_id, session_id="s1", page_url="https://q.example/a",
                                 event_type="scroll", timestamp=datetime.now(timezone.utc)))
            await db.commit()
            await classify_sessions(db, ["s1"])
            await db.commit()
            self.assertEqual((await db.get(Session, "s1")).traffic_class, "verified_human")

    async def test_log_import_leaves_no_session_unclassified(self):
        log_path = Path(self.tmp.name) / "access.log"
        lines = [
            f'198.51.100.{i} - - [14/Aug/2026:12:00:{i:02d} +0000] "GET /catalogue/{i} HTTP/1.1" 200 5000 "-" "{BROWSER_UA}"\n'
            for i in range(1, 6)
        ]
        lines.append('203.0.113.9 - - [14/Aug/2026:12:00:20 +0000] "GET /wp-login.php HTTP/1.1" 404 500 "-" "Mozilla/5.0"\n')
        log_path.write_text("".join(lines))
        with patch("services.log_importer.resolve_geo", no_geo):
            result = await import_log_file(filepath=str(log_path), domain="q.example", db_url=self.db_url)
        self.assertEqual(result["errors"], 0)
        async with self.sessions() as db:
            self.assertEqual(await count_unclassified(db), 0)
            classes = [r[0] for r in (await db.execute(select(Session.traffic_class))).all()]
        self.assertIn("suspicious", classes)
        self.assertEqual(len(classes), result["sessions"])


class BackfillTests(_DbCase):
    async def test_backfill_classifies_every_pending_session_newest_first(self):
        async with self.sessions() as db:
            for i in range(7):
                db.add(self._session(f"s{i}", minutes_ago=i))
                db.add(self._event(f"s{i}", f"/p{i}", screen_width=800))
            await db.commit()
            self.assertEqual(await count_unclassified(db), 7)
        done = await backfill(self.sessions, batch=3, pause=0)
        self.assertEqual(done, 7)
        async with self.sessions() as db:
            self.assertEqual(await count_unclassified(db), 0)
            classes = {r[0] for r in (await db.execute(select(Session.traffic_class))).all()}
        self.assertEqual(classes, {"verified_human"})


class ReadFromStoredTests(_DbCase):
    async def test_dashboard_counts_come_from_the_stored_column_only(self):
        async with self.sessions() as db:
            db.add(self._session("v", traffic_class="verified_human"))
            db.add(self._session("l", traffic_class="likely_human"))
            db.add(self._session("x", traffic_class="suspicious"))
            db.add(self._session("p"))  # not yet classified
            db.add(self._event("v", "/wp-login.php"))  # would be "suspicious" if re-derived
            await db.commit()
            await db.execute(delete(Event))  # no events at all: a read must not need them
            await db.commit()
            ctx = await _traffic_quality_context(db, 30, str(self.site_id))
            payload = _quality_payload(ctx, 30)
        self.assertEqual(payload["verified_humans"], 1)
        self.assertEqual(payload["likely_humans"], 1)
        self.assertEqual(payload["suspicious_sessions"], 1)
        self.assertEqual(payload["unclassified_sessions"], 1)
        self.assertEqual(payload["total_sessions"], 4)
        self.assertEqual(payload["real_traffic_estimate"], 2)
        self.assertIn("not classified yet", payload["note"])


if __name__ == "__main__":
    unittest.main()
