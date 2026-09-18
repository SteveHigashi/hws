"""HTTP client for Higashi Live. Never raises into a request handler —
every function returns a plain dict, with an "error" key on failure so the
caller (a route handler or a cron script) can show it rather than crash."""
import json
import os
import tempfile
from pathlib import Path

import httpx

from services import bot as bot_service

_TIMEOUT = 10.0
_LIVE_RANGES_FILE = bot_service._DEFAULT_RANGE_FILE.parent / "crawler_ranges.live.json"


async def send_report(live_url: str, live_key: str, report: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{live_url.rstrip('/')}/v1/report",
                json=report,
                headers={"X-Live-Key": live_key},
            )
        if resp.status_code >= 400:
            return {"error": f"Live returned {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


async def latest_reading(live_url: str, live_key: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{live_url.rstrip('/')}/v1/reading/latest",
                headers={"X-Live-Key": live_key},
            )
        if resp.status_code >= 400:
            return {"error": f"Live returned {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


async def fetch_crawlers(live_url: str, live_key: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{live_url.rstrip('/')}/v1/crawlers",
                headers={"X-Live-Key": live_key},
            )
        if resp.status_code >= 400:
            return {"error": f"Live returned {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


def write_live_ranges(ranges: dict, destination: Path | None = None) -> None:
    """Atomically write the family->prefix mapping beside the bundled file.

    Never touches the bundled data/crawler_ranges.json shipped in the repo.
    """
    destination = destination or _LIVE_RANGES_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".crawler-ranges-live.", dir=destination.parent)
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(ranges, stream, indent=1, sort_keys=True)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def refresh_crawlers(live_url: str, live_key: str, current_version: int) -> dict:
    """Fetch the current crawler list from Live and replace the local copy
    only if it's newer than what we already applied. Returns a status dict;
    never raises."""
    payload = await fetch_crawlers(live_url, live_key)
    if "error" in payload:
        return payload

    version = payload.get("version")
    ranges = payload.get("ranges")
    if not isinstance(version, int) or not isinstance(ranges, dict):
        return {"error": "Live returned an unexpected /v1/crawlers payload"}
    if version <= current_version:
        return {"updated": False, "version": current_version}

    write_live_ranges(ranges)
    bot_service.reload_crawler_ranges(str(_LIVE_RANGES_FILE))
    return {"updated": True, "version": version}


def load_local_live_ranges() -> bool:
    """Point bot.py at a previously-fetched Live ranges file, if one exists.
    Local-disk only — makes no outbound request. Meant for app startup."""
    if _LIVE_RANGES_FILE.exists():
        bot_service.reload_crawler_ranges(str(_LIVE_RANGES_FILE))
        return True
    return False
