# Higashi Interactive Analytics — Architecture & Decisions

## Positioning

**Tagline:** "The dots connect themselves."

**What this is not:** Another pretty dashboard.

**What this is:** An analytics intelligence layer that automatically connects patterns across complex data — even when the signals are subtle, sparse, or hiding across multiple dimensions. IBM-level analytical depth with the ease of use of consumer web tools. Self-hosted, privacy-first, visually cinematic.

---

## Locked Decisions

| Decision | Choice | Reason |
|---|---|---|
| License | MIT | Maximum adoption, same philosophy as Jetpack |
| Deployment model | One install per site | Simple, isolated, auditable |
| Authentication | Admin + Viewer roles | Owner manages; clients/team get read-only |
| Data storage | User's own server | Privacy story stays intact |
| Raw event retention | 90 days (configurable) | Balances storage vs. depth |
| Aggregated data | Forever | Long-term trend lines |
| Data cleanup | Export + deletion commands | User controls their own data |
| Installation | Docker, RPM, DEB + setup wizard | Covers all server types |

---

## Monetization Path

1. **Free / open source** — self-hosted tracker, single site, MIT license
2. **Paid desktop app** — multi-site command center, local only, talks directly to your servers
3. **Future: paid cloud archive** — optional off-site storage for historical aggregated data

---

## Use Cases (Internal Test Sites)

### stevenhigashi.com
- Personal site, real traffic
- Tests general-purpose tracking: pageviews, referrers, geo, device breakdown
- Use for: baseline dashboard testing, screenshot demos

### cloudanalyst.net
- AI/tech content site, more sophisticated audience
- Tests content analytics: article performance, scroll depth, return visitor patterns
- Use for: AI insight layer validation, "content intelligence" demos
- Launch story: announce Higashi Analytics on cloudanalyst.net itself

Both sites provide:
- Real traffic patterns (no fake data)
- Credibility ("built by the team running these properties")
- Screenshots and case studies for marketing

---

## Project Goal
Build a self-hosted website analytics platform designed for AI-native websites, static HTML sites, hybrid systems, and future agent-based ecosystems.

The goal is not to replace WordPress plugins like Jetpack. The goal is to create a modern analytics operating layer.

This system should:
- Track visitors and sessions
- Analyze flows and behavior
- Provide advanced visual dashboards
- Support AI-generated insights
- Run independently of WordPress
- Work across multiple websites
- Allow future agent integrations
- Be visually rich and interactive
- Operate in real time where possible

---

## Core Philosophy

Traditional analytics tools were built for blogs, CMS systems, ad funnels, cookie-based tracking, and centralized SaaS platforms.

This platform is designed for AI-native websites, static sites, decentralized ecosystems, privacy-first operation, local/server-side ownership, modular AI integrations, and future autonomous agents.

---

## High Level Architecture

```
Website Visitors
      ↓
Tracking Layer (tracker.js — 2KB, SPA-aware, Web Vitals)
      ↓
Event Collector (FastAPI /api/collect/pageview)
      ↓
Processing Engine (bot filter → geo → session reconstruction)
      ↓
Database / Storage Layer (PostgreSQL + Redis)
      ↓
Analytics Engine (aggregation, timeseries, path analysis)
      ↓
Visualization Layer (React + Recharts → D3/Three.js cinematic layer)
      ↓
Desktop Client / Web Dashboard / AI Agent
```

---

## Current Stack (v0.1)

**Backend**
- Python FastAPI (async)
- PostgreSQL (primary store)
- Redis (sessions, rate limiting, real-time)
- SQLAlchemy 2.0 async ORM

**Frontend**
- React 18 + Vite
- Tailwind CSS (dark cinematic theme)
- Recharts (v0.1 charts — to be upgraded)
- Zustand (auth state)

**Tracker**
- Vanilla JS, no dependencies, ~2KB
- Captures: pageview, scroll depth, Web Vitals (LCP, FCP, TTFB), duration
- SPA-aware (intercepts history.pushState)
- Uses sendBeacon for reliability on unload

**Infra**
- Docker Compose (Postgres + Redis + backend + frontend/nginx)
- RPM / DEB packages planned

---

## Build Phases

### Phase 1 — Core Tracking Engine ✓ (v0.1 scaffold complete)
- [x] JS tracker snippet
- [x] Event collection endpoint
- [x] Session reconstruction
- [x] Bot detection
- [x] Geolocation enrichment (ip-api.com, swap to MaxMind for production)
- [x] PostgreSQL schema: events, sessions, users, sites
- [x] Analytics endpoints: overview, timeseries, top pages, geo, devices, browsers, sources
- [x] JWT auth with admin/viewer roles
- [x] Setup wizard (3-step: account → site → snippet)
- [x] Docker Compose deployment

### Phase 2 — Intelligence Layer (next)
- [ ] AI insight generation ("Traffic from Germany up 340% this week")
- [ ] Anomaly detection
- [ ] Session path reconstruction → Sankey diagrams
- [ ] Real-time visitor feed (WebSocket or SSE)
- [ ] Scroll heatmap data collection
- [ ] Returning visitor intelligence

### Phase 3 — Cinematic Visualization
- [ ] Geographic globe (Three.js or react-globe.gl)
- [ ] Sankey flow diagrams (D3.js)
- [ ] Live visitor map with glowing nodes
- [ ] Traffic pulse animation
- [ ] Heatmap overlay

### Phase 4 — Desktop App
- [ ] Tauri application shell
- [ ] Multi-site panel (paid tier)
- [ ] Local data caching
- [ ] Export engine
- [ ] Screenshot / presentation mode

### Phase 5 — Agent Layer
- [ ] Conversational analytics API
- [ ] Predictive traffic modeling
- [ ] Content correlation (article performance vs. traffic patterns)
- [ ] Scheduled AI summaries

---

## Data Model

### events
Raw pageview events. Retained 90 days by default, then compressed to aggregates.

Key fields: site_id, session_id, timestamp, page_url, ip_hash (not raw IP), country, region, city, browser, os, device_type, scroll_depth, duration_seconds, lcp, fcp, ttfb, is_bot

### sessions
Reconstructed from events. One row per visit sequence.

Key fields: entry_page, exit_page, page_count, duration_seconds, is_bounce, is_returning, referrer_domain

### users
Admin and Viewer roles. JWT auth.

### sites
One row per tracked domain. Contains tracker_key (unique per site, embedded in snippet).

---

## Privacy Model
- Raw IPs are never stored — hashed with site_id salt before write
- GDPR mode: configurable IP anonymization
- All data lives on the user's own server
- Export and deletion tools built in
- Optional cookie-less operation (session ID in sessionStorage, not cookies)

---

## Competitive Differentiation

| Platform | Weakness | How we beat it |
|---|---|---|
| Google Analytics 4 | Bloated, confusing, privacy concerns | Self-hosted, privacy-first, cleaner UX |
| Plausible | Limited depth, weak visualization | AI insights, cinematic visuals, path analysis |
| Matomo | Older UX, heavy interface | Modern dark UI, AI layer, agent-ready |
| Mixpanel | Enterprise pricing, SaaS lock-in | Free, self-hosted, open source |

---

## Questions Deferred
- Should the AI layer run locally (Ollama) or via API (Claude/OpenAI)?
- Should the desktop app support offline replay of historical sessions?
- Plugin architecture for community extensions?
- Should visual dashboards be user-customizable (drag/drop widgets)?
- Multi-tenant hosted version (SaaS) — timing?
