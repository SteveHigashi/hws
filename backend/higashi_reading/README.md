# higashi_reading — MIT licensed

**This package is MIT, not AGPL.** See `LICENSE` beside this file. Everything else
under `backend/` is AGPL-3.0-or-later.

It holds the deterministic rules that turn crawler activity into a plain-language
reading: which crawler classes a stance refuses, what counts as a walk, the ceiling on
what may be recommended, and the checks that keep a model's prose inside those rules.

It is MIT because two products run it — the free self-hosted product, and the paid
Higashi Live service. Both must produce the *same* reading from the same data; that is
a promise made to customers. One shared copy is what keeps the promise honest. Two
copies drift, and on 2026-09-23 they did, which is how Live came to reject every
report for several hours.

Being MIT does not make the rest of the core permissive. The boundary is this
directory.

No network calls, no database, no framework beyond pydantic. Pure functions in, text
out — which is also why it is safe to share.
