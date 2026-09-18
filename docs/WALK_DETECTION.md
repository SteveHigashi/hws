# Catalogue walk detection

Catalogue Protection is an after-the-fact access-log analysis feature. It answers a
narrow question: does a window of requests have the shape of a client systematically
copying content records? It reports evidence and uncertainty. It does not block, slow,
redirect, challenge, or change any request.

## Privacy and architecture

Higashi does not store raw IP addresses. During import, the crawler network check runs
while the address is still in memory. The importer then replaces it with the existing
site-salted SHA-256 identity. The detector receives that salted identity, request path,
time, status, response size, referer, and the crawler verdict. The persisted detection
run contains only aggregates. Neither the raw address nor the per-request salted
identities are written to the detection table.

The implementation has two layers:

1. `backend/services/bot.py` is core crawler classification. It uses the bundled
   published prefix file and can accept already-resolved FCrDNS evidence where a
   vendor has no prefix feed.
2. `backend/services/walk_detection.py`, its model, router, migration, and dashboard
   page are the removable detection layer. Its detector functions have no database,
   network, or filesystem access. Core log import exposes only an optional observation
   callback and never imports the detector service.

## Crawler identity verdicts

- **verified** — the claimed operator matches a published vendor prefix, or (only when
  no usable prefix family is available) caller-supplied, already-resolved evidence
  passes forward-confirmed reverse DNS for the operator's documented suffix.
- **unverified** — the user agent looks automated, but no authoritative network test is
  available. This is not an accusation.
- **forged** — a valid address claims an operator whose published range set is present,
  and the address is outside that set. This is reported prominently because it is the
  highest-confidence deception signal available from the log.

The importer never starts a DNS lookup, because that would send a visitor address to a
resolver and break the no-outbound boundary. Deployments that already enrich logs with
locally resolved, forward-confirmed DNS evidence can inject that pure fallback into the
classifier. Without it, families lacking a prefix feed remain unverified.

OpenAI, Anthropic, social preview, audit, and generic tool names remain unverified when
the bundled data has no authoritative network contract for them. A recognizable name
is never upgraded to verified on user-agent text alone.

### Prefix data and the only outbound operation

`backend/data/crawler_ranges.json` is bundled and loaded into sorted numeric intervals
at process startup. Request-time classification is local and uses binary search; it
does not call a vendor.

The optional `backend/scripts/fetch_crawler_ranges.py` contacts only the vendor URLs
listed in that script. It sends a fixed user-agent and no hostname, log row, count,
identifier, or traffic data. Higashi never runs it automatically. An operator may run
or schedule it, for example weekly:

```text
17 3 * * 2 /path/to/higashi/.venv/bin/python /path/to/higashi/backend/scripts/fetch_crawler_ranges.py
```

Set `HIGASHI_CRAWLER_RANGE_FETCH=0` to make the script exit without network access. Set
`HIGASHI_CRAWLER_RANGES=/writable/path/crawler_ranges.json` to use a separately managed
last-known-good file. A partial or implausibly small refresh is rejected.

## What each detector measures

Analysis is divided into aligned 30-minute windows so a multi-day import does not hide a
short copying episode inside normal traffic.

### SHAPE — independent primary trigger

SHAPE counts salted identities that made exactly one request in the window, received a
full content record, and fetched no static asset. It fires when at least ten such
identities account for at least 70% of full content records. Verified crawlers are
excluded from this trigger.

This catches a rotating pool whose members take one record and disappear. It does not
depend on URL order. It can be defeated by reusing identities, making cover requests,
or fetching assets. At very low traffic it deliberately returns insufficient evidence.

### ORDER — independent primary trigger

ORDER examines consecutive full content record slugs. With at least twelve adjacent
pairs, it fires when at least 85% move in the same lexical direction. It is independent
of SHAPE and can catch a sequential walk from one address.

It is defeated by shuffling or choosing records non-lexically. That is why ORDER is not
a required condition for SHAPE. Combining them with `AND` would repeat the historical
failure where one shuffle disabled the detector.

### Asset-fetch absence

The detector infers static assets from same-origin paths and common JS, CSS, font, image,
and media extensions. It reports the share of identities receiving content while
fetching no asset. This is costly for a scraper to imitate because a normal first page
render usually fetches multiple assets.

It is not proof by itself. Cached assets, text browsers, prefetchers, API clients,
single-file pages, and logs that omit asset requests can all appear asset-less. A scraper
can fetch a few plausible assets.

### Records taken — response size, never status alone

A successful status does not prove that content left the server: gates, stubs, and
decoys can also return 200. Higashi first infers repeated path families, such as
`/catalogue/:item`, then calculates the rolling median byte size of successful GET
responses in that family. A row counts as a record taken only when its bytes are at
least 60% of a baseline of at least 1 KiB.

This deliberately favors avoiding inflated loss figures. It can undercount very small
HTML records, highly variable templates, downloads served from paths that look like
assets, or a window containing no full-response baseline. Compression or template
changes can move the baseline; compare trends and inspect the source log when precision
matters.

### Per-address rate

For salted identities that received full records, Higashi reports median and 95th
percentile requests per active calendar day. High rates separate a concentrated
extractor from a low-rate search crawler.

This metric fails against address rotation. When at least half the identities took one
record, the dashboard says so explicitly. A low median in that state is not reassuring.

### Referer absence

The report measures the share of full record responses with no referer. Harvest jobs
often fetch bare URLs; browser navigation more often carries same-site or discovery
context.

Privacy tools, direct links, apps, email clients, and Referrer-Policy can all remove the
header. Referers are also trivial to forge, so this is supporting evidence only.

### Shared-queue fingerprint

Among consecutive full records assigned to different salted identities, the detector
measures how often both slugs begin with the same alphanumeric character. A high ratio
can expose one sorted work queue distributed across a rotating pool even though no
single identity has a sequence.

It can be defeated by shuffling or by choosing a different partition strategy. Small
catalogues and naturally clustered browsing can produce correlation, so the signal
requires at least twelve cross-identity pairs and corroborates the primary triggers.

### Scroll and engagement absence

For each time window, the persistence adapter compares sessions with behavior events to
all sessions observed for that site and time. High absence is shown as corroboration.
It never creates a walk verdict or primary trigger.

Search crawlers do not run JavaScript; some people do not scroll; trackers may be blocked
or newly installed; and log-derived sessions cannot always be joined exactly to a
client-side session. A scraper can also synthesize events. This signal is intentionally
weak and aggregate.

## Interpreting the score and verdict

- **Catalogue walk detected** means SHAPE or ORDER fired. Either is sufficient.
- **Suspicious** means high-value deception or several supporting signals were present,
  but neither primary walk shape was proven.
- **No walk detected** means the analyzed rows did not cross the thresholds. It does not
  prove that copying did not happen.
- **Insufficient data** means too few full content responses were available to judge.

The 0–100 evidence score helps rank windows. It is not a probability, a count of people,
or a legal conclusion. Thresholds are general defaults derived from observed failure
modes, not fitted to a particular site's known loss totals.

## Explicit non-goals

There is no enforcement code in this feature. It has no nginx integration, middleware,
rate limiter, blocklist, decoy response, challenge, authentication decision, or inline
request-path position. It does not identify a human or company behind a salted identity.
It does not phone home or report product usage. Only logs the operator imports and local
behavior events are analyzed.
