#!/usr/bin/env python3
"""
Pull the current crawler range list from Higashi Live and replace the local
copy only if it's newer — run via cron. This is the only step of the Live
integration that reaches out on a schedule; app startup only ever reads
whatever range file already sits on disk.

No-op if no Live key is configured. Never touches the bundled
data/crawler_ranges.json shipped in the repo — writes crawler_ranges.live.json
beside it instead.

Cron example (weekly, Monday 05:00):
    0 5 * * 1 /path/to/venv/bin/python /app/scripts/live_refresh_crawlers.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_settings
from services.live_client import refresh_crawlers


async def run():
    settings = get_settings()
    if not settings.live_key:
        print("[live_refresh_crawlers] No Live key configured. Nothing to do.")
        return

    result = await refresh_crawlers(settings.live_url, settings.live_key, settings.live_crawler_version)
    if "error" in result:
        print(f"[live_refresh_crawlers] Failed: {result['error']}")
        return
    if not result.get("updated"):
        print(f"[live_refresh_crawlers] Already current (version {result.get('version')}).")
        return

    try:
        from dotenv import set_key as dotenv_set_key
        env_path = os.environ.get("HIGASHI_ENV_PATH", os.path.join(os.path.dirname(__file__), "..", ".env"))
        dotenv_set_key(env_path, "LIVE_CRAWLER_VERSION", str(result["version"]))
    except Exception as e:
        print(f"[live_refresh_crawlers] Wrote ranges but could not persist version to .env: {e}")
        return

    print(f"[live_refresh_crawlers] Updated to version {result['version']}.")


if __name__ == "__main__":
    asyncio.run(run())
