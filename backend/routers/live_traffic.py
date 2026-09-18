"""
Live traffic feed — raw nginx access log, tailed and classified in real time.

WHY THIS EXISTS
The rest of the app reports on data that has already landed in the database:
`collect.py` receives beacons, `import_logs.py` ingests log files after the
fact, `ai_crawlers.py` aggregates what was seen. All of it answers "what
happened". None of it answers "what is happening right now", which is the
question you need during an incident.

On 2026-08-08 viabandwidth.com was being walked by a rented residential-proxy
pool: exactly one request per IP, no asset fetches, a forged same-site referer,
and a reverse-alphabetical march through the directory. Every individual
request looked ordinary. The attack was only visible in the SHAPE of the
stream — adjacent records arriving in order from unrelated addresses. Reading
that off a static report is close to impossible; watching it scroll is easy.

WHAT IT DOES
Tails the remote nginx access log over SSH from this machine (never runs an
agent on the web server, so it adds no attack surface there), parses each line,
and enriches it against the local ASN atlas so every row carries who owns the
address and what kind of network it is.

CLASSIFICATION IS ADVISORY, NOT AUTHORITATIVE
Two known mislabels in the atlas that matter here, both verified 2026-08-08:
AWS AS16509 is labelled `enterprise` and Google AS15169 is labelled
`commercial_dc`. So `segment` is a hint for a human reading the feed, never a
blocking signal. IPv6 coverage also has holes.
"""
import os
import re
import shutil
import subprocess
import threading
from collections import deque, OrderedDict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from routers.auth import get_current_user

router = APIRouter()

# --- configuration ---------------------------------------------------------
# Credentials never live in this file. Set them in the environment (or the
# shell that launches uvicorn). Without LIVE_TRAFFIC_HOST the feature simply
# reports itself as unconfigured rather than failing the app on import.
SSH_HOST = os.getenv("LIVE_TRAFFIC_HOST", "")
SSH_USER = os.getenv("LIVE_TRAFFIC_USER", "root")
SSH_PASS = os.getenv("LIVE_TRAFFIC_PASS", "")
LOG_PATH = os.getenv("LIVE_TRAFFIC_LOG", "/var/log/nginx/access.log")
ATLAS_DSN = os.getenv("LIVE_TRAFFIC_ATLAS_DSN", "dbname=operation_dc_net")

# Remote mode. When set, this router forwards to a log-feed service running on
# the monitored server instead of tailing over SSH, and does no parsing itself.
#
# That is the only shape that works for a deployed dashboard: SSH mode needs the
# monitored box's root credentials, which must never sit on a shared host that
# also serves a public site. The bearer token below grants log reads and nothing
# else, so a compromise of the dashboard host cannot become a compromise of the
# web server. Remote mode wins when both are configured.
FEED_URL = os.getenv("LIVE_TRAFFIC_FEED_URL", "").rstrip("/")
FEED_TOKEN = os.getenv("LIVE_TRAFFIC_FEED_TOKEN", "")

BUFFER_SIZE = 800          # rows held in memory; the UI never asks for more
ASN_CACHE_MAX = 5000       # bounded so a long run cannot grow without limit

# --- log parsing -----------------------------------------------------------
# combined + a trailing `cf=<real client ip>` appended by the viabandwidth
# vhost, which is the Cloudflare-verified address rather than the edge node.
LINE_RE = re.compile(
    r'^(?P<edge>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>[^"]*?) (?P<proto>[^"]*)" '
    r'(?P<status>\d{3}) (?P<bytes>\S+) '
    r'"(?P<referer>[^"]*)" "(?P<ua>[^"]*)"'
    r'(?: cf=(?P<cf>\S+))?'
)

BOT_TOKENS = ("bot", "crawl", "spider", "slurp", "fetcher", "externalagent",
              "externalhit", "claude", "gpt", "openai", "anthropic",
              "perplexity", "python", "curl", "wget", "scrapy", "httpx",
              "go-http", "okhttp", "axios", "node-fetch", "libwww", "java/",
              "headless", "monitor", "uptime", "pingdom", "archiver")

ASSET_RE = re.compile(r'(_next/static|\.css|\.js|\.woff2?|\.ico|\.png|\.jpe?g|\.svg|\.webp)(\?|$)')
# Record pages are the asset of value here: /gpu/<domain>, /msp/<domain>, etc.
RECORD_RE = re.compile(r'^/(colo|gpu|bandwidth|ip-intel|msp|datacenters)/[^/]+/?(\?|$)')


def _classify_ua(ua: str) -> str:
    low = ua.lower()
    if any(t in low for t in BOT_TOKENS):
        return "declared"
    if low.startswith("mozilla/"):
        return "browser-ua"
    if not ua or ua == "-":
        return "none"
    return "other"


class AsnLookup:
    """Longest-prefix lookup against the local atlas, with a bounded cache.

    Uses the GiST index on asn_prefix_networks.prefix, so `<<=` is fast enough
    to run per unique address at live traffic rates. Falls back to an inert
    result whenever psycopg2 or the database is unavailable, because a missing
    atlas should degrade the feed's labels, never stop the feed.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()
        self._conn = None
        self._broken = False

    def _connect(self):
        if self._conn is not None or self._broken:
            return self._conn
        try:
            import psycopg2
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = True
        except Exception:
            self._broken = True
            self._conn = None
        return self._conn

    def lookup(self, ip: str) -> dict:
        if not ip:
            return {"asn": None, "segment": None, "org": None}
        with self._lock:
            hit = self._cache.get(ip)
            if hit is not None:
                self._cache.move_to_end(ip)
                return hit

        result = {"asn": None, "segment": None, "org": None}
        conn = self._connect()
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    # Longest prefix wins, mirroring how nginx geo resolves.
                    cur.execute(
                        """
                        SELECT a.asn, a.asn_segment,
                               COALESCE(a.org_name, a.whois_org_name)
                        FROM asn_prefix_networks p
                        JOIN asns a ON a.asn = p.asn
                        WHERE %s::inet <<= p.prefix
                        ORDER BY masklen(p.prefix) DESC
                        LIMIT 1
                        """,
                        (ip,),
                    )
                    row = cur.fetchone()
                    if row:
                        result = {"asn": row[0], "segment": row[1], "org": row[2]}
            except Exception:
                # A bad address (or a dropped connection) must not kill the tail.
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

        with self._lock:
            self._cache[ip] = result
            while len(self._cache) > ASN_CACHE_MAX:
                self._cache.popitem(last=False)
        return result


class TrafficTail:
    """Owns the SSH tail subprocess and the rolling buffer of parsed rows.

    Started lazily on first request rather than at import, so the app boots
    normally on a machine that cannot reach the web server.
    """

    def __init__(self):
        self.rows: deque = deque(maxlen=BUFFER_SIZE)
        self.seq = 0
        self.started = False
        self.error: Optional[str] = None
        self._lock = threading.Lock()
        self._asn = AsnLookup(ATLAS_DSN)
        # Per-IP running totals, used for the "1 request per address" signal
        # that distinguishes a proxy walk from a person reading pages.
        self._ip_hits: OrderedDict[str, int] = OrderedDict()
        self._ip_assets: OrderedDict[str, int] = OrderedDict()

    def _command(self) -> list:
        ssh = ["ssh", "-o", "StrictHostKeyChecking=no",
               "-o", "ServerAliveInterval=30",
               f"{SSH_USER}@{SSH_HOST}", f"tail -F -n 40 {LOG_PATH}"]
        if SSH_PASS:
            if not shutil.which("sshpass"):
                raise RuntimeError("LIVE_TRAFFIC_PASS is set but sshpass is not installed")
            return ["sshpass", "-p", SSH_PASS] + ssh
        return ssh

    def start(self):
        with self._lock:
            if self.started:
                return
            if not SSH_HOST:
                self.error = "LIVE_TRAFFIC_HOST is not set"
                return
            self.started = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            proc = subprocess.Popen(
                self._command(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
        except Exception as exc:
            self.error = f"could not start tail: {exc}"
            self.started = False
            return

        for line in proc.stdout:
            row = self._parse(line.rstrip("\n"))
            if row is not None:
                with self._lock:
                    self.seq += 1
                    row["seq"] = self.seq
                    self.rows.append(row)

        err = (proc.stderr.read() or "").strip()
        self.error = err or "tail ended"
        self.started = False   # allow a later request to restart it

    def _bump(self, store: OrderedDict, key: str) -> int:
        store[key] = store.get(key, 0) + 1
        store.move_to_end(key)
        while len(store) > ASN_CACHE_MAX:
            store.popitem(last=False)
        return store[key]

    def _parse(self, line: str) -> Optional[dict]:
        m = LINE_RE.match(line)
        if not m:
            return None
        g = m.groupdict()
        ip = g.get("cf") or g["edge"]
        path = g["path"]
        is_asset = bool(ASSET_RE.search(path))

        hits = self._bump(self._ip_hits, ip)
        assets = self._ip_assets.get(ip, 0)
        if is_asset:
            assets = self._bump(self._ip_assets, ip)

        try:
            ts = datetime.strptime(g["ts"], "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            ts = datetime.now(timezone.utc)

        asn = self._asn.lookup(ip)
        ua = g["ua"]
        referer = g["referer"]
        status = int(g["status"])

        return {
            "time": ts.strftime("%H:%M:%S"),
            "ip": ip,
            "status": status,
            "blocked": status in (403, 429),
            "method": g["method"],
            "path": path,
            "is_asset": is_asset,
            "is_record": bool(RECORD_RE.match(path)),
            "ua": ua[:160],
            "ua_class": _classify_ua(ua),
            "referer": "" if referer == "-" else referer[:120],
            "asn": asn["asn"],
            "segment": asn["segment"],
            "org": asn["org"],
            # Signals a human reads at a glance. `hits` is how many requests
            # this address has made since the feed started, and `assets` how
            # many of them were CSS/JS. One hit and zero assets, repeatedly,
            # across many addresses, is the proxy-walk shape.
            "ip_hits": hits,
            "ip_assets": assets,
            "suspect": (not is_asset) and assets == 0 and _classify_ua(ua) == "browser-ua",
        }


_tail = TrafficTail()


async def _remote(path: str) -> Optional[dict]:
    """Fetch from the monitored server's own feed. Returns None when remote mode
    is not configured, so the caller falls through to SSH mode."""
    if not (FEED_URL and FEED_TOKEN):
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{FEED_URL}{path}",
                headers={"Authorization": f"Bearer {FEED_TOKEN}"},
            )
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        return {"rows": [], "cursor": 0, "connected": False,
                "error": f"log feed unreachable: {exc.__class__.__name__}"}


@router.get("/feed")
async def feed(
    since: int = Query(0, ge=0, description="last seq already seen; 0 returns the buffer"),
    limit: int = Query(200, ge=1, le=BUFFER_SIZE),
    _=Depends(get_current_user),
):
    """Rows newer than `since`. The client polls this and passes back the
    highest seq it holds, so no row is delivered twice."""
    remote = await _remote(f"/feed?since={since}")
    if remote is not None:
        return remote
    _tail.start()
    rows = [r for r in list(_tail.rows) if r["seq"] > since]
    return {
        "rows": rows[-limit:],
        "cursor": _tail.seq,
        "connected": _tail.started,
        "error": _tail.error,
        "host": SSH_HOST or None,
    }


@router.get("/stats")
async def stats(_=Depends(get_current_user)):
    """Counters over whatever is currently buffered. Deliberately derived from
    the same rows the operator can see, so a number can always be traced back
    to the lines that produced it."""
    remote = await _remote("/stats")
    if remote is not None:
        return remote
    _tail.start()
    rows = list(_tail.rows)
    pages = [r for r in rows if not r["is_asset"]]
    ips = {r["ip"] for r in pages}
    single = {r["ip"] for r in pages if r["ip_hits"] == 1}

    by_segment: dict = {}
    for r in pages:
        key = r["segment"] or "unknown"
        by_segment[key] = by_segment.get(key, 0) + 1

    return {
        "buffered": len(rows),
        "page_requests": len(pages),
        "blocked": sum(1 for r in pages if r["blocked"]),
        "distinct_ips": len(ips),
        "single_request_ips": len(single),
        "suspect": sum(1 for r in pages if r["suspect"]),
        "records_served": sum(1 for r in pages if r["is_record"] and not r["blocked"]),
        "by_segment": dict(sorted(by_segment.items(), key=lambda kv: -kv[1])),
        "connected": _tail.started,
        "error": _tail.error,
    }
