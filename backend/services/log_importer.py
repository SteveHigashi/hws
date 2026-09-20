"""
Core nginx log parsing and DB insertion logic.
Shared by the CLI script (backend/scripts/import_logs.py) and the import router.
"""

import gzip
import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from urllib.parse import urlparse, parse_qs

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from models.event import Event
from models.import_cursor import ImportCursor
from models.session import Session
from services.session_quality import classify_sessions
from models.site import Site
from models.bot_visit import BotVisit
from services.bot import classify_bot
from services.geo import resolve_geo

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATIC_EXT = re.compile(
    r"\.(css|js|ico|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot|map|webp|avif|mp4|webm|pdf|zip|gz|xml|txt|json)$",
    re.IGNORECASE,
)

_LOG_RE = re.compile(
    r'(?:(\S+) )?'             # optional vhost prefix
    r'(\S+) \S+ \S+ '          # remote_addr
    r'\[([^\]]+)\] '           # time_local
    r'"(\S+) (\S+)[^"]*" '    # method + path
    r'(\d+) (\d+|-) '          # status + bytes
    r'"([^"]*)" '              # referrer
    r'"([^"]*)"'               # user_agent
)

_TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"

SESSION_TIMEOUT = timedelta(minutes=30)
BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> Optional[str]:
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def _extract_search_query(referrer: Optional[str]) -> Optional[str]:
    if not referrer:
        return None
    try:
        params = parse_qs(urlparse(referrer).query)
        for key in ("q", "p", "query"):
            if key in params:
                return params[key][0][:512]
    except Exception:
        pass
    return None


def _ip_hash(ip: str, site_id) -> str:
    return hashlib.sha256(f"{ip}{site_id}".encode()).hexdigest()


def _session_row(s: Session) -> dict:
    """Convert a Session ORM object to a plain dict for bulk Core insert."""
    return {k: v for k, v in vars(s).items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def import_log_file(
    filepath: str,
    domain: str,
    db_url: str,
    log_path: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    request_observer: Optional[Callable[[dict], None]] = None,
) -> dict:
    """
    Parse *filepath* (nginx combined format) and insert records into the DB.

    request_observer receives privacy-safe parsed request facts, including a
    site-salted identity but never the raw address. It is the clean seam used by
    optional after-the-fact analysis; core does not import any detector.

    log_path — remote server path used as the cursor key. When provided,
    lines at or before the last cursor timestamp are skipped, enabling
    incremental imports. The cursor is advanced after a successful run.

    Returns:
        {
            "page_views":       int,
            "sessions":         int,
            "bot_visits":       int,
            "skipped":          int,
            "errors":           int,
            "cursor_from":      ISO str | null  (previous cursor)
            "cursor_to":        ISO str | null  (new cursor after this run)
        }
    """
    engine = create_async_engine(db_url, echo=False)
    Session_ = async_sessionmaker(engine, expire_on_commit=False)

    # --- resolve site ---
    async with Session_() as db:
        result = await db.execute(select(Site).where(Site.domain == domain))
        site = result.scalar_one_or_none()
        if not site:
            await engine.dispose()
            raise ValueError(f"No site found with domain '{domain}'.")
        site_id = site.id
        site_id_str = str(site_id)

    # --- load cursor ---
    cursor_obj: Optional[ImportCursor] = None
    cursor_ts: Optional[datetime] = None
    if log_path:
        async with Session_() as db:
            result = await db.execute(
                select(ImportCursor).where(
                    ImportCursor.site_id == site_id_str,
                    ImportCursor.log_path == log_path,
                )
            )
            cursor_obj = result.scalar_one_or_none()
            if cursor_obj:
                ct = cursor_obj.last_line_at
                # SQLite returns naive datetimes — normalize to UTC-aware
                cursor_ts = ct if ct.tzinfo else ct.replace(tzinfo=timezone.utc)

    # --- per-call geo cache ---
    geo_cache: dict[str, dict] = {}

    async def _geo(ip: str) -> dict:
        if ip not in geo_cache:
            geo_cache[ip] = await resolve_geo(ip)
        return geo_cache[ip]

    # --- accumulators ---
    session_map: dict[str, dict] = {}
    new_sessions: dict[str, Session] = {}
    new_events: list[Event] = []
    new_bot_visits: list[BotVisit] = []

    page_views = 0
    bot_count = 0
    skipped = 0
    errors = 0
    max_ts: Optional[datetime] = None

    async def _flush(db: AsyncSession) -> None:
        if new_sessions:
            # INSERT OR IGNORE: silently skip any session that already exists
            # (safety net for overlap window or crash recovery)
            await db.execute(
                sqlite_insert(Session.__table__).on_conflict_do_nothing(),
                [_session_row(s) for s in new_sessions.values()],
            )
        for e in new_events:
            db.add(e)
        for b in new_bot_visits:
            db.add(b)
        await db.commit()
        # Verdict per session, stored on the row (m004). A session that spans two
        # flushes is simply classified twice; the second pass sees all its events.
        touched = {e.session_id for e in new_events}
        if touched:
            await classify_sessions(db, touched)
            await db.commit()
        new_sessions.clear()
        new_events.clear()
        new_bot_visits.clear()

    # --- read lines (transparently handle gzipped rotated logs) ---
    opener = gzip.open if filepath.endswith(".gz") else open
    with opener(filepath, "rt", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)

    async with Session_() as db:
        for i, line in enumerate(lines):
            if progress_callback is not None:
                progress_callback(i + 1, total)

            m = _LOG_RE.match(line.strip())
            if not m:
                errors += 1
                continue

            _, ip, time_str, method, path, status_str, bytes_str, referrer, ua = m.groups()

            if method not in ("GET", "HEAD"):
                skipped += 1
                continue

            try:
                ts = datetime.strptime(time_str, _TIME_FMT).astimezone(timezone.utc)
            except ValueError:
                errors += 1
                continue

            # --- cursor check: skip lines already imported ---
            if cursor_ts is not None and ts <= cursor_ts:
                skipped += 1
                continue

            if max_ts is None or ts > max_ts:
                max_ts = ts

            referrer = referrer if referrer != "-" else None
            ua = ua if ua != "-" else ""
            ip_hash = _ip_hash(ip, site_id)
            path_only = path.split("?", 1)[0]
            status = int(status_str)
            response_bytes = int(bytes_str) if bytes_str.isdigit() else 0

            # Network verification must happen here while the raw address is
            # still in memory. Only the verdict and salted identity persist.
            bot = classify_bot(ua, ip)

            if request_observer is not None:
                request_observer({
                    "timestamp": ts,
                    "identity": ip_hash,
                    "method": method,
                    "path": path_only,
                    "status": status,
                    "response_bytes": response_bytes,
                    "content_type": None,  # combined logs omit it; detectors also infer by path
                    "referrer": referrer,
                    "user_agent": ua,
                    "bot_name": bot["name"] if bot else None,
                    "bot_verification": bot["verification_state"] if bot else None,
                })

            if _STATIC_EXT.search(path_only):
                skipped += 1
                continue

            if status not in (200, 301, 302, 304, 404):
                skipped += 1
                continue

            # --- bot routing ---
            if bot:
                bot_count += 1
                new_bot_visits.append(BotVisit(
                    site_id=site_id,
                    timestamp=ts,
                    page_path=path_only[:2048],
                    bot_name=bot["name"],
                    bot_category=bot["category"],
                    country=None,
                    user_agent=ua[:1024],
                    verification_state=bot["verification_state"],
                    verification_method=bot["verification_method"],
                    ip_hash=ip_hash,
                    http_status=status,
                    response_bytes=response_bytes,
                    referrer=referrer,
                ))
                if len(new_bot_visits) >= BATCH_SIZE:
                    await _flush(db)
                continue

            geo = await _geo(ip)

            # --- UA parsing ---
            try:
                from user_agents import parse as parse_ua
                parsed_ua = parse_ua(ua)
                browser = parsed_ua.browser.family
                browser_version = parsed_ua.browser.version_string
                os_name = parsed_ua.os.family
                device_type = (
                    "mobile" if parsed_ua.is_mobile
                    else "tablet" if parsed_ua.is_tablet
                    else "desktop"
                )
            except Exception:
                browser = browser_version = os_name = device_type = None

            # --- session management ---
            sess_state = session_map.get(ip_hash)
            if sess_state and (ts - sess_state["last_seen"]) <= SESSION_TIMEOUT:
                sess_id = sess_state["id"]
                sess_state["last_seen"] = ts
                sess_state["page_count"] += 1
                sess_state["exit_page"] = path
                if sess_id in new_sessions:
                    s = new_sessions[sess_id]
                    s.page_count = sess_state["page_count"]
                    s.exit_page = path
                    s.last_seen_at = ts
                    s.is_bounce = sess_state["page_count"] < 2
            else:
                sess_id = hashlib.sha256(
                    f"{ip_hash}{ts.isoformat()}".encode()
                ).hexdigest()[:64]
                sess_state = {
                    "id": sess_id,
                    "last_seen": ts,
                    "entry_page": path,
                    "exit_page": path,
                    "page_count": 1,
                    "country": geo.get("country"),
                    "device_type": device_type,
                    "referrer_domain": _extract_domain(referrer),
                }
                session_map[ip_hash] = sess_state
                new_sessions[sess_id] = Session(
                    id=sess_id,
                    site_id=site_id,
                    started_at=ts,
                    last_seen_at=ts,
                    entry_page=path[:1024],
                    exit_page=path[:1024],
                    page_count=1,
                    is_bounce=True,
                    country=geo.get("country"),
                    device_type=device_type,
                    referrer_domain=_extract_domain(referrer),
                )

            page_url = f"https://{domain}{path}"
            new_events.append(Event(
                site_id=site_id,
                session_id=sess_id,
                timestamp=ts,
                page_url=page_url,
                referrer=referrer,
                ip_hash=ip_hash,
                country=geo.get("country"),
                region=geo.get("region"),
                city=geo.get("city"),
                asn=geo.get("asn"),
                timezone=geo.get("timezone"),
                browser=browser,
                browser_version=browser_version,
                os=os_name,
                device_type=device_type,
                user_agent=ua,
                is_bot=False,
                is_404=(status == 404),
                search_query=_extract_search_query(referrer),
            ))
            page_views += 1

            if len(new_events) >= BATCH_SIZE:
                await _flush(db)

        # final flush
        if new_events or new_sessions or new_bot_visits:
            await _flush(db)

    # --- advance cursor ---
    if log_path and max_ts is not None:
        prev_total = cursor_obj.total_imported if cursor_obj else 0
        async with Session_() as db:
            await db.execute(
                sqlite_insert(ImportCursor).values(
                    id=cursor_obj.id if cursor_obj else str(uuid.uuid4()),
                    site_id=site_id_str,
                    log_path=log_path,
                    last_line_at=max_ts,
                    last_run_at=datetime.now(timezone.utc),
                    total_imported=prev_total + page_views,
                ).on_conflict_do_update(
                    index_elements=["site_id", "log_path"],
                    set_={
                        "last_line_at": max_ts,
                        "last_run_at": datetime.now(timezone.utc),
                        "total_imported": prev_total + page_views,
                    },
                )
            )
            await db.commit()

    await engine.dispose()

    return {
        "site_id": str(site_id),
        "page_views": page_views,
        "sessions": len(session_map),
        "bot_visits": bot_count,
        "skipped": skipped,
        "errors": errors,
        "cursor_from": cursor_ts.isoformat() if cursor_ts else None,
        "cursor_to": max_ts.isoformat() if max_ts else None,
    }
