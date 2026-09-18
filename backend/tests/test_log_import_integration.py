import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from database import Base  # noqa: E402
from models.bot_visit import BotVisit  # noqa: E402
from models.site import Site  # noqa: E402
from models.walk_detection import WalkDetectionRun  # noqa: E402
from routers.walk_detection import persist_detection_results  # noqa: E402
from services.log_importer import import_log_file  # noqa: E402
from services.walk_detection import analyze_windows  # noqa: E402


async def no_geo(_ip):
    return {}


class LogImportIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_combined_log_imports_classifies_and_detects(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "import.db"
            log_path = Path(directory) / "access.log"
            db_url = f"sqlite+aiosqlite:///{database_path}"
            engine = create_async_engine(db_url)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            site_id = uuid.uuid4()
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with sessions() as db:
                db.add(Site(id=site_id, domain="catalogue.example", name="Catalogue"))
                await db.commit()

            slugs = ["a", "z", "b", "y", "c", "x", "d", "w", "e", "v", "f", "u", "g", "t"]
            lines = []
            for index, slug in enumerate(slugs):
                lines.append(
                    f'198.51.100.{index + 1} - - [14/Aug/2026:12:00:{index:02d} +0000] '
                    f'"GET /catalogue/{slug} HTTP/1.1" 200 50000 "-" "Mozilla/5.0"\n'
                )
            lines.append(
                '203.0.113.9 - - [14/Aug/2026:12:00:20 +0000] '
                '"GET /catalogue/probe HTTP/1.1" 200 50000 "-" "Googlebot/2.1"\n'
            )
            log_path.write_text("".join(lines))

            observed = []
            with patch("services.log_importer.resolve_geo", no_geo):
                result = await import_log_file(
                    filepath=str(log_path),
                    domain="catalogue.example",
                    db_url=db_url,
                    request_observer=observed.append,
                )
            detections = analyze_windows(observed)
            stored = await persist_detection_results(db_url, site_id, detections)

            self.assertEqual(result["page_views"], 14)
            self.assertEqual(result["bot_visits"], 1)
            self.assertEqual(stored, 1)
            self.assertEqual(detections[0].verdict, "walk_detected")
            self.assertIn("shape", detections[0].triggers)
            self.assertEqual(detections[0].forged_claims, 1)
            self.assertFalse(any("198.51.100" in repr(item) for item in observed))

            async with sessions() as db:
                bot = (await db.execute(select(BotVisit))).scalar_one()
                run = (await db.execute(select(WalkDetectionRun))).scalar_one()
            self.assertEqual(bot.verification_state, "forged")
            self.assertEqual(len(bot.ip_hash), 64)
            self.assertEqual(run.records_taken, 15)
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
