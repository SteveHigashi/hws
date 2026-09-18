"""Reproducible importer benchmark; not collected as a test."""

import asyncio
from pathlib import Path
import sys
import tempfile
from time import perf_counter
import uuid
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import Base
from models.site import Site
from routers.walk_detection import persist_detection_results
from services.log_importer import import_log_file
from services.walk_detection import analyze_windows


async def no_geo(_ip):
    return {}


async def run_once(root: Path, log_path: Path, observed: bool) -> tuple[float, int, int]:
    database_path = root / ("observed.db" if observed else "core.db")
    db_url = f"sqlite+aiosqlite:///{database_path}"
    engine = create_async_engine(db_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    site_id = uuid.uuid4()
    async with sessions() as db:
        db.add(Site(id=site_id, domain="benchmark.example", name="Benchmark"))
        await db.commit()

    rows = []
    started = perf_counter()
    with patch("services.log_importer.resolve_geo", no_geo):
        result = await import_log_file(
            filepath=str(log_path),
            domain="benchmark.example",
            db_url=db_url,
            request_observer=rows.append if observed else None,
        )
    if observed:
        detections = analyze_windows(rows)
        await persist_detection_results(db_url, site_id, detections)
    elapsed = perf_counter() - started
    await engine.dispose()
    return elapsed, result["page_views"], len(rows)


async def main(count: int = 10_000) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        log_path = root / "access.log"
        lines = []
        for index in range(count):
            second = index % 60
            minute = (index // 60) % 60
            hour = (index // 3600) % 24
            ip = f"198.51.{(index // 250) % 100}.{index % 250 + 1}"
            lines.append(
                f'{ip} - - [14/Aug/2026:{hour:02d}:{minute:02d}:{second:02d} +0000] '
                f'"GET /catalogue/item-{index:05d} HTTP/1.1" 200 50000 "-" "Mozilla/5.0"\n'
            )
        log_path.write_text("".join(lines))
        core_time, page_views, _ = await run_once(root, log_path, observed=False)
        detection_time, _, observed_rows = await run_once(root, log_path, observed=True)
        overhead = (detection_time / core_time - 1) * 100 if core_time else 0
        print(f"rows={count} page_views={page_views} observed_rows={observed_rows}")
        print(f"core_seconds={core_time:.3f} core_rows_per_second={count / core_time:.0f}")
        print(f"detection_seconds={detection_time:.3f} detection_rows_per_second={count / detection_time:.0f}")
        print(f"detection_overhead_percent={overhead:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
