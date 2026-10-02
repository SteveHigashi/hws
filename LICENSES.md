# Which licence applies to what

Higashi is not licensed under a single licence. Three different things live in this
repository and they are licensed differently on purpose. This file is the map; each
component also carries its own notice so you do not have to come back here.

| Component | Path | Licence |
|---|---|---|
| **Higashi core** — the self-hosted analytics application | `backend/`, `frontend/`, `server/`, `softaculous/`, `docker-compose.yml`, `build-backend.sh` | **AGPL-3.0-or-later** (`LICENSE`) |
| **Shared reading rules** | `backend/higashi_reading/` | **MIT** (`backend/higashi_reading/LICENSE`) |
| **Browser tracker** — the snippet you embed in your own site | `tracker/` | **MIT** (`tracker/LICENSE`) |
| **Higashi Live** — the paid hosted service | not in this repository | **Proprietary** — all rights reserved |
| **Name, logo and brand** | — | Not licensed by any of the above. See `TRADEMARK.md`. |

## Why the tracker is MIT

`tracker/tracker.js` is copied into other people's websites. If it were AGPL, a site
owner embedding it could reasonably worry about what that means for their own site.
It is MIT so that question never arises: **embedding the Higashi tracker places no
licence obligation on your website whatsoever.**

Running the Higashi *server* is a different matter — that is the AGPL part.

## Why `higashi_reading` is MIT

`backend/higashi_reading/` holds the deterministic rules that turn crawler activity
into a plain-language reading. Both the free self-hosted product and the paid Higashi
Live service run the *same* rules — that is a deliberate product promise, so that a
Live reading and a local reading of the same data agree.

Keeping one copy is what makes that promise true. Two copies drift, and on
2026-09-23 exactly that happened: the copies fell out of step and Live rejected every
report for several hours. So the package is MIT, and both sides import it.

MIT here is a grant, not a loophole. It does not make the rest of the core permissive:
everything outside `backend/higashi_reading/` remains AGPL.

## What AGPL means for you, briefly

If you run Higashi for yourself, on your own machine or server, AGPL asks nothing of
you. You do not have to publish anything.

If you modify Higashi and offer it to other people **over a network** — a hosted
analytics service built on this code — AGPL requires that those users can obtain the
source of your modified version. That is the whole point: it keeps hosted forks open.

If that does not suit you, a commercial licence is available. Ask.

## Contributing

Contributions to the AGPL core are accepted under AGPL-3.0-or-later. Contributions to
`tracker/` or `backend/higashi_reading/` are accepted under MIT. Say which you intend.

## Where Higashi Live lives

Not here. Live is proprietary and has its own repository. It was tracked in this one
until 2026-10-02, which would have published the whole Live implementation the moment
this repository went public; `release.sh` never packaged it, so no released tarball
ever contained it. Higashi keeps only the client code needed to talk to Live.
