import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import shlex
import tempfile
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from models.pull_profile import PullProfile

from config import get_settings
from database import init_db, AsyncSessionLocal
from services.session_quality import backfill_in_background
from routers import collect, analytics, auth, setup, intelligence, admin, behavior, ai_crawlers
from routers import import_logs, geo_probes, sites, live_traffic, live, reading, passkeys
from services.live_client import load_local_live_ranges
from services.log_importer import import_log_file

# Optional layer-2 feature. The composition root is the only core file aware of
# it; removing its service/router/model files leaves the application bootable.
try:
    from routers import walk_detection as walk_detection_router
except ImportError:
    walk_detection_router = None

settings = get_settings()


SYNC_INTERVAL = 300  # seconds
logger = logging.getLogger(__name__)
SCHEDULE_DELAYS = {"hourly": timedelta(hours=1), "6h": timedelta(hours=6), "daily": timedelta(days=1)}

def profile_is_due(profile: PullProfile, now: datetime) -> bool:
    delay = SCHEDULE_DELAYS.get(profile.schedule)
    if not delay:
        return False
    if profile.last_run_at is None:
        return True
    last = profile.last_run_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= delay

async def _sync_logs():
    try:
        import asyncssh
    except ImportError:
        asyncssh = None
    for server in import_logs.KNOWN_SERVERS:
        if asyncssh is None:
            break
        if not server.get("log_path") or not server.get("host"):
            continue
        try:
            connect_kwargs, _ = import_logs._build_connect_kwargs(
                server["host"], server["port"], server["username"], server["password"], None
            )
            async with asyncssh.connect(**connect_kwargs) as conn:
                fd, tmp_path = tempfile.mkstemp(suffix=".log")
                os.close(fd)
                try:
                    async with conn.create_process(
                        f"cat {shlex.quote(server['log_path'])}", encoding=None
                    ) as proc:
                        stdout, _ = await proc.communicate()
                    with open(tmp_path, "wb") as f:
                        f.write(stdout or b"")
                    await import_log_file(
                        filepath=tmp_path, domain=server["domain"],
                        db_url=settings.database_url, log_path=server["log_path"],
                    )
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
        except Exception:
            logger.exception("Configured log import failed for %s", server.get("label"))

    async with AsyncSessionLocal() as db:
        profiles = (await db.execute(select(PullProfile).where(PullProfile.schedule != "off"))).scalars().all()
        for profile in profiles:
            if not profile_is_due(profile, datetime.now(timezone.utc)):
                continue
            try:
                paths = json.loads(profile.log_paths or "[]")
                if not isinstance(paths, list):
                    raise ValueError("Expected a list of log paths")
            except (TypeError, ValueError):
                logger.exception("Invalid saved log paths for %s", profile.label)
                continue
            if not paths or not profile.domain:
                continue
            succeeded = True
            for path in paths:
                tmp_path = key_path = None
                try:
                    if profile.host:
                        if asyncssh is None:
                            raise RuntimeError("asyncssh is required for remote imports")
                        credentials = import_logs.SSHCredentials(profile_id=profile.id)
                        host, port, username, password, private_key = await import_logs._resolve_credentials(credentials)
                        kwargs, key_path = import_logs._build_connect_kwargs(host, port, username, password, private_key)
                        async with asyncssh.connect(**kwargs) as conn:
                            suffix = ".log.gz" if path.endswith(".gz") else ".log"
                            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                            os.close(fd)
                            try:
                                async with conn.start_sftp_client() as sftp:
                                    await sftp.get(path, tmp_path)
                            except Exception:
                                async with conn.create_process(f"cat {shlex.quote(path)}", encoding=None) as proc:
                                    stdout, stderr = await proc.communicate()
                                if proc.exit_status != 0:
                                    raise RuntimeError((stderr or b"").decode(errors="replace"))
                                with open(tmp_path, "wb") as output:
                                    output.write(stdout or b"")
                        filepath = tmp_path
                    else:
                        filepath = path
                    await import_log_file(filepath=filepath, domain=profile.domain, db_url=settings.database_url, log_path=path)
                except Exception:
                    succeeded = False
                    logger.exception("Scheduled import failed for %s: %s", profile.label, path)
                finally:
                    for temporary in (tmp_path, key_path):
                        if temporary:
                            try:
                                os.unlink(temporary)
                            except OSError:
                                pass
            if succeeded:
                profile.last_run_at = datetime.now(timezone.utc)
                await db.commit()

async def _sync_loop():
    await asyncio.sleep(10)  # initial delay so DB is ready
    while True:
        await _sync_logs()
        await asyncio.sleep(SYNC_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    load_local_live_ranges()
    # Pulls each KNOWN_SERVERS access log over SSH every SYNC_INTERVAL and
    # imports it. Lived only on the cloudanalyst install until 2026-09-18; it
    # is what fills pageviews for sites whose browser beacon never arrives.
    task = asyncio.create_task(_sync_loop())
    # Sessions written before m004 carry no stored verdict; classify them once, in the
    # background, newest first. Restart-safe: it resumes wherever it stopped.
    backfill_task = asyncio.create_task(backfill_in_background(AsyncSessionLocal))
    yield
    task.cancel()
    backfill_task.cancel()


app = FastAPI(
    title="HWS",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # An explicit list, never "*": the tracker posts with navigator.sendBeacon,
    # which always sends credentials, and a browser refuses a wildcard on a
    # credentialed request. With "*" every cross-site pageview and behaviour
    # batch from viabandwidth was blocked at preflight (found 2026-09-18). The
    # cloudanalyst origins are listed so the dashboard keeps working if it is
    # ever served from a sibling host; same-origin calls never needed this.
    allow_origins=[
        "https://viabandwidth.com", "https://www.viabandwidth.com",
        "https://gpu.viabandwidth.com", "https://colo.viabandwidth.com",
        "https://carrier.viabandwidth.com", "https://bandwidth.viabandwidth.com",
        "https://dc.viabandwidth.com", "https://ip.viabandwidth.com",
        "https://msp.viabandwidth.com",
        "https://cloudanalyst.net", "https://www.cloudanalyst.net",
        "https://analytics.cloudanalyst.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(collect.router, prefix="/api/collect", tags=["collect"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(setup.router, prefix="/api/setup", tags=["setup"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(behavior.router, prefix="/api/behavior", tags=["behavior"])
app.include_router(ai_crawlers.router, prefix="/api/ai-crawlers", tags=["ai-crawlers"])
app.include_router(import_logs.router, prefix="/api/admin/import", tags=["import"])
app.include_router(geo_probes.router, prefix="/api/geo-probes", tags=["geo-probes"])
app.include_router(sites.router, prefix="/api/sites", tags=["sites"])
app.include_router(live_traffic.router, prefix="/api/live-traffic", tags=["live-traffic"])
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(reading.router, prefix="/api/reading", tags=["reading"])
app.include_router(passkeys.router, prefix="/api/auth/passkeys", tags=["auth"])
if walk_detection_router is not None:
    app.include_router(
        walk_detection_router.router,
        prefix="/api/walk-detection",
        tags=["walk-detection"],
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.app_version, "first_run": settings.first_run}


# Serve tracker.js publicly — no auth, must be loadable by any website
def _resolve_tracker_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "tracker" / "tracker.js"
    return Path(__file__).parent.parent / "tracker" / "tracker.js"

_tracker_path = _resolve_tracker_path()

@app.get("/tracker.js", include_in_schema=False)
async def serve_tracker():
    return FileResponse(
        _tracker_path,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# Serve the bundled React dashboard (sidecar mode only — skipped in dev if dist/ absent)
def _resolve_frontend_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend"
    return Path(__file__).parent.parent / "frontend" / "dist"

_frontend_path = _resolve_frontend_path()

if _frontend_path.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_path / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        return FileResponse(_frontend_path / "index.html")
