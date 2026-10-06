#!/usr/bin/env python3
"""Refresh crawler prefixes from vendor feeds, retaining last-known-good data.

This is the only feature component that can make outbound requests. It runs only
when an operator invokes or schedules it and sends no host or traffic data.
Set HIGASHI_CRAWLER_RANGE_FETCH=0 to disable it explicitly.
"""

import datetime
import ipaddress
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request


METADATA_KEY = "_meta"

FEEDS = {
    "googlebot": ["https://developers.google.com/static/search/apis/ipranges/googlebot.json"],
    "google-special": ["https://developers.google.com/static/search/apis/ipranges/special-crawlers.json"],
    "google-user": ["https://developers.google.com/static/search/apis/ipranges/user-triggered-fetchers-google.json"],
    "bingbot": ["https://www.bing.com/toolbox/bingbot.json"],
    "applebot": ["https://search.developer.apple.com/applebot.json"],
    "duckduckbot": ["https://duckduckgo.com/duckduckbot.json"],
    "duckassistbot": ["https://duckduckgo.com/duckassistbot.json"],
    "perplexitybot": ["https://www.perplexity.ai/perplexitybot.json"],
}
MINIMUMS = {
    "googlebot": 50,
    "google-special": 20,
    "google-user": 20,
    "bingbot": 5,
    "applebot": 5,
    "duckduckbot": 20,
    "perplexitybot": 2,
}
DEFAULT_DEST = Path(__file__).resolve().parent.parent / "data" / "crawler_ranges.json"


def _prefixes(payload) -> list[str]:
    if isinstance(payload, dict) and isinstance(payload.get("prefixes"), list):
        return [
            item.get("ipv4Prefix") or item.get("ipv6Prefix")
            or item.get("ipv4prefix") or item.get("ipv6prefix")
            for item in payload["prefixes"]
            if isinstance(item, dict)
        ]
    if isinstance(payload, list):
        return [value for value in payload if isinstance(value, str)]
    return []


def main() -> int:
    if os.getenv("HIGASHI_CRAWLER_RANGE_FETCH", "1").lower() in {"0", "false", "no", "off"}:
        print("crawler range refresh disabled by HIGASHI_CRAWLER_RANGE_FETCH")
        return 0

    destination = Path(os.getenv("HIGASHI_CRAWLER_RANGES", str(DEFAULT_DEST)))
    try:
        previous = json.loads(destination.read_text())
    except (OSError, ValueError):
        previous = {}
    # METADATA_KEY is provenance, not a crawler family. Strip it before the
    # last-known-good carry-forward below so it cannot be mistaken for prefixes.
    if isinstance(previous, dict):
        previous_stamp = previous.get(METADATA_KEY)
        previous = {k: v for k, v in previous.items() if k != METADATA_KEY}
    else:
        previous_stamp = None
        previous = {}

    refreshed: dict[str, list[str]] = {}
    carried_forward: list[str] = []
    for family, urls in FEEDS.items():
        values: list[str] = []
        for url in urls:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Higashi-range-refresh/1.0"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    values.extend(_prefixes(json.loads(response.read().decode())))
            except Exception as exc:
                print(f"WARN {family} {url}: {exc}", file=sys.stderr)
        clean = []
        for value in values:
            try:
                clean.append(str(ipaddress.ip_network(value, strict=False)))
            except (TypeError, ValueError):
                continue
        if clean:
            refreshed[family] = sorted(set(clean))
        elif family in previous:
            refreshed[family] = previous[family]
            carried_forward.append(family)
        else:
            carried_forward.append(family)

    failures = [
        f"{family}: {len(refreshed.get(family, []))} < {minimum}"
        for family, minimum in MINIMUMS.items()
        if family in previous and len(refreshed.get(family, [])) < minimum
    ]
    if failures:
        print("REFUSING to replace last-known-good ranges: " + "; ".join(failures), file=sys.stderr)
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".crawler-ranges.", dir=destination.parent)
    try:
        # Stamp when this data was last actually CONFIRMED current. The verifier
        # uses it to decide whether the ranges can still justify a verdict, and
        # the file's mtime does not survive packaging, copying or a checkout.
        #
        # The stamp only advances when every family was refreshed from its feed.
        # A run where any family had to fall back to the previous data has not
        # confirmed that family, and advancing anyway would make a box that has
        # lost outbound access look permanently fresh while serving data that
        # never changes, which is precisely the state the freshness check exists
        # to catch. Keeping the old stamp lets the data age honestly instead.
        payload = dict(refreshed)
        previous_meta = previous_stamp if isinstance(previous_stamp, dict) else {}
        if carried_forward:
            print(
                "not advancing the freshness stamp; carried forward: "
                + ", ".join(sorted(carried_forward)),
                file=sys.stderr,
            )
            if previous_meta.get("generated_at"):
                payload[METADATA_KEY] = previous_meta
        else:
            payload[METADATA_KEY] = {
                "generated_at": datetime.datetime.now(datetime.timezone.utc)
                .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "generator": "fetch_crawler_ranges",
            }
        with os.fdopen(handle, "w") as stream:
            json.dump(payload, stream, indent=1, sort_keys=True)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(
        f"wrote {destination}: {len(refreshed)} families, "
        f"{sum(len(values) for values in refreshed.values())} prefixes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
