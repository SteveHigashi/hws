import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from database import Base  # noqa: E402
from models.site import Site  # noqa: E402
from models.walk_detection import WalkDetectionRun  # noqa: E402
from routers.walk_detection import detection_runs, walk_overview  # noqa: E402


class WalkRouterIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.NamedTemporaryFile(suffix=".db")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.temporary.name}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.site_a = Site(id=uuid.uuid4(), domain="a.example", name="A")
        self.site_b = Site(id=uuid.uuid4(), domain="b.example", name="B")
        now = datetime.now(timezone.utc)
        async with self.sessions() as db:
            db.add_all([self.site_a, self.site_b])
            db.add_all([
                WalkDetectionRun(
                    site_id=self.site_a.id, window_start=now - timedelta(minutes=30), window_end=now,
                    verdict="walk_detected", headline="A only", score=80, triggers=["shape"], signals=[], records_taken=12,
                ),
                WalkDetectionRun(
                    site_id=self.site_b.id, window_start=now - timedelta(minutes=30), window_end=now,
                    verdict="walk_detected", headline="B only", score=95, triggers=["order"], signals=[], records_taken=999,
                ),
            ])
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temporary.close()

    async def test_site_a_cannot_read_site_b_detection(self):
        async with self.sessions() as db:
            overview = await walk_overview(site_id=str(self.site_a.id), days=30, db=db, _=object())
            runs = await detection_runs(site_id=str(self.site_a.id), days=30, limit=100, db=db, _=object())
        self.assertEqual(overview["records_taken"], 12)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["headline"], "A only")
        self.assertNotEqual(runs[0]["records_taken"], 999)


if __name__ == "__main__":
    unittest.main()
