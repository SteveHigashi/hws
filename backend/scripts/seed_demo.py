#!/usr/bin/env python3
"""Fill a throwaway database with invented traffic, for screenshots and demos.

Nothing here is real. The site is example.com, the visitors are generated, and the
crawler counts are made up — chosen to look like a small publisher's month rather
than to flatter the product. Run it against a scratch database, never a live one:

    DATABASE_URL=sqlite+aiosqlite:///./demo.db python scripts/seed_demo.py

It refuses to touch a database that already holds data.
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402

from database import AsyncSessionLocal, init_db  # noqa: E402
from models.bot_visit import BotVisit  # noqa: E402
from models.event import Event  # noqa: E402
from models.session import Session  # noqa: E402
from models.site import Site  # noqa: E402

random.seed(20260924)  # same picture every run

DAYS = 30
PAGES = [
    ("/", "Home"),
    ("/catalogue", "Catalogue"),
    ("/catalogue/kingfisher", "Kingfisher — Catalogue"),
    ("/catalogue/heron", "Heron — Catalogue"),
    ("/about", "About"),
    ("/pricing", "Pricing"),
    ("/writing/why-crawlers-lie", "Why crawlers lie"),
]
COUNTRIES = ["GB", "US", "DE", "FR", "CA", "NL", "IE", "AU"]
DEVICES = ["desktop", "mobile", "tablet"]
BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
REFERRERS = [None, "https://www.google.com/", "https://news.ycombinator.com/",
             "https://duckduckgo.com/", "https://chat.openai.com/"]

# name, category, verification, requests, distinct pages
CRAWLERS = [
    ("GPTBot",        "ai_crawler",     "unverified", 4120, 690),
    ("ClaudeBot",     "ai_crawler",     "unverified", 2870, 612),
    ("Googlebot",     "seo_crawler",    "verified",   1940, 540),
    ("Bingbot",       "seo_crawler",    "forged",      880, 301),
    ("PerplexityBot", "ai_crawler",     "unverified",  640, 188),
    ("AhrefsBot",     "seo_crawler",    "unverified",  510, 160),
    ("Applebot",      "seo_crawler",    "verified",    310, 122),
    ("CCBot",         "ai_crawler",     "unverified",  260,  97),
    ("generic-bot",   "generic_bot",    "unverified",  180,  74),
]


async def main() -> int:
    await init_db()
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(func.count()).select_from(Site))).scalar_one()
        if existing:
            print("This database already has data. Point DATABASE_URL at a scratch file.",
                  file=sys.stderr)
            return 1

        site_id = uuid.uuid4()
        db.add(Site(id=site_id, domain="example.com", name="Example",
                    timezone="Europe/London", tracker_key=uuid.uuid4().hex, active=True))

        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start = now - timedelta(days=DAYS)

        # ── people ────────────────────────────────────────────────────────────
        sessions = events = 0
        for day in range(DAYS):
            midnight = start + timedelta(days=day)
            weekday = midnight.weekday()
            # weekends quieter, one modest spike in the third week
            base = 38 if weekday < 5 else 22
            if 14 <= day <= 16:
                base = int(base * 1.7)
            for _ in range(base + random.randint(-6, 6)):
                sid = uuid.uuid4().hex
                started = midnight + timedelta(hours=random.randint(6, 22),
                                               minutes=random.randint(0, 59))
                depth = random.choices([1, 2, 3, 4, 6], weights=[42, 24, 16, 12, 6])[0]
                dur = depth * random.randint(18, 95)
                verified = random.random() < 0.63
                country = random.choices(COUNTRIES, weights=[30, 24, 9, 8, 7, 6, 4, 3])[0]
                device = random.choices(DEVICES, weights=[58, 36, 6])[0]
                ref = random.choice(REFERRERS)
                entry, _ = random.choice(PAGES)

                db.add(Session(
                    id=sid, site_id=site_id, started_at=started,
                    last_seen_at=started + timedelta(seconds=dur),
                    entry_page=entry, exit_page=random.choice(PAGES)[0],
                    page_count=depth, duration_seconds=dur, is_bounce=depth == 1,
                    is_returning=random.random() < 0.28, country=country,
                    device_type=device,
                    referrer_domain=(ref.split("/")[2] if ref else None),
                    traffic_class="verified_human" if verified else "likely_human",
                    quality_confidence=round(random.uniform(0.72, 0.99), 2),
                    quality_reasons="browser signals" if verified else "clean navigation",
                    quality_at=started,
                ))
                sessions += 1

                for hop in range(depth):
                    path, title = random.choice(PAGES)
                    db.add(Event(
                        id=uuid.uuid4(), site_id=site_id, session_id=sid,
                        timestamp=started + timedelta(seconds=hop * random.randint(15, 80)),
                        page_url=f"https://example.com{path}", page_title=title,
                        referrer=ref if hop == 0 else None,
                        ip_hash=uuid.uuid4().hex, country=country, device_type=device,
                        browser=random.choice(BROWSERS), os="macOS" if device == "desktop" else "iOS",
                        duration_seconds=random.randint(12, 180),
                        scroll_depth=random.randint(20, 100), is_bot=False, is_unique=hop == 0,
                    ))
                    events += 1

            # a few sessions that behaved like scanners
            for _ in range(random.randint(0, 3)):
                sid = uuid.uuid4().hex
                started = midnight + timedelta(hours=random.randint(0, 23))
                db.add(Session(
                    id=sid, site_id=site_id, started_at=started,
                    last_seen_at=started + timedelta(seconds=4),
                    entry_page="/wp-login.php", exit_page="/.env", page_count=9,
                    duration_seconds=4, is_bounce=False, is_returning=False,
                    country=random.choice(["RU", "CN", "US"]), device_type="desktop",
                    traffic_class="suspicious", quality_confidence=0.94,
                    quality_reasons="scanner paths, no browser signals", quality_at=started,
                ))
                sessions += 1

        # ── machines ──────────────────────────────────────────────────────────
        visits = 0
        for name, category, state, total, uniq in CRAWLERS:
            paths = [f"/catalogue/item-{i}" for i in range(uniq)]
            for i in range(total):
                ts = start + timedelta(seconds=random.randint(0, DAYS * 86400))
                db.add(BotVisit(
                    id=uuid.uuid4(), site_id=site_id, timestamp=ts,
                    page_path=random.choice(paths), bot_name=name, bot_category=category,
                    country=random.choice(["US", "GB", "DE"]),
                    user_agent=f"Mozilla/5.0 (compatible; {name}/1.0)",
                    verification_state=state,
                    verification_method="reverse-dns" if state != "unverified" else None,
                    http_status=200, response_bytes=random.randint(9000, 82000),
                ))
                visits += 1
                if visits % 2000 == 0:
                    await db.flush()

        await db.commit()
        print(f"  site: example.com")
        print(f"  {sessions:,} sessions, {events:,} page views, {visits:,} crawler requests")
        print(f"  window: {start:%Y-%m-%d} to {now:%Y-%m-%d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
