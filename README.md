# Higashi Interactive Analytics

**The dots connect themselves.**

A self-hosted, privacy-first analytics platform for AI-native websites, static sites, and modern digital ecosystems. Open source under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) — you own your data, always.

The embeddable browser tracker (`tracker/`) and the shared reading rules (`backend/higashi_reading/`) are MIT licensed, so putting the tracker on your site places no obligation on it. Higashi Live, the paid hosted service, is proprietary. See [LICENSES.md](LICENSES.md) for the boundaries and [TRADEMARK.md](TRADEMARK.md) for the name and logo.

---

## What makes this different

Most analytics tools show you what happened. This one tells you why it matters.

- **Intelligence layer** — automatic anomaly detection, geo spikes, traffic trends, dead pages, and new source alerts
- **Session flow maps** — Sankey diagrams showing how visitors actually navigate your site
- **Cinematic visualization** — 3D rotating globe, live visitor feed, real-time activity stream
- **Privacy by design** — IPs are hashed, never stored raw. Runs entirely on your own server.
- **No SaaS dependency** — your data never leaves your infrastructure

---

## Quick Start (Docker)

```bash
git clone https://github.com/higashi-interactive/analytics.git
cd analytics
cp .env.example .env
# Edit .env — set a real SECRET_KEY and your DB password
docker-compose up -d
```

Open `http://your-server:3000/setup` and follow the 3-step wizard.

You'll get a tracker snippet like:

```html
<script src="https://your-server:8000/tracker.js" data-key="YOUR_KEY" async></script>
```

Paste it into the `<head>` of every page you want to track.

---

## Manual Install (Linux)

### Requirements
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Node.js 20+ (for frontend build)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run build
# Serve /dist with nginx — see frontend/nginx.conf for config
```

### Cron (data retention)

Add to crontab to auto-purge events older than your retention window:

```
0 3 * * * /path/to/venv/bin/python /app/scripts/retention_cleanup.py >> /var/log/higashi-retention.log 2>&1
```

---

## Dashboard

| Page | What it shows |
|---|---|
| Overview | People, Automated and Looked-wrong side by side, then who fetched your site and what they took, then the trend and breakdowns |
| Intelligence | Auto-detected patterns, anomalies, and trend alerts |
| Real-time | Live visitor stream, updates every 5 seconds |
| Session Flow | Sankey diagram of how visitors navigate |
| Geography | 3D globe + country breakdown |
| Pages | All pages ranked by traffic share |
| Sources | Channel breakdown (search, social, referral) + pie chart |
| Devices | Device type + browser bar chart |

---

## Data & Privacy

- Raw events retained for **90 days** by default (configurable in `.env`)
- Daily aggregates kept **forever**
- IP addresses are **hashed** with a per-site salt — never stored in plain text
- Export your data anytime: `GET /api/admin/export/events?format=csv`
- Delete data: `DELETE /api/admin/purge/old-events` (admin only)

---

## Tracker Reference

The tracker snippet is ~2KB, has no dependencies, and works on any site — static HTML, React, Vue, WordPress, or anything else.

**Options (data attributes on the script tag):**

| Attribute | Default | Description |
|---|---|---|
| `data-key` | required | Your site tracker key from the setup wizard |
| `data-api` | `/api/collect/pageview` | Override the collection endpoint URL |

**What it captures automatically:**
- Page URL, title, referrer
- Screen size, language
- Scroll depth (0–100%)
- Time on page
- Web Vitals (LCP, FCP, TTFB)
- SPA navigation (React Router, Vue Router, etc.)

---

## API

Full API docs available at `http://your-server:8000/docs` after starting the backend.

Key endpoints:

```
POST /api/collect/pageview     — receive tracker events (public)
GET  /api/analytics/overview   — summary stats
GET  /api/analytics/timeseries — daily traffic series
GET  /api/intelligence/insights — auto-detected patterns
GET  /api/intelligence/realtime — SSE live event stream
GET  /api/admin/export/events  — download raw events (admin)
GET  /api/admin/storage        — storage usage stats (admin)
```

---

## Use Cases

**stevenhigashi.com** — personal site tracking, baseline dashboard testing

**cloudanalyst.net** — AI content site, content intelligence, article performance analysis

---

## Roadmap

- [x] v0.1 — Core tracking, dashboard, setup wizard, Docker deploy
- [x] v0.1 — Intelligence layer (anomaly detection, insights)
- [x] v0.1 — Session flow (Sankey), geo globe, real-time feed
- [ ] v0.2 — Heatmap overlay, concurrent users, session replay concepts
- [ ] v0.2 — Multi-site desktop app (Tauri, paid)
- [ ] v0.3 — Predictive analytics, AI conversational queries
- [ ] v0.4 — Historical archive cloud service (paid)

---

## Configuration

Everything is environment variables. Copy [`.env.example`](.env.example) to
`backend/.env` and edit — it documents every name the application reads, and the
application rejects names it does not recognise, so a typo fails loudly at startup
rather than quietly at runtime.

The ones that matter on a first run:

| Variable | What it does |
|---|---|
| `DATABASE_URL` | SQLite by default, so nothing to install. Postgres if you prefer. |
| `SECRET_KEY` | Signs sessions and encrypts saved log-source credentials. Generated on first start if left as the placeholder. **Changing it later signs everyone out and makes saved credentials unreadable.** |
| `SITE_DOMAIN`, `SITE_NAME` | The first site you will track |
| `ADMIN_EMAIL` | Who administers this install |
| `DASHBOARD_URL` | Where the dashboard itself is served — used for password-reset links. Not a site you track. |

AI is optional. With no key at all, Higashi still explains crawler activity using
fixed rules that run locally. A key adds the chat and model-written prose; the rules
stay the ceiling either way.

### Importing access logs

Higashi can read server access logs as well as, or instead of, the browser tracker —
useful because crawlers frequently do not run JavaScript. Point it at logs with
`LOG_SOURCES`, semicolon-separated:

```
LOG_SOURCES=My site|example.com|/var/log/nginx/example.access.log
```

Each entry is `label|domain|path`, and may carry its own credentials when one source
differs from the rest: `label|domain|path|username|password`. `SFTP_HOST`,
`SFTP_PORT`, `SFTP_USER` and `SFTP_PASSWORD` are the shared connection defaults.

Leave `LOG_SOURCES` empty to upload logs by hand instead.

---

## Adding a site

1. Sign in and open **Import Data → Sites**, or complete the first-run wizard.
2. Copy the snippet it gives you — it carries that site's tracker key.
3. Paste it before `</body>` on the site you want to measure.

The tracker key is not a secret: it identifies a site, it is visible in your page
source, and it grants nothing but the ability to report a page view.

---

## Upgrading

```bash
git pull
cd backend && pip install -r requirements.txt   # new dependencies
cd ../frontend && npm ci && npm run build       # rebuild the dashboard
# restart however you run it (systemd, docker compose, supervisor)
```

Database migrations run themselves at startup, in order, and are safe to re-run.
Back up your database first anyway — it is one file if you are on SQLite.

If the application refuses to start after an upgrade complaining about an unknown
setting, a variable was renamed: compare your `backend/.env` against
[`.env.example`](.env.example) and remove anything no longer listed.

---

## Troubleshooting

**No data appears.** Check the snippet is on the page and the key matches the site
(view source and look for `data-key`). Open the browser console — a blocked request
shows there. Ad blockers do not usually block a self-hosted tracker, but a strict
Content-Security-Policy will.

**The dashboard is slow on a small VPS.** Expected on one core with a large database:
the window queries scan a lot of rows. [docs/PERFORMANCE_AND_SIZING.md](docs/PERFORMANCE_AND_SIZING.md)
explains how to tell a hardware problem from a software one, with measured numbers —
and why the answer is usually not a bigger server.

**"Extra inputs are not permitted" at startup.** Your `.env` has a name the
application does not read. See Upgrading above.

**Crawlers are missing from the numbers.** Most do not run JavaScript, so the browser
tracker never sees them. Configure `LOG_SOURCES` to read your access logs.

**Logs import but pageviews stay at zero.** Check the log path and that the format is
one Higashi parses — combined/common nginx and Apache formats are supported.

---

## Development

```bash
# Backend, with reload
cd backend && ../.venv/bin/python -m uvicorn main:app --reload --port 8010

# Frontend, pointed at it
cd frontend && VITE_HIGASHI_API_URL=http://localhost:8010 npm run dev

# Tests
cd backend && ../.venv/bin/python -m pytest tests -q
```

Contributions to the AGPL core are accepted under AGPL-3.0-or-later; contributions to
`tracker/` or `backend/higashi_reading/` under MIT. Say which you intend.

If you are adding a control that is supposed to prevent something, break it first and
check that a test fails. A test that has never failed has not been shown to work.

---

## Licence

Three licences, on purpose. [LICENSES.md](LICENSES.md) is the map; each component
also carries its own notice.

| Part | Licence |
|---|---|
| The application — `backend/`, `frontend/`, `server/`, `softaculous/` | **AGPL-3.0-or-later** ([LICENSE](LICENSE)) |
| The browser tracker — `tracker/` | **MIT** |
| The shared reading rules — `backend/higashi_reading/` | **MIT** |

**Embedding the tracker on your website places no licence obligation on your site.**
That is why it is MIT rather than AGPL — you should not have to think about it.

**Running Higashi for yourself asks nothing of you either.** AGPL only has something
to say if you modify Higashi and offer it to other people over a network: then those
users must be able to get your modified source. It keeps hosted forks open. If that
does not suit you, a commercial licence is available — ask.

The name, logo and product identity are not covered by any of these. See
[TRADEMARK.md](TRADEMARK.md).

---

## Higashi Live

Higashi Live is a paid hosted service, and it is **not** in this repository. It is
separate, proprietary software.

Everything Higashi does on its own is here and free: it detects crawler activity and
explains it in plain language using deterministic rules that run on your own box,
with no account and no key. Live adds what only a service can have — history across
weeks, comparison against other sites of your size and type, a managed model, a
weekly email, and centrally maintained crawler ranges.

The code in this repository that *talks* to Live is here and open
(`backend/routers/live.py`, `backend/services/live_client.py`, the dashboard's Live
card), so you can read exactly what an install would send before deciding to use it.
It sends counts, crawler names and a verdict — never IPs, paths, URLs, user agents
or page content, and a validator rejects anything that looks like one.

Leave `LIVE_KEY` empty and none of it runs.

---

Built by [Higashi Interactive](https://stevenhigashi.com)
