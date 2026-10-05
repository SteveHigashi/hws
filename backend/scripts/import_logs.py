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

This is a thin command-line wrapper. All parsing and writing is done by
services.log_importer.import_log_file, which is the same code path the in-app
importer uses, so a log imported here and a log imported from the dashboard
produce identical rows.

Until 2026-10-05 this script carried its own copy of the parse-and-insert loop,
and that copy had drifted: it built BotVisit rows with no timestamp, so every
imported crawler visit fell back to the column default of import time, and with
no verification_state, ip_hash, http_status, response_bytes or referrer. A
historical import therefore collapsed the whole crawler timeline onto the day of
the import and lost the verification evidence. Do not reintroduce a second
parsing path here; call the service.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")
from config import get_settings
from services.log_importer import import_log_file


def _progress(done: int, total: int) -> None:
    """Print a line every 2000 records, and once at the end."""
    if total and (done % 2000 == 0 or done == total):
        print(f"  parsed {done:,} of {total:,} lines")


async def run(logfile: str, domain: str) -> None:
    if not Path(logfile).is_file():
        print(f"No such log file: {logfile}")
        sys.exit(1)

    settings = get_settings()
    print(f"Importing {logfile} into '{domain}'...")

    try:
        result = await import_log_file(
            filepath=logfile,
            domain=domain,
            db_url=settings.database_url,
            progress_callback=_progress,
        )
    except ValueError as exc:
        # raised when the domain does not match a site
        print(str(exc))
        sys.exit(1)

    print("\nDone.")
    print(f"  Page views imported : {result['page_views']:,}")
    print(f"  Bot visits imported : {result['bot_visits']:,}")
    print(f"  Sessions created    : {result['sessions']:,}")
    print(f"  Skipped (static/etc): {result['skipped']:,}")
    print(f"  Parse errors        : {result['errors']:,}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/import_logs.py <logfile> <site_domain>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1], sys.argv[2]))
