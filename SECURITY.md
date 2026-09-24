# Security

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Mail
**steve@higashi.edu** instead, or use GitHub's private vulnerability reporting
on this repository (Security → Report a vulnerability).

Tell me what you found, how to reproduce it, and what an attacker gets out of
it. A working proof is welcome but not required — a clear description of the
path is enough to start.

You will get an acknowledgement within 72 hours and an assessment within a
week. This is a one-person project, so I will tell you honestly if a fix is
going to take longer than that rather than going quiet. When a fix ships you
get credit in the changelog unless you would rather not be named.

There is no bug bounty. There is no legal threat either: if you are looking at
your own install, or at a test install you set up yourself, you are welcome
here. Do not test against someone else's Higashi instance.

## What is in scope

The code in this repository — the backend, the dashboard, the tracker, the
installer packaging. Higashi Live is a separate hosted service and is not in
this repository; problems there go to the same address.

Out of scope: findings against the demo screenshots, reports that amount to
"this dependency has a CVE" with no path to exploiting it here, and anything
requiring an attacker who already has your server.

## Supported versions

Only `main`. There are no maintained release branches yet, so security fixes
land on `main` and you upgrade by pulling. `README.md` has the upgrade steps.

## Known open issues

These are real and they are not fixed. You do not need to report them; they
are listed here so you can decide whether they matter for your install, and so
nobody wastes a disclosure on something already known.

### The collection endpoints accept anything that knows the tracker key

`POST /api/collect/pageview` and `POST /api/behavior/batch` authenticate the
request by looking up `tracker_key` in the `sites` table and nothing else. The
tracker key is **public by design** — it sits in the script tag in the HTML of
every page it is installed on, where anyone can read it. So anyone who views
your source can post fabricated pageviews, sessions and behaviour events into
your analytics.

What that costs you: wrong numbers. It does not give the sender access to your
data, your account, or your server — the collection endpoints only write, and
they write only to the site the key belongs to.

Plausible and Fathom have the same shape for the same reason. Any analytics
tracker that a browser can run has to carry its credential in public.

The mitigation we intend is an origin allow-list: the `sites` table already
stores `domain`, so the server can refuse a collection request whose `Origin`
header does not match the site the key belongs to. **Be clear about what that
buys.** `Origin` is set by the browser, so it stops a page on another site
from posting to yours, and it stops casual forgery from a browser. It is sent
by the client, so it stops nothing at all from `curl`. Treat it as raising the
cost, not as authentication. Per-key rate limiting is the control that
actually bounds the damage, and it is not written yet either.

If fabricated data would be a problem for you rather than an annoyance, do not
put a Higashi collection endpoint on the public internet without a rate limit
in front of it.

### CORS origins are hardcoded to the author's own sites

`backend/main.py` passes `allow_origins` an explicit list of `viabandwidth.com`
and `cloudanalyst.net` hosts. It is explicit rather than `*` for a good reason
— `navigator.sendBeacon` sends credentials and a browser refuses a wildcard on
a credentialed request — but the list is somebody else's domains. **If you
install Higashi and serve the tracker from your own site, the browser will
block your pageviews at preflight until you add your domain to that list.**
This is a configuration defect, not a vulnerability, and it is being moved to
configuration.

## What Higashi already does

So you know where the line is, rather than having to read for it:

- **IPs are never stored raw.** `sha256(ip + site_id)` is written instead of
  the address. Know what that is and is not: the site id is not a secret and
  IPv4 is only 2^32 wide, so someone holding your database and a target
  address can confirm a guess by recomputing the hash. It stops the database
  from being a list of addresses. It is not a promise that an address cannot
  be checked against it.
- **Live sends counts, not content.** The paid service receives crawler names,
  counts and a verdict. Never IPs, paths, URLs, user agents or page content —
  `ReportIn.reject_private_data` in `backend/higashi_reading/schemas.py`
  refuses the whole report if any string in it looks like one, and the model
  the report is built from is `extra="forbid"`, so a new field cannot slip out
  unnoticed. That package is MIT and it is the same code the paid service
  runs, so you can read exactly what an install would send.
- **Session tokens go in the `Authorization` header, never the query string.**
  A query-string token ends up in the server's logs in plaintext. That was a
  real defect here, found and fixed on 2026-09-23.
- **Secrets at rest are encrypted** — AES-256-GCM under a key derived from
  `SECRET_KEY` (`backend/services/secret_box.py`), so a stolen database file
  on its own does not hand over your provider keys. The cost of that: once a
  credential is stored, rotating `SECRET_KEY` means re-encrypting those rows.
  It is not a free operation and it is not automatic.
- **Password fields are marked by purpose.** API key and SSH fields are marked
  not-a-login so password managers stop offering to fill them.

## If you run Higashi

Two things are worth doing on day one, because the defaults cannot do them for
you:

1. **Set a real `SECRET_KEY`.** `.env.example` ships a placeholder. It signs
   every session token and derives the key that encrypts stored credentials.
2. **Do not expose the dashboard or the API without TLS.** Sign-in posts a
   password and hands back a bearer token.
