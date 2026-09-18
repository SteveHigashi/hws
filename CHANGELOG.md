# Changelog — Higashi Interactive Analytics

Visual screenshots are stored in `/screenshots/` and linked inline below.
Format: version · date · what changed · why it matters.

---

## Screenshots — v0.1.0 (2026-05-13)

All 13 screens captured from live dev server on first run.

| Screen | Description |
|---|---|
| ![Login](screenshots/login.png) | Login — dark centered form, HIGASHI ANALYTICS pulse branding |
| ![Setup Step 1](screenshots/setup-welcome.png) | Setup wizard step 1 — 4-step progress bar, welcome card |
| ![Overview](screenshots/dashboard-overview.png) | Overview — 8 stat cards, traffic chart, intelligence + realtime strips |
| ![Intelligence](screenshots/dashboard-intelligence.png) | Intelligence — insight feed with severity colors, raw signals table |
| ![Real-time](screenshots/dashboard-realtime.png) | Real-time — live SSE feed, "connecting…" state, active now panel |
| ![Session Flow](screenshots/dashboard-flow.png) | Session Flow — Sankey placeholder (renders with real traffic data) |
| ![Geography](screenshots/dashboard-geo.png) | Geography — globe container + country breakdown table |
| ![Pages](screenshots/dashboard-pages.png) | Pages — sortable table with PAGE / VIEWS / TRAFFIC SHARE columns |
| ![Traffic Sources](screenshots/dashboard-sources.png) | Traffic Sources — channel pie + top referrers breakdown |
| ![Campaigns](screenshots/dashboard-campaigns.png) | Campaigns — UTM attribution table + search queries list |
| ![Devices](screenshots/dashboard-devices.png) | Devices — device type bars + browser horizontal chart |
| ![Errors & Exits](screenshots/dashboard-errors.png) | Errors & Exits — 404 list with ✓ clean state + exit pages |
| ![Behavior](screenshots/dashboard-behavior.png) | Behavior — rage clicks, dead clicks, text selections, form abandonment, JS errors |

---

## v0.2.2 — 2026-05-14

### GEO Visibility — brand mention tracking in AI-generated answers

**New page: GEO Visibility** (`/dashboard/geo-visibility`)
- Admin defines up to 5 "probe queries" per site (e.g. "best self-hosted analytics for privacy")
- Each probe asks the configured AI model and checks whether the site's brand name appears in the response
- Distinguishes between being *indexed* by AI crawlers (tracked on AI Crawlers page) and being *recommended* — the gap no GEO tool fills without real traffic data
- Context note on page links to AI Crawlers data and explains the correlation

**New: `geo_probe_queries` table** — query text, brand name to detect, active flag, last_run_at

**New: `geo_probe_results` table** — ran_at, mentioned bool, excerpt (sentences containing brand name), full response, model, tokens, cost

**New: `/api/geo-probes/` endpoints**
- `GET /queries` — list probes with mention_rate, last result, result count
- `POST /queries` — create probe (max 5 per site enforced)
- `DELETE /queries/{id}` — admin only
- `GET /results?probe_id=&days=` — full result history for trend chart
- `POST /run` — run all active probes (or one) immediately, logs AI usage + cost

**Probe card UI**
- Green/grey dot: latest mentioned state
- Mention rate % badge (green >50%, amber >20%, grey otherwise)
- Latest excerpt shown in green italic when mentioned
- "History" toggle reveals step-line chart (recharts) + chronological result list with excerpts
- Per-card "Run" button + "Run all probes now" button at top
- Summary strip: probe count, mentions/total, average mention rate

**Cost transparency:** every probe run logs to `ai_usage_log`, respects monthly budget gate

---

## v0.2.1 — 2026-05-14

### Claude-enriched insights — cost engine, model transparency, options-framing

**New: `POST /api/intelligence/enrich`**
- Takes the full list of rule-detected insights, sends them to Claude in a single batched call
- Returns each insight augmented with `interpretation` (what caused it) and `options` (2-3 possible approaches, ordered low→high effort)
- Deliberately never gives a single directive — presents options so the site owner makes the final call
- Gracefully returns raw insights if no API key is set or budget is exceeded

**New: Cost engine — `ai_usage_log` table**
- Every AI API call logs: endpoint, model, input tokens, output tokens, estimated cost USD
- Token counts come from actual API usage response (not estimated)
- Budget gate: if monthly spend ≥ budget cap, enrichment stops for the rest of the month

**New: Model catalog — `services/ai_cost.py`**
- Claude Haiku 4.5 ($0.80/$4.00 per MTok) — fast, cost-efficient, default
- Claude Sonnet 4.6 ($3.00/$15.00 per MTok) — balanced depth
- Claude Opus 4.7 ($15.00/$75.00 per MTok) — maximum depth
- `estimate_cost(model, input_tokens, output_tokens)` used server-side before logging

**New: Admin AI settings — `/api/admin/settings/ai/`**
- `GET /models` — returns full model catalog with quality descriptions, pricing, and which is default
- `POST /budget` — set monthly budget cap (USD) and default enrichment model, persisted to `.env`
- `GET /usage` — current month spend, call count, budget remaining

**New: AI Enrichment Settings panel (Intelligence page, admin only)**
- Collapsed by default — shows active model + monthly spend in header
- Expands to: usage bar (color shifts warn→danger as budget fills), three model cards side-by-side with quality tier badge, description, and cost-per-MTok
- Click any model card to switch default (saved immediately)
- Budget input with Save button; helper text explains 0 = no limit
- Non-admins see enriched insights but never see the settings panel (RBAC via existing admin/viewer JWT roles)

**Dashboard overview** — also chains enrich after insights load; enriched cards show "Possible approaches" section with options

**Multi-provider AI support**
- All 7 models across 3 providers available for enrichment and chat: Claude Haiku/Sonnet/Opus (Anthropic), GPT-4o/GPT-4o-mini (OpenAI), Gemini 1.5 Flash/Pro (Google)
- `services/ai_providers.py` — provider-agnostic router: `call_model()` (sync) + `stream_model()` (async generator), routes to correct SDK based on model ID
- `POST /api/admin/settings/ai/provider-key` — add/update key for any provider
- `DELETE /api/admin/settings/ai/provider-key/{provider}` — remove key
- Model cards show which provider is configured (green dot) and disable unconfigured ones
- `/enrich` and `/ask` both route through the provider abstraction — switching model switches provider transparently
- `requirements.txt` updated: `openai>=1.30.0`, `google-generativeai>=0.7.0`

---

## v0.2.0 — 2026-05-14

### Claude-powered "Ask your data" chat — the primary differentiator

**Architecture philosophy locked:**
Rule-based detection (fast, free, always-on) surfaces signals. Claude interprets them with industry context. No other self-hosted analytics tool does this. The LLM layer is additive — the tool works without it.

**New: Intelligence → Ask your data chat panel**
- `POST /api/intelligence/ask` — streaming endpoint (plain text SSE)
- Gathers real DB context per request: traffic stats, top 10 pages, top referrers, top countries, device split, all detected anomalies
- Calls `claude-sonnet-4-6` with prompt caching on the context block (reduces cost on repeat questions within 5 minutes)
- Streams response back to browser in real time
- System prompt instructs Claude to be direct and actionable, not hedge-y
- Chat UI in Intelligence page: suggested starter questions, message history, streaming indicator

**New: Admin API key management (no .env editing required)**
- `GET /api/admin/settings/ai` — returns `{configured, key_preview}`, never the full key
- `POST /api/admin/settings/ai` — validates key against Anthropic API first, then writes to `.env` via python-dotenv, clears settings cache
- `DELETE /api/admin/settings/ai` — removes key
- All endpoints are admin-role only

**New: Inline key setup UI on Intelligence page**
- Admins see a "Save & Verify" form with a password-type input when no key is configured
- Key is validated before saving — shows human-readable error if rejected by Anthropic
- After saving, masked preview shown in header (e.g. `sk-ant-api03-...xxxx`)
- Non-admins see a plain "contact your admin" message instead
- "Remove key" action with confirmation dialog

**Security posture:**
- Key stored server-side only, never in browser localStorage or returned in API responses
- Admin auth required on all key endpoints
- Password-type input (not visible in browser)
- Validated against Anthropic before persisting
- HTTPS required in production (documented inline)

---

## v0.1.0 — 2026-05-13

### First working scaffold. Everything below was built in one session.

---

### Foundation decisions locked

| Decision | Choice |
|---|---|
| License | MIT |
| Deployment | One install per site |
| Auth | Admin + Viewer roles (JWT) |
| Data | Server-side only, never leaves your infrastructure |
| Raw event retention | 90 days configurable, aggregates forever |
| Install methods | Docker Compose, RPM, DEB, setup wizard |
| Monetization path | Free tracker → Paid desktop multi-site app → Future cloud archive |

---

### Backend

**New: Core FastAPI application**
- Async Python 3.12 + SQLAlchemy 2.0
- PostgreSQL primary store, Redis for caching and real-time
- Auto-creates all tables on first boot via `init_db()`

**New: Data models**
- `events` — every pageview with 30+ fields: geo, device, browser, UTM, scroll depth, Web Vitals, 404 flag, search query, anchor
- `sessions` — reconstructed from events: entry/exit page, bounce, duration, page count, returning visitor, UTM attribution
- `users` — admin and viewer roles, JWT auth, bcrypt passwords
- `sites` — one row per tracked domain, unique `tracker_key` per site
- `behavior_events` — high-frequency behavioral signals: clicks, selections, pauses, errors, form interactions, media events

**New: Event collection**
- `POST /api/collect/pageview` — receives tracker payload, hashes IP, resolves geo, reconstructs session, writes event
- `POST /api/behavior/batch` — accepts up to 50 behavioral events at once, detects rage clicks and dead clicks server-side
- Bot filtering via user-agent pattern matching (40+ known bot signatures)
- Geolocation via ip-api.com (swappable to MaxMind for production)

**New: Analytics endpoints**
- `GET /api/analytics/overview` — 8 metrics: views, visitors, sessions, bounce rate, avg duration, pages/session, returning %, 404 count
- `GET /api/analytics/timeseries` — daily views + visitors
- `GET /api/analytics/top-pages` — ranked with avg time on page and avg scroll depth
- `GET /api/analytics/exit-pages` — where visitors leave
- `GET /api/analytics/new-vs-returning` — split with percentages
- `GET /api/analytics/not-found` — 404 URLs ranked by hits
- `GET /api/analytics/utm-campaigns` — source/medium/campaign attribution
- `GET /api/analytics/search-queries` — organic search terms parsed from referrer
- `GET /api/analytics/traffic-sources` — referrer domains
- `GET /api/analytics/geo` — country visitor counts
- `GET /api/analytics/devices` — device type breakdown
- `GET /api/analytics/browsers` — browser breakdown

**New: Intelligence endpoints**
- `GET /api/intelligence/insights` — auto-detected patterns (geo spikes, bounce anomalies, dead pages, new sources, overall trend)
- `GET /api/intelligence/paths` — session navigation reconstructed into Sankey-ready nodes + links
- `GET /api/intelligence/realtime` — SSE stream of live visitor events, updates every 5s

**New: Behavioral analytics endpoints**
- `GET /api/behavior/summary` — event type breakdown
- `GET /api/behavior/rage-clicks` — pages with frustrated repeated clicking
- `GET /api/behavior/dead-clicks` — clicks on non-interactive elements
- `GET /api/behavior/selected-text` — what visitors highlight and copy
- `GET /api/behavior/scroll-attention` — scroll pause zones by page
- `GET /api/behavior/form-abandonment` — which field stops form completion
- `GET /api/behavior/errors` — JavaScript errors experienced by visitors
- `GET /api/behavior/external-clicks` — where you're sending visitors

**New: Admin endpoints**
- `GET /api/admin/storage` — event + session counts, oldest event, retention window
- `GET /api/admin/export/events` — download raw events as CSV or JSON
- `GET /api/admin/export/summary` — download daily aggregates as CSV or JSON
- `DELETE /api/admin/purge/old-events` — delete events past retention window (background task)
- `DELETE /api/admin/purge/date-range` — delete events between two dates
- `DELETE /api/admin/purge/all` — full wipe

**New: Setup API**
- `GET /api/setup/status` — is setup complete?
- `POST /api/setup/initialize` — creates admin user + site, returns tracker snippet

**New: Auth**
- `POST /api/auth/login` — returns JWT
- `POST /api/auth/users` — create user (admin only)
- `GET /api/auth/me` — current user info

**New: tracker.js served publicly**
- `GET /tracker.js` — no auth, loadable by any site, 1-hour cache

---

### Tracker

**New: tracker.js (~4KB, no dependencies)**

Pageview signals:
- Page URL, title, referrer
- UTM parameters parsed from URL (source, medium, campaign, content, term)
- Anchor/fragment detection
- 404 auto-detection (title + meta tag check)
- Screen size, language
- Scroll depth (0–100%)
- Time on page (via visibilitychange)
- Web Vitals: LCP, FCP, TTFB

Behavioral signals (new vs. standard analytics):
- **Clicks** — element tag, ID, class, visible text, position (px + %)
- **External link clicks** — destination URL captured
- **Text selection** — what visitors highlight (reading intent)
- **Copy events** — what visitors copy to clipboard
- **Scroll pauses** — where visitors stop and read (1.5s+ pause threshold)
- **Tab blur / focus** — distraction and return detection
- **Form field tracking** — focus, blur, and abandonment per field
- **Media events** — play, pause, ended with position in seconds
- **JavaScript errors** — message, source file, line number
- **Print events**

Delivery:
- Batches behavioral events (flush every 3s or at 20 events)
- Uses `sendBeacon` for reliable unload delivery
- SPA-aware (intercepts `history.pushState`, listens to `popstate`)

---

### Frontend

**Tech stack**
- React 18 + Vite
- Tailwind CSS with custom dark cinematic design system
- Recharts for standard charts
- D3-sankey for session flow diagrams
- react-globe.gl for 3D geographic visualization
- Zustand for auth state (persisted to localStorage)

**Design system**
- Dark theme: deep navy surface colors (`#080c14` → `#232d42`)
- Accent: electric blue `#3b82f6` with cyan pulse `#22d3ee`
- Cinematic glow effects on cards
- Animated pulse dot for live indicators
- JetBrains Mono for data/code values, Inter for UI

**Dashboard pages (11 total)**

| Page | Route | What it shows |
|---|---|---|
| Overview | `/dashboard` | 8 stat cards, traffic chart, top pages, top countries, insights strip, realtime strip |
| Intelligence | `/dashboard/intelligence` | AI-detected patterns with severity levels |
| Real-time | `/dashboard/realtime` | Live SSE visitor stream |
| Session Flow | `/dashboard/flow` | D3 Sankey navigation diagram |
| Geography | `/dashboard/geo` | 3D rotating globe + country bar chart |
| Pages | `/dashboard/pages` | All pages ranked with traffic share bars |
| Traffic Sources | `/dashboard/sources` | Channel pie + referrer breakdown |
| Campaigns | `/dashboard/campaigns` | UTM attribution + search query list |
| Devices | `/dashboard/devices` | Device type + horizontal browser chart |
| Errors & Exits | `/dashboard/errors` | 404 list + exit pages side by side |
| Behavior | `/dashboard/behavior` | Rage clicks, dead clicks, text selections, form abandonment, JS errors, external clicks |

**Auth flow**
- `/setup` — 3-step wizard: welcome → admin account → site details → snippet
- `/login` — single-field JWT login
- Protected routes redirect to `/login`

---

### Infrastructure

- `docker-compose.yml` — Postgres 16 + Redis 7 + backend + frontend/nginx
- `backend/Dockerfile` — Python 3.12-slim, installs dependencies
- `frontend/Dockerfile` — Node 20 build → nginx alpine serve
- `frontend/nginx.conf` — SPA routing + API proxy to backend
- `.env.example` — all configurable values documented
- `backend/scripts/retention_cleanup.py` — standalone cron script for event purging

---

### Documentation

- `README.md` — quickstart (Docker + manual), tracker reference, API overview, roadmap
- `docs/ARCHITECTURE.md` — all decisions, monetization path, use cases, full phase roadmap

---

## Roadmap

### v0.2 (next)
- [ ] Scroll heatmap overlay on actual page content
- [ ] Concurrent active users counter
- [ ] Email / webhook alerts for anomalies
- [ ] Dashboard widget drag-and-drop layout
- [ ] Returning visitor deep analysis
- [ ] Page-level detail drill-down (click any page → its own mini-dashboard)
- [ ] Traffic pulse animation on overview
- [ ] Globe arc lines between traffic origins
- [ ] GDPR mode toggle (full IP anonymization)
- [ ] Multi-site desktop app foundation (Tauri)

### v0.3
- [ ] Predictive traffic modeling
- [ ] Conversational analytics ("show me visitors from France who read more than 3 articles")
- [ ] Content correlation (article performance vs. engagement signals)
- [ ] Session replay concepts

### v0.4
- [ ] Historical archive cloud service (paid tier)
- [ ] Plugin / extension API

---

*Screenshots: pending first server run — see `/screenshots/` once generated.*
