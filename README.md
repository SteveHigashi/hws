# Higashi Interactive Analytics

**The dots connect themselves.**

A self-hosted, privacy-first analytics platform for AI-native websites, static sites, and modern digital ecosystems. Open source, MIT licensed — you own your data, always.

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
| Overview | Stats, traffic chart, top pages, countries, live insights |
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

## License

MIT — see [LICENSE](LICENSE)

Built by [Higashi Interactive](https://stevenhigashi.com)
