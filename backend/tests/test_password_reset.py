"""A reset link works once, for 30 minutes, and only the hash is stored.

Remove the used_at or expiry check in consume_reset_token and a test here fails.
"""
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from database import Base  # noqa: E402
from models.password_reset import PasswordReset  # noqa: E402
from models.user import User, UserRole  # noqa: E402
from services.password_reset import consume_reset_token, hash_reset_token, issue_reset_token  # noqa: E402


class ResetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{Path(self.tmp.name) / 'r.db'}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            db.add(User(id=uuid.uuid4(), email="o@example.test", password_hash="x", role=UserRole.admin))
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def test_only_the_hash_is_stored_and_the_token_works_once(self):
        async with self.sessions() as db:
            raw = await issue_reset_token(db, "o@example.test")
            self.assertTrue(raw and len(raw) >= 40)
            rows = (await db.execute(select(PasswordReset))).scalars().all()
            self.assertEqual(rows[0].token_hash, hash_reset_token(raw))
            self.assertNotIn(raw, rows[0].token_hash)
            user = await consume_reset_token(db, raw)
            await db.commit()
            self.assertEqual(user.email, "o@example.test")
            self.assertIsNone(await consume_reset_token(db, raw))  # second use refused

    async def test_expired_token_is_refused(self):
        async with self.sessions() as db:
            raw = await issue_reset_token(db, "o@example.test")
            row = (await db.execute(select(PasswordReset))).scalars().first()
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await db.commit()
            self.assertIsNone(await consume_reset_token(db, raw))

    async def test_unknown_email_and_garbage_token(self):
        async with self.sessions() as db:
            self.assertIsNone(await issue_reset_token(db, "nobody@example.test"))
            self.assertIsNone(await consume_reset_token(db, "not-a-token"))
            self.assertIsNone(await consume_reset_token(db, ""))


class BaseUrlTests(unittest.TestCase):
    """The printed link must point at the dashboard, not at a site being tracked.

    site_domain is whatever domain the operator added during setup (on the walk box:
    stevenhigashi.com). A reset link built from it hands a live token to an unrelated
    host. Make _base_url prefer site_domain again and these fail.
    """

    def _base_url(self, override=None, **settings):
        import manage_users
        from types import SimpleNamespace
        real = manage_users.__dict__.get("get_settings")
        import config
        original = config.get_settings
        config.get_settings = lambda: SimpleNamespace(**settings)
        try:
            return manage_users._base_url(override)
        finally:
            config.get_settings = original
            if real is not None:
                manage_users.get_settings = real

    def test_explicit_override_wins(self):
        self.assertEqual(
            self._base_url("https://higashi.jotnotes.com/", dashboard_url="", site_domain="stevenhigashi.com"),
            "https://higashi.jotnotes.com",
        )

    def test_dashboard_url_beats_site_domain(self):
        self.assertEqual(
            self._base_url(None, dashboard_url="https://higashi.jotnotes.com", site_domain="stevenhigashi.com"),
            "https://higashi.jotnotes.com",
        )

    def test_bare_host_gets_https(self):
        self.assertEqual(
            self._base_url(None, dashboard_url="higashi.jotnotes.com", site_domain=""),
            "https://higashi.jotnotes.com",
        )

    def test_falls_back_to_loopback_when_nothing_is_set(self):
        self.assertEqual(self._base_url(None, dashboard_url="", site_domain=""), "http://127.0.0.1:8003")


if __name__ == "__main__":
    unittest.main()
