# Higashi — Complete User Workflow

A walkthrough of every step a user takes, what happens behind the scenes, and what dependencies exist. The goal is to spot anything missing or confusing before more code is written.

---

## Step 1 — User opens the desktop app for the first time

**What the user sees:**
"Looking for Higashi…" (1 second spinner)

**What's happening behind the scenes:**
The app pings localhost on common ports (8000, 8080, 80, 127.0.0.1:8000) looking for a Higashi backend. It does this by calling `/api/health` and checking the response contains a `version` field.

**Dependency:** A Higashi backend must be running. Right now this means the user (or a script) started uvicorn manually. **GAP:** Eventually the desktop app should bundle the backend so this is automatic. For now it's a manual prerequisite.

**Outcomes:**
- Found → next step
- Not found → "Higashi isn't running" with options to connect to a remote server or retry

---

## Step 2 — Login screen

**What the user sees (fresh install):**
"Welcome to Higashi — Set your login. Email + Password. [Create & Sign In]"

**What the user sees (returning user):**
"Sign in to Higashi — Email + Password. [Sign In]"

**What's happening behind the scenes (fresh install):**
1. App calls `/api/setup/initialize` with email, password, and a placeholder site (domain="default", name="My Site")
2. Backend creates an admin user (bcrypt-hashed password) and a default site (auto-generates a `tracker_key`)
3. App then calls `/api/auth/login` with the same credentials, gets back a JWT
4. JWT is stored in Tauri's secure store (per-site)
5. App auto-opens the dashboard

**What's happening behind the scenes (returning user):**
1. App calls `/api/auth/login`, gets back JWT
2. JWT stored
3. Dashboard opens

**Dependency:** Backend must be reachable, must have either zero admins (for setup) or matching credentials (for login).

**GAP:** Right now the desktop app stores credentials as a "site" entry per backend URL. If the user has only one backend, they have one site entry. But the BACKEND itself supports multiple tracked websites under one login. That's a confusing overlap — see Step 4.

---

## Step 3 — Dashboard opens

**What the user sees:**
The full Higashi web dashboard (Overview, Intelligence, AI Crawlers, Real-time, Session Flow, Geography, Pages, Traffic Sources, Campaigns, Devices, Errors & Exits, Behavior, Import Data).

**What's happening behind the scenes:**
The desktop app opens a Tauri WebviewWindow pointing at the backend's `/dashboard` route. Before the page loads, Tauri injects an `initialization_script` that writes the JWT into `localStorage['ha-auth']` so the frontend's auth state picks it up automatically without a re-login.

**Dependency:** The backend serves both the API and the frontend SPA from the same origin.

---

## Step 4 — User has multiple websites to track

**This is the part you raised — let's get it right.**

**The conceptual model that should match user expectations:**
- One Higashi backend = one "install"
- One install can track many websites (each gets its own `tracker_key`)
- The user logs in once and sees all their sites
- Switching between sites should feel like switching browser tabs

**Current implementation:**
The web frontend already has a site selector in `siteStore.js` and most analytics endpoints accept a `site_id` query parameter. The dropdown in the sidebar lets the user switch which site they're viewing. That part works.

**The desktop app's current model (the problem):**
The desktop app treats each *backend* (each install) as a "site card." So if the user has one backend with three tracked websites, the desktop app shows one card, and they have to open the dashboard to switch between the three sites inside it. That's confusing.

**The better model — per the user's "tabs" idea:**
The desktop app should:
1. After login, call `/api/analytics/sites` (or similar) to fetch the list of websites under that account
2. Show each website as its own card/tab on the main screen
3. Each tab has its own quick-stats summary (page views, AI visibility, etc.)
4. Each tab has: [Open Dashboard] [Update Data] [Import Data] [Tracker Code]
5. Clicking a tab opens its specific dashboard view

**GAP:** There is currently no `/api/analytics/sites` endpoint that returns the list of sites for the logged-in user. Need to add one.

---

## Step 5 — Per-site actions: Update / Import / Tracker

**What the user sees on each site tab:**
A card with:
- Site name & domain
- 4 key stats (Page Views 30d, AI Visibility, Bot Visits, AI Crawlers)
- Status indicator (online / offline / token expired)
- Buttons: **Open Dashboard** · **Update Data** · **Import Logs** · **Tracker Code**

**What each button does:**

**Open Dashboard** — Opens the full web dashboard for this site (Tauri WebviewWindow with JWT injection, site_id pre-selected in localStorage).

**Update Data** — Triggers an immediate refresh. Calls `/api/analytics/overview` and refreshes the card's stats. This is just polling — data automatically appears as visitors hit the site (via the tracker).

**Import Logs** — For users who want to backfill historical data from server logs. Calls `/api/admin/import` endpoints with a file upload. Supports Apache/Nginx/Cloudflare log formats. This is for power users.

**Tracker Code** — Shows the JavaScript snippet the user pastes into their website's `<head>`. The snippet contains the site's unique `tracker_key`. One-click copy.

**Dependencies:**
- Tracker code must be installed on the user's actual website for any data to flow
- Import requires log files in a recognized format
- Update is just a poll — assumes tracker has been collecting

---

## Step 6 — Adding another website to track

**What the user sees:**
"+ Add Website" button in the main app. Modal with one field: "Website domain (e.g. mysite.com)". Click Add.

**What's happening behind the scenes:**
1. App calls a new endpoint (NEEDS TO BE BUILT): `POST /api/sites` with `{domain, name}`
2. Backend creates a new Site row with a fresh `tracker_key`
3. App immediately shows the tracker snippet for the new site

**GAP:** This endpoint doesn't exist yet. The web frontend has it via setup wizard, but no general "add another site" flow exists.

---

## Step 7 — AI features: API keys & cost tracking

**What the user sees:**
A "Settings" section (already partially built — `AISettingsPanel` in `Intelligence.jsx`) with:
- API key management (Anthropic, OpenAI, Google)
- Monthly budget cap
- Spend-so-far meter
- Default model selector (Haiku for cheap, Sonnet for balanced, Opus for premium)

**What's happening behind the scenes:**
Keys are validated against each provider before saving, then written to the backend's `.env` file. Usage is logged per-request in an `ai_usage` table with token counts and dollar cost.

**Dependency:** Without at least one API key configured, the "Ask your data" chat doesn't work — but everything else (dashboards, rule-based insights, AI crawler tracking) still does.

---

## Backend dependencies summary (the things that have to exist)

| What | Endpoint | Used for | Status |
|---|---|---|---|
| Health check | `GET /api/health` | Desktop discovers backend | ✓ Exists |
| Setup status | `GET /api/setup/status` | Desktop knows if first-run | ✓ Exists |
| Initial setup | `POST /api/setup/initialize` | Create admin + first site | ✓ Exists |
| Login | `POST /api/auth/login` | Returns JWT | ✓ Exists |
| List user's sites | `GET /api/sites` | Multi-site tab UI | **MISSING** |
| Create another site | `POST /api/sites` | Add additional sites | **MISSING** |
| Get site profile | `GET /api/ai-crawlers/site/profile` | Per-site stats summary | ✓ Exists |
| Get site analytics | `GET /api/analytics/overview` | Dashboard data | ✓ Exists |
| Log import | `POST /api/admin/import/...` | Backfill historical data | ✓ Exists |
| AI settings | `GET/POST /api/admin/settings/ai*` | Configure AI keys/budget | ✓ Exists |

**Two missing endpoints** (small, ~30 lines each):
1. `GET /api/sites` — return all sites the logged-in user can access
2. `POST /api/sites` — create a new site under the logged-in user

---

## What's normal vs. what's a gap

**Normal for an analytics tool:**
- Tracker code must be manually installed by the user. This is universal — Google Analytics, Plausible, Fathom all require it.
- Per-site `tracker_key` so events are correctly attributed.
- Cookie-less / privacy-friendly tracking via IP hashing (already implemented).
- Multi-site under one login (already supported by the data model, just not exposed in the desktop UI yet).

**Gaps in our current build:**
1. **Backend isn't bundled with desktop app** — user must manually start uvicorn. Fix: PyInstaller sidecar (see `strategy/ONBOARDING_STRATEGY.md`).
2. **No `/api/sites` endpoints** — desktop app can't show multi-site tabs cleanly.
3. **Tracker code shown only at first-run setup** — should be accessible from every site's tab so users can re-copy it.
4. **No connection test after tracker install** — user pastes the code but doesn't get a "✓ Tracker is working" confirmation.
5. **Import UI exists but isn't surfaced in the desktop app** — users wouldn't know they can backfill historical data.
6. **No per-site site_id passed to the dashboard webview** — opens generic dashboard, user has to manually switch via the sidebar dropdown.

---

## Recommended next steps in priority order

1. **Add `GET /api/sites` and `POST /api/sites` backend endpoints** (~30 min)
2. **Replace desktop "site cards" with per-website tabs** that show stats and the three action buttons (Open / Update / Import) + Tracker Code modal (~1-2 hours)
3. **Pass site_id when opening the dashboard webview** so the right site is preselected (~15 min)
4. **Add a "Test tracker" button** that polls for the first event from a new site and confirms detection (~30 min)
5. **Bundle the backend** (PyInstaller + Tauri sidecar — bigger change, day or two)

---

## What I might still be missing

Things worth thinking about before we build:
- **Tracker installation help per platform** — WordPress, Squarespace, Wix, Shopify each have a different way to add a `<script>` tag. Should we show platform-specific instructions?
- **What happens if the user deletes a site** — does historical data get purged or archived?
- **What does "Update Data" actually do** — currently this is a polling refresh. Should it also re-run intelligence/insight detection? Re-query AI models for GEO scores?
- **Tab order / favorites** — if a user tracks 10 sites, which one opens by default?
- **Per-site notifications** — if traffic drops 50% on one site, the desktop app should probably notify them. Native macOS/Windows notifications via Tauri.

If any of these feel important, flag them and we'll fold them in. If they feel like noise, we ignore them.
