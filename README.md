# Higashi Web Stats (HWS)

**See who — and what — is actually visiting your website.**

Self-hosted web analytics for a web where a growing share of traffic is not human.
HWS reads your own server logs and separates ordinary visitors from crawlers, bots,
AI systems and scrapers, then writes a plain-language reading from fixed rules.

It runs on your server. It observes and reports; it never blocks or changes traffic.

---

## Install

```bash
curl -fsSL https://hws.jotnotes.com/releases/install.sh | sudo sh
```

**Requirements: Python 3.9 or newer, and systemd.** That is all. The frontend arrives
already built, so there is no Node, no npm and no build step on the installing
machine. The database is SQLite, created for you. There is no Docker, no PostgreSQL
and no Redis.

The release is a signed tarball on our own host — checksum and Ed25519 signature are
published beside it at <https://hws.jotnotes.com/releases/>. To install a specific
version, or to check what you are about to run, download it first and read
`install.sh` before running it.

---

## Source

Complete source for the AGPL parts of HWS is at
**<https://github.com/SteveHigashi/hws>** — backend, frontend source, migrations,
build files and dependency manifests. The release tarball also carries the frontend
source used to build the assets it ships, so a copy of the tarball is enough to
rebuild and modify HWS without going anywhere.

Rebuilding the frontend, if you want to:

```bash
cd frontend && npm ci && npm run build
```

---

## What is open, and what is not

| Component | Path | Licence |
|---|---|---|
| **HWS core** — the self-hosted application | `backend/`, `frontend/`, `server/` | **AGPL-3.0-or-later** |
| **Shared reading rules** | `backend/higashi_reading/` | **MIT** |
| **Browser tracker** — the snippet you embed | `tracker/` | **MIT** |
| **HWS Live** — the paid hosted service | not in this repository | **Proprietary** |
| **Name, logo and brand** | — | see [TRADEMARK.md](TRADEMARK.md) |

The tracker and the reading rules are MIT on purpose: embedding the tracker places no
licence obligation on your site, and both the free product and the paid service run
the *same* reading rules so their readings agree. See [LICENSES.md](LICENSES.md).

**HWS Live is proprietary and is not part of this repository.** HWS contains only the
client code needed to talk to it.

---

## HWS Live (optional, paid)

HWS is free and complete on its own. HWS Live is a separate paid service that adds
stored history across weeks, week-over-week change, comparison with sites of similar
size, crawler lists kept current for you, and a weekly email.

It is **off until you turn it on**. You buy a key at
<https://shop.jotnotes.com/buy?product=hws-live&plan=monthly>, paste it into your own
install, and that is the only thing that enables it — installing HWS never enables
Live. See <https://hws.jotnotes.com/kb/your-key.html>.

When Live is enabled, your install sends an aggregate report: counts, crawler names
and a verdict. It does not send IP addresses, paths, URLs or user agents.

---

## What leaves your server

Nothing, unless you enable it. In full:

| What | When | Where |
|---|---|---|
| Aggregate Live report | only if you configure an HWS Live key | `live.hws.jotnotes.com` |
| Visitor IP, for geolocation | **only if you set `EXTERNAL_GEO=true`** | `ip-api.com` |

`EXTERNAL_GEO` is **off by default**. Turning it on sends each visitor IP to
ip-api.com — a third party, in the United States, over plain HTTP, because their free
tier offers no TLS. An IP address is personal data; leave it off unless you have
decided that trade is one you want to make, and tell your visitors if you turn it on.

There is no telemetry, no phone-home, no usage reporting and no research data
collection in HWS. None exists in the code.

---

## Data and privacy

- IP addresses are **hashed** with a per-site salt — never stored in plain text
- Raw events retained for **90 days** by default, configurable in `settings.env`
- Daily aggregates kept indefinitely
- Export: `GET /api/admin/export/events?format=csv`
- Delete: `DELETE /api/admin/purge/old-events` (admin only)

---

## Dashboard

| Page | What it shows |
|---|---|
| Overview | Stats, traffic chart, top pages, countries |
| Intelligence | Auto-detected patterns, anomalies, trend alerts |
| Walk detection | Catalogue walks and what they took |
| Real-time | Live event stream |
| Geography | Globe + country breakdown |
| Pages | Pages ranked by traffic share |
| Devices | Device type and browser breakdown |

---

## Licence

**AGPL-3.0-or-later** for the core — see [LICENSE](LICENSE), and [LICENSES.md](LICENSES.md)
for which licence covers which component.

Built by [JotNotes](https://jotnotes.com).
