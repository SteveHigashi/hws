#!/usr/bin/env python3
"""
Higashi Analytics — post-import bot reclassification.

WHY THIS EXISTS
---------------
The log importer judges one line at a time, so it can only flag bots by
user-agent string (services/bot.py) and writes is_bot=0 for everything else.
That misses the traffic that actually inflates the "human" numbers:

  1. Distributed proxy pools. Thousands of IPs all presenting ONE byte-identical
     browser UA, roughly one request each, spread across many countries. A real
     audience never looks like that: real browsers carry a spread of versions and
     real visitors come back for more than a single page. On cloudanalyst.net a
     single UA string accounted for 7,598 hits from 6,846 distinct IPs across 18
     countries in one week.
  2. Single-IP bursts. One address pulling hundreds of pages in a day.
  3. Vulnerability probes. /.env, /wp-login.php and friends.

Every dashboard query already filters `Event.is_bot == False`, so flagging here
cleans every page of the dashboard at once. Nothing is deleted.

SAFETY
------
  * Dry-run by default. Pass --apply to write.
  * Never touches an event with screen_width set. Those came from tracker.js,
    which means a real browser ran real JavaScript. That is the strongest
    humanity proof available, so it always wins over any heuristic here.
  * A UA fingerprint that produced tracker.js events is exempt from the
    proxy-pool rule for the same reason.
  * Every applied run writes a reversible journal of the exact event ids it
    flagged, so `--revert <journal>` puts them back.

Idempotent: already-flagged events are skipped, so re-running is free.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE, "backend", "higashi.db")
JOURNAL_DIR = os.environ.get("HIGASHI_JOURNAL_DIR", os.path.join(BASE, "reclassify_journal"))

# --- Rule 1: distributed proxy pool -----------------------------------------
# One identical UA string, many IPs, almost no repeat visits, many countries.
#
# UA identity alone is NOT enough: Chrome freezes its UA to the major version
# ("143.0.0.0"), so hundreds of unrelated real visitors legitimately share a
# byte-identical string. The discriminator that actually works is how the hits
# spread over PAGES relative to IPs:
#
#   pages/IPs very LOW   → thousands of IPs pounding a handful of URLs.
#   pages/IPs near 1.0   → each IP takes a different URL: a distributed crawl
#                          walking the sitemap one page per proxy.
#   pages/IPs in between → what humans look like. Real audiences pile onto the
#                          same popular pages, so unique pages grow far slower
#                          than unique visitors. This band is left alone.
PROXY_MIN_IPS = 60           # pool has to be big enough to be a pool
PROXY_MAX_HITS_PER_IP = 1.6  # real visitors read more than one page
PROXY_MIN_COUNTRIES = 5      # a genuine local audience is not spread this wide
PROXY_HAMMER_MAX = 0.10      # pages/IPs at or below this = mass hammering
PROXY_CRAWL_MIN = 0.65       # pages/IPs at or above this = distributed crawl
PROXY_TRACKER_EXEMPT = 3     # this many tracker.js events proves real browsers

# --- Rule 2: single-IP burst -------------------------------------------------
BURST_PER_DAY = 300

# --- Rule 3: probe paths -----------------------------------------------------
# --- Rule 4: XHR / API endpoints --------------------------------------------
# Access logs cannot tell a page view from a background fetch. An admin
# dashboard polling /api/admin/overview every few seconds looked like thousands
# of human page views on viabandwidth. These are requests, not readers.
XHR_PATTERNS = ["/api/", "/_next/data/", "/graphql", "/SDK/", ".php?check="]

PROBE_PATTERNS = [
    "/.env", "/.git", "/.aws", "/.ssh", "/wp-login", "/wp-admin",
    "/wp-content", "/wp-includes", "/xmlrpc.php", "/phpmyadmin",
    "/phpinfo", "/vendor/phpunit", "/cgi-bin/", "/.well-known/openid",
    "/solr/", "/actuator/", "/config.json", "/backup.sql", "/shell",
    "/eval-stdin.php", "/hello.world",
]


def _connect(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        sys.exit(f"database not found: {db_path}")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _sites(con: sqlite3.Connection) -> dict:
    return {r["id"]: r["domain"] for r in con.execute("select id, domain from sites")}


def find_proxy_pools(con, site_id, since):
    """Rule 1 — identical UA fanned across a large, shallow, multi-country IP set."""
    rows = con.execute(
        """
        select user_agent                                        as ua,
               count(*)                                          as hits,
               count(distinct ip_hash)                           as ips,
               count(distinct country)                           as countries,
               count(distinct page_url)                          as pages,
               sum(case when screen_width is not null then 1 else 0 end) as tracker_hits
          from events
         where site_id = ? and timestamp >= ? and is_bot = 0
           and user_agent is not null and user_agent != ''
         group by user_agent
        having ips >= ?
        """,
        (site_id, since, PROXY_MIN_IPS),
    ).fetchall()

    hits = []
    for r in rows:
        if r["tracker_hits"] >= PROXY_TRACKER_EXEMPT:
            continue                              # real browsers ran JS here
        if r["ips"] == 0:
            continue
        ratio = r["hits"] / r["ips"]
        if ratio >= PROXY_MAX_HITS_PER_IP:
            continue
        if r["countries"] < PROXY_MIN_COUNTRIES:
            continue
        spread = r["pages"] / r["ips"]
        if spread <= PROXY_HAMMER_MAX:
            shape = "hammer"
        elif spread >= PROXY_CRAWL_MIN:
            shape = "crawl"
        else:
            continue                              # human-shaped: leave it alone
        hits.append({
            "ua": r["ua"], "hits": r["hits"], "ips": r["ips"],
            "countries": r["countries"], "ratio": round(ratio, 2),
            "pages": r["pages"], "spread": round(spread, 2), "shape": shape,
        })
    return hits


def find_bursts(con, site_id, since):
    """Rule 2 — a single IP pulling more pages in one day than a person reads."""
    return con.execute(
        """
        select ip_hash, date(timestamp) as d, count(*) as hits
          from events
         where site_id = ? and timestamp >= ? and is_bot = 0
           and screen_width is null
         group by ip_hash, date(timestamp)
        having hits > ?
         order by hits desc
        """,
        (site_id, since, BURST_PER_DAY),
    ).fetchall()


def find_probes(con, site_id, since):
    """Rule 3 — requests for files that only an attacker goes looking for."""
    clause = " or ".join(["page_url like ?"] * len(PROBE_PATTERNS))
    params = [site_id, since] + [f"%{p}%" for p in PROBE_PATTERNS]
    return con.execute(
        f"""
        select id, page_url from events
         where site_id = ? and timestamp >= ? and is_bot = 0
           and screen_width is null and ({clause})
        """,
        params,
    ).fetchall()


def find_xhr(con, site_id, since):
    """Rule 4 — background fetches logged as if they were page views."""
    clause = " or ".join(["page_url like ?"] * len(XHR_PATTERNS))
    params = [site_id, since] + [f"%{p}%" for p in XHR_PATTERNS]
    return con.execute(
        f"""
        select id, page_url from events
         where site_id = ? and timestamp >= ? and is_bot = 0 and ({clause})
        """,
        params,
    ).fetchall()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--days", type=int, default=30,
                    help="lookback window in days (default 30)")
    ap.add_argument("--site", help="only this domain (default: all sites)")
    ap.add_argument("--apply", action="store_true",
                    help="actually write is_bot=1 (default is a dry run)")
    ap.add_argument("--revert", metavar="JOURNAL",
                    help="undo a previous run from its journal file")
    args = ap.parse_args()

    con = _connect(args.db)

    if args.revert:
        with open(args.revert) as fh:
            journal = json.load(fh)
        ids = [e["id"] for e in journal["flagged"]]
        con.executemany("update events set is_bot = 0 where id = ?",
                        [(i,) for i in ids])
        con.commit()
        print(f"reverted {len(ids)} events from {args.revert}")
        return

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)) \
        .strftime("%Y-%m-%d %H:%M:%S")
    sites = _sites(con)
    if args.site:
        sites = {k: v for k, v in sites.items() if v == args.site}
        if not sites:
            sys.exit(f"no site with domain '{args.site}'")

    flagged: list[dict] = []
    summary = defaultdict(lambda: defaultdict(int))

    for site_id, domain in sites.items():
        print(f"\n=== {domain} (last {args.days}d) ===")

        pools = find_proxy_pools(con, site_id, since)
        for p in pools:
            rows = con.execute(
                """select id from events
                    where site_id = ? and timestamp >= ? and is_bot = 0
                      and user_agent = ? and screen_width is null""",
                (site_id, since, p["ua"]),
            ).fetchall()
            for r in rows:
                flagged.append({"id": r["id"], "rule": "proxy_pool", "site": domain})
            summary[domain]["proxy_pool"] += len(rows)
            print(f"  {p['shape']:<7}{len(rows):7d} events | {p['ips']} IPs / "
                  f"{p['countries']} countries / {p['ratio']} hits-per-IP / "
                  f"{p['pages']} pages (spread {p['spread']})")
            print(f"              {p['ua'][:96]}")

        bursts = find_bursts(con, site_id, since)
        for b in bursts:
            rows = con.execute(
                """select id from events
                    where site_id = ? and ip_hash = ? and date(timestamp) = ?
                      and is_bot = 0 and screen_width is null""",
                (site_id, b["ip_hash"], b["d"]),
            ).fetchall()
            for r in rows:
                flagged.append({"id": r["id"], "rule": "burst_ip", "site": domain})
            summary[domain]["burst_ip"] += len(rows)
        if bursts:
            print(f"  burst-IP    {summary[domain]['burst_ip']:6d} events across "
                  f"{len(bursts)} IP-days (>{BURST_PER_DAY}/day)")

        probes = find_probes(con, site_id, since)
        for r in probes:
            flagged.append({"id": r["id"], "rule": "probe_path", "site": domain})
        summary[domain]["probe_path"] += len(probes)
        if probes:
            print(f"  probe-path  {len(probes):6d} events")

        xhr = find_xhr(con, site_id, since)
        for r in xhr:
            flagged.append({"id": r["id"], "rule": "xhr_endpoint", "site": domain})
        summary[domain]["xhr_endpoint"] += len(xhr)
        if xhr:
            print(f"  xhr-api     {len(xhr):6d} events")

        if not (pools or bursts or probes or xhr):
            print("  nothing to reclassify")

    # de-duplicate: an event can trip more than one rule
    seen, unique = set(), []
    for e in flagged:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)

    print(f"\n--- total: {len(unique)} events to flag as bot ---")
    for domain, rules in summary.items():
        total = sum(rules.values())
        before = con.execute(
            "select count(*) from events where site_id = (select id from sites "
            "where domain = ?) and timestamp >= ? and is_bot = 0", (domain, since)
        ).fetchone()[0]
        pct = (100.0 * total / before) if before else 0
        print(f"  {domain}: {total} of {before} currently-human events ({pct:.0f}%) "
              f"→ {dict(rules)}")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to commit.")
        return

    if not unique:
        print("nothing to do")
        return

    os.makedirs(JOURNAL_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    journal_path = os.path.join(JOURNAL_DIR, f"reclassify_{stamp}.json")
    with open(journal_path, "w") as fh:
        json.dump({
            "run_at": stamp, "days": args.days, "db": args.db,
            "thresholds": {
                "PROXY_MIN_IPS": PROXY_MIN_IPS,
                "PROXY_MAX_HITS_PER_IP": PROXY_MAX_HITS_PER_IP,
                "PROXY_MIN_COUNTRIES": PROXY_MIN_COUNTRIES,
                "BURST_PER_DAY": BURST_PER_DAY,
            },
            "flagged": unique,
        }, fh, indent=1)

    con.executemany("update events set is_bot = 1 where id = ?",
                    [(e["id"],) for e in unique])
    con.commit()
    print(f"flagged {len(unique)} events. journal: {journal_path}")
    print(f"to undo: python3 {os.path.basename(__file__)} --revert {journal_path}")


if __name__ == "__main__":
    main()
