#!/usr/bin/env python3
"""
Higashi Analytics — scheduled access-log import.

Runs from cron. Imports new access-log lines incrementally (the importer keeps a
per-stream cursor keyed on `log_path`, so re-reading the live log is idempotent —
already-imported lines are skipped by timestamp, no duplicates).

  * cloudanalyst.net  — read straight from this account's local log directory.
  * stevenhigashi.com — pulled over SSH (separate hosting account on the same box).
  * viabandwidth.com  — pulled over SSH from the IONOS VPS (nginx, not Cloudways).

After importing, `reclassify_bots.py` runs a population-level pass that flags
distributed proxy pools and burst scrapers that per-line UA matching cannot see.

Output is appended to import_cron.log by the crontab entry.
"""
import asyncio
import glob
import gzip
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

# Walk-box edition (2026-09-19). Layout comes from the environment set by
# higashi-import.service; nothing here is Cloudways-local any more.
BASE = os.environ.get("HIGASHI_HOME", "/opt/higashi")
DB_PATH = os.environ.get("HIGASHI_DB", "/var/lib/higashi/higashi.db")
JOURNAL_DIR = os.environ.get("HIGASHI_JOURNAL_DIR", "/var/lib/higashi/reclassify_journal")
os.chdir(BASE + "/backend")                       # config reads HIGASHI_ENV_PATH
sys.path.insert(0, BASE + "/backend")

from config import get_settings                   # noqa: E402
from services.log_importer import import_log_file  # noqa: E402

# Explicit absolute path to the LIVE database (avoid any CWD/.env ambiguity).
DB = "sqlite+aiosqlite:////" + DB_PATH.lstrip("/")

S = get_settings()

# cloudanalyst.net logs live on the Cloudways box; pulled over SSH like stevenhigashi.
CA_HOST = getattr(S, "sftp_host", "cloudanalyst.net")
CA_PORT = int(getattr(S, "sftp_port", 22) or 22)
CA_USER = getattr(S, "sftp_user_cloudanalyst", "steve2")
CA_PASS = getattr(S, "sftp_password", "")
CLOUD_LOG_DIR = "/home/1596013.cloudwaysapps.com/hunwkuvarr/logs"

# stevenhigashi.com runs under a different Cloudways account; pull its logs over SSH.
SH_HOST = getattr(S, "sftp_host", "cloudanalyst.net")
SH_PORT = int(getattr(S, "sftp_port", 22) or 22)
SH_USER = getattr(S, "sftp_user_stevenhigashi", "steve")
SH_PASS = getattr(S, "sftp_password_stevenhigashi", "")
SH_LOG_DIR = "/home/1596013.cloudwaysapps.com/kyackqfqrp/logs"

# viabandwidth.com runs on its own IONOS VPS behind Cloudflare (plain nginx).
VBW_HOST = os.environ.get("VBW_HOST", "82.165.188.141")
VBW_PORT = int(os.environ.get("VBW_PORT", "22") or 22)
VBW_USER = os.environ.get("VBW_USER", "root")
VBW_PASS = os.environ.get("VBW_PASS", "") or getattr(S, "ssh_password_viabandwidth", "")
VBW_LOG_DIR = "/var/log/nginx"
# Current log plus yesterday's rotation. The importer's cursor makes re-reads
# idempotent, so overlapping on purpose costs nothing and closes the gap that
# opens when the cron fires either side of midnight rotation.
VBW_FILES = ("access.log", "access.log.1")

# The VPS log_format is `cf_combined`, which appends the true client address as
# `cf=<ip>` because $remote_addr is Cloudflare's edge. Without this rewrite every
# viabandwidth visitor would be geolocated to a Cloudflare PoP and, worse, would
# collapse into a handful of ip_hashes — destroying session and unique counts.
_CF_RE = re.compile(r'^(\S+)(\s.*\scf=)(\S+)\s*$')


def _rewrite_cf_ips(raw: bytes) -> tuple[bytes, int]:
    """Swap Cloudflare's edge IP for the real client IP recorded in cf=."""
    out, swapped = [], 0
    for line in raw.decode("utf-8", "replace").splitlines():
        m = _CF_RE.match(line)
        if m and m.group(3) not in ("-", ""):
            # group(2) is everything between the two addresses, "…  cf=" included
            line = m.group(3) + m.group(2) + m.group(3)
            swapped += 1
        out.append(line)
    return ("\n".join(out) + "\n").encode(), swapped

# Both the Apache (dynamic) and nginx-cache (static) access logs carry real page
# hits on Cloudways; import each as its own stream so neither is missed.
STREAMS = ("backend_wordpress", "static_wordpress")


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def _import_cloudways_site(domain, host, port, user, password, log_dir, prefix):
    """Pull a Cloudways account's access logs over SSH exec (ls / cat) and import them.
    The SFTP subsystem is chrooted on that host, but the shell sees the real paths."""
    if not password:
        print(f"{_stamp()}  {domain}  SKIP: no SSH password in settings")
        return
    import paramiko
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(host, port=port, username=user, password=password, timeout=25, banner_timeout=25)
    try:
        for stream in STREAMS:
            _in, out, _err = cli.exec_command(f"ls {log_dir}/*{stream}*access.log 2>/dev/null")
            files = [l.strip() for l in out.read().decode().splitlines() if l.strip()]
            for remote in files:
                local = os.path.join(tempfile.gettempdir(), prefix + os.path.basename(remote))
                try:
                    _i, sout, _e = cli.exec_command(f"cat {remote}")
                    data = sout.read()
                    with open(local, "wb") as fh:
                        fh.write(data)
                    r = await import_log_file(local, domain, DB, log_path=f"{domain}:{stream}")
                    print(f"{_stamp()}  {domain}  {stream}  "
                          f"+{r['page_views']}pv +{r['bot_visits']}bot "
                          f"(skip {r['skipped']}, err {r['errors']})")
                finally:
                    if os.path.exists(local):
                        os.remove(local)
    finally:
        cli.close()


async def import_cloudanalyst():
    await _import_cloudways_site("cloudanalyst.net", CA_HOST, CA_PORT, CA_USER, CA_PASS, CLOUD_LOG_DIR, "ca_")


async def import_stevenhigashi():
    await _import_cloudways_site("stevenhigashi.com", SH_HOST, SH_PORT, SH_USER, SH_PASS, SH_LOG_DIR, "sh_")


async def import_viabandwidth():
    """Pull nginx logs off the IONOS VPS, de-Cloudflare them, then import."""
    if not VBW_PASS:
        print(f"{_stamp()}  viabandwidth.com  SKIP: no SSH password "
              f"(set VBW_PASS or ssh_password_viabandwidth in settings)")
        return
    import paramiko
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(VBW_HOST, port=VBW_PORT, username=VBW_USER,
                password=VBW_PASS, timeout=25, banner_timeout=25)
    try:
        for name in VBW_FILES:
            remote = f"{VBW_LOG_DIR}/{name}"
            # We decompress on the remote side, so what lands here is always plain
            # text. The local name must NOT keep a .gz suffix or the importer will
            # try to gunzip already-gunzipped bytes and fail on every rotated file.
            local = os.path.join(tempfile.gettempdir(),
                                 "vbw_" + (name[:-3] if name.endswith(".gz") else name))
            try:
                reader = "zcat" if name.endswith(".gz") else "cat"
                _i, sout, _e = cli.exec_command(f"{reader} {remote} 2>/dev/null")
                raw = sout.read()
                if not raw:
                    print(f"{_stamp()}  viabandwidth.com  {name}  SKIP: empty/missing")
                    continue
                data, swapped = _rewrite_cf_ips(raw)
                with open(local, "wb") as fh:
                    fh.write(data)
                r = await import_log_file(
                    local, "viabandwidth.com", DB,
                    log_path=f"viabandwidth.com:{name}",
                )
                print(f"{_stamp()}  viabandwidth.com  {name}  "
                      f"+{r['page_views']}pv +{r['bot_visits']}bot "
                      f"(skip {r['skipped']}, err {r['errors']}, cf-ip {swapped})")
            except Exception as e:
                print(f"{_stamp()}  viabandwidth.com  {name}  ERROR: {e}")
            finally:
                if os.path.exists(local):
                    os.remove(local)
    finally:
        cli.close()


def reclassify():
    """Population-level bot pass — catches what per-line UA matching cannot."""
    script = os.path.join(BASE, "reclassify_bots.py")
    if not os.path.exists(script):
        print(f"{_stamp()}  reclassify  SKIP: {script} not found")
        return
    try:
        p = subprocess.run(
            [sys.executable, script, "--db", DB_PATH, "--days", "7", "--apply"],
            capture_output=True, text=True, timeout=900,
        )
        tail = [l for l in (p.stdout or "").splitlines() if l.strip()][-6:]
        for l in tail:
            print(f"{_stamp()}  reclassify  {l}")
        if p.returncode != 0:
            print(f"{_stamp()}  reclassify  rc={p.returncode} {(p.stderr or '')[:300]}")
    except Exception as e:
        print(f"{_stamp()}  reclassify  ERROR: {e}")


async def main():
    try:
        await import_cloudanalyst()
    except Exception as e:
        print(f"{_stamp()}  cloudanalyst.net  FATAL: {e}")
    try:
        await import_stevenhigashi()
    except Exception as e:
        print(f"{_stamp()}  stevenhigashi.com  FATAL: {e}")
    try:
        await import_viabandwidth()
    except Exception as e:
        print(f"{_stamp()}  viabandwidth.com  FATAL: {e}")
    reclassify()


if __name__ == "__main__":
    asyncio.run(main())
