# Contributing to Higashi

Thanks for looking. This is a small project with one maintainer, so the most
useful thing you can do before writing code is open an issue and say what you
intend — it takes five minutes and it is cheaper than a rejected pull request.

**Security problems do not go in an issue.** See [SECURITY.md](SECURITY.md).

---

## Which licence your contribution lands under

Higashi is not one licence, and where your change lands decides which one
applies. [LICENSES.md](LICENSES.md) is the full map; the short version:

| If you change… | your contribution is accepted under |
|---|---|
| `backend/` (except `backend/higashi_reading/`), `frontend/`, `server/`, `softaculous/` | **AGPL-3.0-or-later** |
| `backend/higashi_reading/` | **MIT** |
| `tracker/` | **MIT** |

There is no CLA to sign and no copyright assignment. You keep your copyright;
you are licensing the change under the licence that already governs the file
you touched.

Say which you intend in the pull request. If your change spans both — say a
rule in `higashi_reading/` plus the dashboard code that displays it — say so
explicitly, because the two halves land under different licences.

One boundary matters enough to state on its own: **`backend/higashi_reading/`
must not import from the rest of the backend.** It is a standalone package —
today it imports nothing but the standard library and pydantic — and it is
shared verbatim by the free product and the paid service. That is what makes
the product promise true: a Live reading and a local reading of the same data
agree because they are the same code. If your change needs the database or
the network, it belongs on the other side of that line.

Worth knowing before you rely on it: **nothing currently enforces that.**
`tests/test_layer_boundary.py` guards a different seam (walk detection), and
no test fails if `higashi_reading/` grows an import into `models/` or
`services/`. A test that walks the package's imports and refuses anything
outside the standard library and pydantic would be a genuinely useful first
contribution.

## Setting the project up

```bash
git clone https://github.com/SteveHigashi/higashi-analytics.git
cd higashi-analytics

python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-minimal.txt
.venv/bin/python -m pip install "pytest>=9,<10" "pytest-asyncio>=1,<2"

cd frontend && npm install
```

`requirements-minimal.txt` is the SQLite set, and it is what the tests and CI
use — the suite never touches PostgreSQL. `requirements.txt` is the production
set with the PostgreSQL drivers; install that one instead if you are working
on something that needs a real Postgres.

## Running the tests

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
SECRET_KEY="anything-non-empty-for-tests" \
../.venv/bin/python -m pytest tests -q
```

Both environment variables are required. `config.py` defaults `database_url`
to a PostgreSQL URL, and several test modules build an engine at import time,
so without `DATABASE_URL` the suite fails during collection rather than
failing a test — which looks alarming and is not.

The frontend has no test suite yet. `npm run build` is the check, and CI runs
it.

## The house rule: break it first

**If you add a control that is supposed to prevent something, break it and
check that a test fails.**

This is the one process rule here and it is not a formality. A test that has
never failed has not been shown to work — it has only been shown to pass,
which is also what a test asserting nothing does. Every defence in this
repository was broken on purpose once, with the matching test observed going
red, before it was trusted.

It has caught real things. On 2026-09-23 a deploy check went green while the
service it was checking was broken, because the check's own payload did not
carry the field that was failing. The suite was 33 green throughout an outage.

So: write the test, watch it fail for the reason you expect, then make it
pass. Say in the pull request which control you broke and what failed. If you
cannot make the test fail, the test is not testing the control.

Two corollaries that have each cost a day:

- **A harness is not the page.** Checking a component in an isolated preview
  does not prove the real page loads it. An undefined import is a runtime
  error, not a build error, and `npm run build` will not catch it.
- **Assert on every edit.** A find-and-replace anchored on a line that does
  not exist changes nothing and reports nothing. The build still passes.

## Pull requests

- One subject per pull request. A refactor bundled with a fix is two reviews.
- Say what you broke to prove the test works (above).
- Run the backend suite and `npm run build` before pushing. CI runs both on
  every push and pull request, so you will find out either way — finding out
  locally is faster.
- Match the surrounding code. The backend is FastAPI with SQLAlchemy 2.x async
  and explicit `select()` calls; the frontend is React with Tailwind and
  Zustand. There is no formatter to run and no lint config to satisfy.
- Comments here explain *why*, not *what*. The interesting ones record a
  decision or a defect that shaped the code, so that nobody undoes it by
  accident. If you find yourself writing one of those, write it.

## User-facing writing

Strings a user reads are part of the product. Plain sentences, no jargon, and
no claiming something the software does not do.

Higashi reports on crawler activity. **It does not enforce anything** — it
cannot block a crawler, because it is not in the request path. A reading that
says a crawler "will not be able to fetch pages" is false, and there is a test
that refuses one. If your change touches the wording of a reading, read
`backend/higashi_reading/prompt.py` first.

## What is likely to be turned down

- Adding a tracking signal that identifies an individual. The privacy line is
  the product, not a setting.
- Anything that makes `backend/higashi_reading/` depend on the database or the
  network.
- Making the paid service a requirement for something the free product does
  today.
- A large refactor that arrives without a preceding issue.

## Code of conduct

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — the Contributor Covenant, which
applies to issues, pull requests and any other project space.
