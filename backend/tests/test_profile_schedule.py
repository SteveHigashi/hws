import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker  # noqa: E402
from database import Base  # noqa: E402
from main import profile_is_due  # noqa: E402
from migrations.m008_profile_schedule import upgrade  # noqa: E402
from models.pull_profile import PullProfile  # noqa: E402
from routers import import_logs  # noqa: E402


class ProfileScheduleTests(unittest.TestCase):
    def test_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = create_engine(f"sqlite:///{Path(temporary) / 'legacy.db'}")
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE pull_profiles (id VARCHAR(36) PRIMARY KEY)"))
                upgrade(connection)
                upgrade(connection)
                columns = {item["name"] for item in inspect(connection).get_columns("pull_profiles")}
                self.assertIn("schedule", columns)
                self.assertIn("last_run_at", columns)
                connection.execute(text("INSERT INTO pull_profiles (id) VALUES ('one')"))
                self.assertEqual(connection.execute(text("SELECT schedule FROM pull_profiles")).scalar(), "off")

    def test_due_check(self):
        now = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
        profile = PullProfile(schedule="hourly", last_run_at=now - timedelta(minutes=61))
        self.assertTrue(profile_is_due(profile, now))
        profile.last_run_at = now - timedelta(minutes=30)
        self.assertFalse(profile_is_due(profile, now))
        profile.schedule = "off"
        profile.last_run_at = now - timedelta(days=10)
        self.assertFalse(profile_is_due(profile, now))
        profile.schedule = "6h"
        profile.last_run_at = None
        self.assertTrue(profile_is_due(profile, now))


class ProfileApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_schedule_survives_save_and_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = create_async_engine(f"sqlite+aiosqlite:///{Path(temporary) / 'profiles.db'}")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            with patch.object(import_logs, "AsyncSessionLocal", session_factory):
                saved = await import_logs.save_profile(import_logs.PullProfileRequest(
                    label="On this server: example.com", host="", username="",
                    auth_mode="local", domain="example.com",
                    log_paths=["/var/log/nginx/access.log"], schedule="6h",
                ))
                listed = await import_logs.list_profiles()
                self.assertEqual(saved["schedule"], "6h")
                self.assertEqual(listed[0]["schedule"], "6h")
                self.assertEqual(listed[0]["log_paths"], ["/var/log/nginx/access.log"])
            await engine.dispose()
