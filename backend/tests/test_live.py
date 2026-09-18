import ipaddress
import re
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from database import Base  # noqa: E402
from models.behavior import BehaviorEvent  # noqa: E402
from models.bot_visit import BotVisit  # noqa: E402
from models.event import Event  # noqa: E402
from models.live_reading import LiveReading  # noqa: E402
from models.session import Session as SessionModel  # noqa: E402
from models.site import Site  # noqa: E402
from models.walk_detection import WalkDetectionRun  # noqa: E402
from routers import live as live_router  # noqa: E402
from routers.intelligence import _build_analytics_context  # noqa: E402
from services import live_client  # noqa: E402
from services.live_report import build_report  # noqa: E402


# Same shape of check Live itself runs on the way in (live/app/auth.py) — a
# private string is an IP, a URL, or something with a path/UA marker in it.
_UA_MARKERS = re.compile(r"mozilla/\d|chrome/\d|safari/\d|curl/\d|user-agent\s*:", re.IGNORECASE)


def _looks_private(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip("[]"))
        return True
    except ValueError:
        pass
    if re.search(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])", value):
        return True
    if re.match(r"^https?://", value) or "/" in value or "\\" in value:
        return True
    return bool(_UA_MARKERS.search(value))


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk_strings(v)


class LiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.NamedTemporaryFile(suffix=".db")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.temporary.name}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        self.site = Site(id=uuid.uuid4(), domain="example.test", name="Example")
        now = datetime.now(timezone.utc)
        async with self.sessions() as db:
            db.add(self.site)
            db.add(Event(
                id=uuid.uuid4(), site_id=self.site.id, session_id="s1",
                timestamp=now, page_url="https://example.test/", is_bot=False,
            ))
            db.add(SessionModel(id="s1", site_id=self.site.id, started_at=now))
            db.add(BehaviorEvent(
                id=uuid.uuid4(), site_id=self.site.id, session_id="s1",
                timestamp=now, page_url="https://example.test/", event_type="click",
                element_text="a bare user-visible label, not a path or UA string",
                href="https://example.test/contact",
            ))
            db.add(BotVisit(
                id=uuid.uuid4(), site_id=self.site.id, timestamp=now,
                bot_name="ClaudeBot", bot_category="ai_crawler",
                verification_state="verified", response_bytes=4096,
                page_path="/catalogue/item-1", user_agent="ClaudeBot/1.0",
                ip_hash="deadbeef",
            ))
            db.add(WalkDetectionRun(
                id=uuid.uuid4(), site_id=self.site.id,
                window_start=now - timedelta(minutes=30), window_end=now,
                verdict="suspicious", headline="Suspicious catalogue access was found.",
                score=40, triggers=["shape"], signals=["asset_fetch_absence"],
                records_taken=7, median_requests_per_address_day=3.5,
            ))
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temporary.close()

    async def test_bundle_has_no_private_strings(self):
        async with self.sessions() as db:
            walk_run = (await db.execute(select(WalkDetectionRun).where(WalkDetectionRun.site_id == self.site.id))).scalar_one()
            report = await build_report(db, self.site, walk_run=walk_run)
        offenders = [s for s in _walk_strings(report) if _looks_private(s)]
        self.assertEqual(offenders, [], f"bundle leaked private-looking strings: {offenders}")
        # And the element_text/href above never entered the bundle at all —
        # confirms the builder pulls only aggregate fields, not raw behavior rows.
        self.assertNotIn("contact", str(report))
        # The walk row's real verdict/triggers made it into the bundle, mapped
        # to Live's vocabulary — this isn't just exercising the empty-data path.
        self.assertEqual(report["walk"]["verdict"], "Suspicious")
        self.assertTrue(report["walk"]["shape_triggered"])
        self.assertTrue(report["walk"]["asset_fetch_signal"])

    async def test_watch_404s_without_key(self):
        fake_settings = type("S", (), {"live_key": "", "live_url": "https://intel.example"})()
        async with self.sessions() as db:
            with patch("routers.live.get_settings", return_value=fake_settings):
                with self.assertRaises(Exception) as ctx:
                    await live_router.watch_site(site_id=str(self.site.id), db=db, _=object())
        self.assertEqual(getattr(ctx.exception, "status_code", None), 404)

    async def test_send_report_failure_does_not_raise(self):
        with patch("services.live_client.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
            result = await live_client.send_report("https://intel.example", "k", {"site_id": "x"})
        self.assertIn("error", result)

    async def test_crawler_refresh_only_replaces_when_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "crawler_ranges.live.json"
            with patch("services.live_client._LIVE_RANGES_FILE", dest), \
                 patch("services.live_client.bot_service.reload_crawler_ranges") as mock_reload, \
                 patch(
                     "services.live_client.fetch_crawlers",
                     new=AsyncMock(return_value={"version": 3, "ranges": {"fam": ["1.2.3.0/24"]}}),
                 ):
                stale = await live_client.refresh_crawlers("https://intel.example", "k", current_version=5)
                self.assertFalse(stale.get("updated"))
                self.assertFalse(dest.exists())
                mock_reload.assert_not_called()

                fresh = await live_client.refresh_crawlers("https://intel.example", "k", current_version=1)
                self.assertTrue(fresh.get("updated"))
                self.assertEqual(fresh.get("version"), 3)
                self.assertTrue(dest.exists())
                mock_reload.assert_called_once()

    async def test_chat_context_mentions_crawler_name(self):
        async with self.sessions() as db:
            context = await _build_analytics_context(db, self.site, days=7)
        self.assertIn("ClaudeBot", context)


if __name__ == "__main__":
    unittest.main()
