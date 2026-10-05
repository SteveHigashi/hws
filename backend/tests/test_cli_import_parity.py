"""The CLI importer must write the same BotVisit rows as the service importer.

scripts/import_logs.py used to carry its own copy of the parse-and-insert loop.
That copy built BotVisit rows without a timestamp, so every imported crawler
visit fell back to the column default of import time and the whole crawler
timeline collapsed onto the day of the import. It also dropped
verification_state, ip_hash, http_status, response_bytes and referrer.

These tests pin the fields that regression destroyed, and they drive the CLI
entry point rather than the service, because the service was never the thing
that was broken.
"""

import importlib.util
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from database import Base  # noqa: E402
from models.bot_visit import BotVisit  # noqa: E402
from models.site import Site  # noqa: E402


def _load_cli():
    """scripts/ is not a package, so load the CLI module by path."""
    path = BACKEND / "scripts" / "import_logs.py"
    spec = importlib.util.spec_from_file_location("hws_cli_import_logs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def no_geo(_ip):
    return {}


# One crawler line and one human line, both well before "now", so a row that
# carries the import time instead of the log time is unmistakable.
CRAWLER_LINE = (
    '66.249.66.1 - - [14/Aug/2026:09:15:42 +0000] '
    '"GET /catalogue/alpha HTTP/1.1" 200 51234 '
    '"https://www.google.com/" "Mozilla/5.0 (compatible; Googlebot/2.1; '
    '+http://www.google.com/bot.html)"\n'
)
HUMAN_LINE = (
    '198.51.100.7 - - [14/Aug/2026:09:16:03 +0000] '
    '"GET /catalogue/beta HTTP/1.1" 200 42000 "-" '
    '"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Safari/605.1.15"\n'
)

LOG_DAY = datetime(2026, 8, 14, tzinfo=timezone.utc).date()


class CliImportParityTests(unittest.IsolatedAsyncioTestCase):
    async def _import(self, directory):
        """Run the CLI entry point against a throwaway SQLite database."""
        database_path = Path(directory) / "cli_import.db"
        log_path = Path(directory) / "access.log"
        db_url = f"sqlite+aiosqlite:///{database_path}"

        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(Site(id=uuid.uuid4(), domain="catalogue.example", name="Catalogue"))
            await db.commit()

        log_path.write_text(CRAWLER_LINE + HUMAN_LINE)

        cli = _load_cli()

        class _Settings:
            database_url = db_url

        with patch.object(cli, "get_settings", lambda: _Settings()), \
                patch("services.log_importer.resolve_geo", no_geo):
            await cli.run(str(log_path), "catalogue.example")

        return engine, sessions

    async def test_bot_visit_keeps_the_timestamp_from_the_log(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, sessions = await self._import(directory)
            async with sessions() as db:
                visits = (await db.execute(select(BotVisit))).scalars().all()

            self.assertEqual(len(visits), 1, "expected exactly one crawler visit")
            visit = visits[0]

            stamp = visit.timestamp
            self.assertIsNotNone(stamp, "BotVisit.timestamp was not written")
            if stamp.tzinfo is None:  # SQLite hands back naive datetimes
                stamp = stamp.replace(tzinfo=timezone.utc)

            self.assertEqual(
                stamp.date(), LOG_DAY,
                "crawler visit did not keep the date from the log line, which is the "
                "regression that collapsed every import onto the day it was run",
            )
            self.assertEqual((stamp.hour, stamp.minute), (9, 15))
            await engine.dispose()

    async def test_bot_visit_keeps_the_evidence_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, sessions = await self._import(directory)
            async with sessions() as db:
                visit = (await db.execute(select(BotVisit))).scalars().one()

            self.assertEqual(visit.bot_name, "Googlebot")
            self.assertIsNotNone(visit.verification_state, "verification_state was dropped")
            self.assertTrue(visit.ip_hash, "ip_hash was dropped")
            self.assertNotIn("66.249.66.1", visit.ip_hash or "", "raw address must never be stored")
            self.assertEqual(visit.http_status, 200, "http_status was dropped")
            self.assertEqual(visit.response_bytes, 51234, "response_bytes was dropped")
            self.assertEqual(visit.referrer, "https://www.google.com/", "referrer was dropped")
            await engine.dispose()

    async def test_cli_does_not_reimplement_parsing(self):
        """The CLI must delegate, so the two paths cannot drift apart again."""
        source = (BACKEND / "scripts" / "import_logs.py").read_text()
        self.assertIn("from services.log_importer import import_log_file", source)
        self.assertNotIn(
            "BotVisit(", source,
            "the CLI is constructing BotVisit rows again; it must call the service instead",
        )


if __name__ == "__main__":
    unittest.main()
