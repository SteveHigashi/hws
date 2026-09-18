"""
Import nginx/apache access logs into Higashi Analytics.

Usage:
    python scripts/import_logs.py <logfile> <site_domain>

Example:
    python scripts/import_logs.py /var/log/nginx/access.log stevenhigashi.com

Supports standard combined log format:
    $remote_addr - $remote_user [$time_local] "$request" $status $bytes "$referrer" "$ua"

Also supports combined log with vhost prefix:
    $host $remote_addr - $remote_user [$time_local] "$request" $status $bytes "$referrer" "$ua"
"""

import asyncio
import hashlib
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse, parse_qs

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

sys.path.insert(0, ".")
from config import get_settings
from models.event import Event
from models.session import Session
from models.site import Site
from models.bot_visit import BotVisit
from services.bot import is_bot_request, classify_bot
from services.geo import resolve_geo

# Skip requests for static assets — these are not page views
_STATIC_EXT = re.compile(
    r"\.(css|js|ico|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot|map|webp|avif|mp4|webm|pdf|zip|gz|xml|txt|json)$",
    re.IGNORECASE,
)

# Skip bot probe paths — scanners, WordPress probes, challenge endpoints
_BOT_PATHS = re.compile(
    r"^(/\.well-known/|/wp-|/wordpress|/wp\.php|/xmlrpc|/phpmyadmin|/admin|"
    r"/shell|/cgi-bin|/\.env|/config\.|/setup-config|/install\.php|"
    r"/readme\.html|/license\.txt|/web\.config|/etc/passwd|/proc/)",
    re.IGNORECASE,
)

# Standard nginx combined log format
_LOG_RE = re.compile(
    r'(?:(\S+) )?'                      # optional vhost prefix
    r'(\S+) \S+ \S+ '                   # remote_addr
    r'\[([^\]]+)\] '                    # time_local
    r'"(\S+) (\S+)[^"]*" '             # method + path
    r'(\d+) \d+ '                       # status + bytes
    r'"([^"]*)" '                       # referrer
    r'"([^"]*)"'                        # user_agent
)

_TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"

SESSION_TIMEOUT = timedelta(minutes=30)
GEO_CACHE: dict[str, dict] = {}
BATCH_SIZE = 500


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


async def _geo(ip: str) -> dict:
    if ip not in GEO_CACHE:
        GEO_CACHE[ip] = await resolve_geo(ip)
    return GEO_CACHE[ip]


def _ip_hash(ip: str, site_id) -> str:
    return hashlib.sha256(f"{ip}{site_id}".encode()).hexdigest()


async def run(logfile: str, domain: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    Session_ = async_sessionmaker(engine, expire_on_commit=False)

    async with Session_() as db:
        result = await db.execute(select(Site).where(Site.domain == domain))
        site = result.scalar_one_or_none()
        if not site:
            print(f"No site found with domain '{domain}'. Run setup or check the domain spelling.")
            await engine.dispose()
            return
        site_id = site.id
        print(f"Found site: {site.name} ({site.domain}) — id {site_id}")

    # session_map: ip_hash -> {id, last_seen, entry_page, page_count, referrer_domain, country, device_type, utm_*}
    session_map: dict[str, dict] = {}
    # already-seen session objects accumulated for bulk insert
    new_sessions: dict[str, Session] = {}
    new_events: list[Event] = []
    new_bot_visits: list[BotVisit] = []

    skipped = 0
    parsed = 0
    errors = 0

    async def flush(db: AsyncSession) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        if new_sessions:
            await db.execute(
                sqlite_insert(Session).prefix_with("OR IGNORE"),
                [
                    {c.key: getattr(s, c.key) for c in Session.__table__.columns}
                    for s in new_sessions.values()
                ],
            )
        if new_events:
            await db.execute(
                sqlite_insert(Event).prefix_with("OR IGNORE"),
                [
                    {c.key: getattr(e, c.key) for c in Event.__table__.columns}
                    for e in new_events
                ],
            )
        if new_bot_visits:
            for b in new_bot_visits:
                db.add(b)
        await db.commit()
        new_sessions.clear()
        new_events.clear()
        new_bot_visits.clear()

    with open(logfile, "r", errors="replace") as f:
        lines = f.readlines()

    print(f"Parsing {len(lines):,} log lines...")

    async with Session_() as db:
        for i, line in enumerate(lines):
            m = _LOG_RE.match(line.strip())
            if not m:
                errors += 1
                continue

            _, ip, time_str, method, path, status_str, referrer, ua = m.groups()

            # Only GET/HEAD page requests
            if method not in ("GET", "HEAD"):
                skipped += 1
                continue

            # Strip query string for extension check
            path_only = path.split("?")[0]
            if _STATIC_EXT.search(path_only) or _BOT_PATHS.match(path_only):
                skipped += 1
                continue

            status = int(status_str)
            if status not in (200, 301, 302, 304, 404):
                skipped += 1
                continue

            # Parse timestamp
            try:
                ts = datetime.strptime(time_str, _TIME_FMT).astimezone(timezone.utc)
            except ValueError:
                errors += 1
                continue

            parsed += 1
            referrer = referrer if referrer != "-" else None
            ua = ua if ua != "-" else ""

            ip_hash = _ip_hash(ip, site_id)

            # Bot handling
            bot = classify_bot(ua)
            if bot or is_bot_request(ua):
                new_bot_visits.append(BotVisit(
                    site_id=site_id,
                    page_path=path_only[:2048],
                    bot_name=bot["name"] if bot else "unknown",
                    bot_category=bot["category"] if bot else "generic_bot",
                    country=None,
                    user_agent=ua[:1024],
                ))
                if len(new_bot_visits) >= BATCH_SIZE:
                    async with Session_() as db:
                        await flush(db)
                continue

            geo = await _geo(ip)

            # UA parsing
            try:
                from user_agents import parse as parse_ua
                parsed_ua = parse_ua(ua)
                browser = parsed_ua.browser.family
                browser_version = parsed_ua.browser.version_string
                os_name = parsed_ua.os.family
                device_type = "mobile" if parsed_ua.is_mobile else "tablet" if parsed_ua.is_tablet else "desktop"
            except Exception:
                browser = browser_version = os_name = device_type = None

            # Session management
            sess_state = session_map.get(ip_hash)
            if sess_state and (ts - sess_state["last_seen"]) <= SESSION_TIMEOUT:
                sess_id = sess_state["id"]
                sess_state["last_seen"] = ts
                sess_state["page_count"] += 1
                sess_state["exit_page"] = path
                # Update the pending Session object if present
                if sess_id in new_sessions:
                    s = new_sessions[sess_id]
                    s.page_count = sess_state["page_count"]
                    s.exit_page = path
                    s.last_seen_at = ts
                    s.is_bounce = sess_state["page_count"] < 2
            else:
                sess_id = hashlib.sha256(f"{ip_hash}{ts.isoformat()}".encode()).hexdigest()[:64]
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

            if len(new_events) >= BATCH_SIZE:
                async with Session_() as db:
                    await flush(db)
                print(f"  flushed batch at line {i+1:,} — {parsed:,} page views so far")

        # Final flush
        if new_events or new_sessions or new_bot_visits:
            async with Session_() as db:
                await flush(db)

    await engine.dispose()
    print(f"\nDone.")
    print(f"  Page views imported : {parsed:,}")
    print(f"  Skipped (static/etc): {skipped:,}")
    print(f"  Parse errors        : {errors:,}")
    print(f"  Sessions created    : {len(session_map):,}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/import_logs.py <logfile> <site_domain>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1], sys.argv[2]))
