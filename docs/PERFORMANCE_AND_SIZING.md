# Is it the box, or is it the software?

Higashi is self-hosted. Someone will run it on a €5 VPS with one core, someone else on
a spare Mac mini, someone else in a container on a NAS. We do not get to answer slowness
with "buy a bigger server", because we do not own the server. So we need a way to tell,
quickly and without arguing, whether a slow page is a hardware problem or our problem.

This is that method, the evidence it produced on 2026-09-23, and the order we fix things in.

## The test that settles it

Take the cheapest endpoint in the product — one that reads a config value and returns two
fields, no scanning, no joins. Time it twice: once on a quiet server, once while the page
that feels slow is loading.

If the cheap call is fast alone and slow under load, the machine is not too small. The
work is queueing. Adding cores moves the number without fixing the shape.

If the cheap call is slow even on a quiet server, something is wrong with the call itself
— and that is still not a sizing problem until you have read the code.

Only when the expensive work is genuinely irreducible — you have precomputed what can be
precomputed, indexed what can be indexed, and the query still has to read every row — does
hardware enter the conversation.

## The worked example, 2026-09-23

The Intelligence page felt broken. Cards sat on "Checking AI status…" for around ten
seconds on an install whose database is under a gigabyte.

Measured on the walk box: 1 vCPU, 1962 MB RAM, a 954 MB database, 571,007 events.

| call | quiet server | while the page loads |
|---|---|---|
| `/api/health` | 2 ms | — |
| `/api/admin/settings/ai` | **9 ms** | **9.6 s** |
| `/api/admin/settings/live` | 8 ms | — |
| `/api/analytics/live-count` | 85 ms | 85 ms |
| `/api/analytics/traffic-quality` 30d | 1.5 s | — |
| `/api/intelligence/summary` 7d | 3.1 s | — |
| `/api/analytics/timeseries` 30d | 4.3 s | — |
| `/api/analytics/overview` 30d | 7.1 s | — |
| `/api/intelligence/insights` 7d | **8.4 s** | — |
| `/api/analytics/suspicious-traffic` 30d | **8.8 s** | — |
| `/api/analytics/overview` 90d | **14.7 s** | — |

There are two separate problems here, and it is worth not confusing them.

**Some work is genuinely expensive.** Insights takes 8.4 seconds on a completely idle
server. The 90-day overview takes 14.7. No amount of front-end cleverness makes those
numbers smaller; only precomputation does.

**And that expensive work blocks everything else.** A config read that takes nine
milliseconds on a quiet box takes nine and a half seconds during a page load. It is not
doing any work in either case — it is waiting. The page fires about fifteen requests at
once, five of them scan half a million events, and there is one core and one SQLite file
to serve them all. The user watches a nine-millisecond call appear to hang.

The second problem is the one that makes the product feel broken, and it is much cheaper
to fix than the first.

Two conclusions, both important:

- **The box is not too small.** A bigger VPS would have shortened the jam, hidden the
  defect, and cost money every month for as long as the product exists.
- **The user was right and the numbers were misleading.** "It's text, and it's not even
  pulling from another server" was the correct instinct. Believe that instinct and go
  measure.

## Fix in this order

1. **Do not do the work.** Precompute it. A daily rollup turns "scan every event in
   ninety days" into "read ninety rows". This is the only step that removes cost rather
   than moving it.
2. **Do the work faster.** Indexes, one windowed query instead of many, stop doing per-row
   work in Python that the database can do in a set.
3. **Do the work once.** Cache the result and reuse it, with a single-flight lock so ten
   simultaneous callers cause one computation, not ten.
4. **Do not do the work at the same time.** Let cheap calls answer immediately instead of
   sitting behind expensive ones. Stagger or limit the parallel burst.
5. **Do not do the work again.** On the client, keep what you already fetched so returning
   to a page you visited a minute ago is instant.
6. **Then, and only then, buy hardware.**

Steps 1–5 are portable: they help the person on the €5 VPS and the person on the Mac mini
equally. Step 6 helps only the people who can afford it, which in a self-hosted product is
a subset we do not control.

## What this means for a product we do not host

Because the hardware is the customer's, the floor has to be low and stated plainly:

- **One core and a gigabyte of RAM is the target, not the minimum we tolerate.** If a page
  is unusable there, it is unfinished, not under-resourced.
- **Size claims must be measured on the smallest supported box**, with a database the size
  a real site produces, not an empty one. An install with a thousand events proves nothing.
- **Never answer a customer's performance complaint with "upgrade your VPS"** until the
  cheap-call test above has been run on their numbers. It is the support equivalent of
  blaming the user.

## Keeping it OS-agnostic

The same discipline applies to anything we tell a self-hoster to run. State requirements as
capabilities, not as packages or distributions:

- **Say what must be true, not how to make it true.** "Higashi needs a writable data
  directory and a way to run one long-lived process" — not "run this systemd unit".
  systemd is how *our* walk box does it; it is not a requirement, and it does not exist on
  a Mac, on Alpine's default install, or inside many containers.
- **Keep OS-specific things in deployment, never in the application.** Service files, cron
  timers, log rotation and package installs belong in a deploy script for a named platform.
  The application should not know which one it landed on.
- **No absolute paths baked into code.** Data location, config location and log location
  are configuration, with sane relative defaults.
- **Prefer the standard library and portable dependencies.** Anything needing a compiler or
  a distro package narrows who can install the product.
- **Assume the clock, the locale and the filesystem are not yours.** Store timestamps in
  UTC, do not assume case-sensitive filenames, do not assume a POSIX shell is present.
- **Test on at least two platforms before claiming portability.** One Linux and one macOS
  catches most of it. Claiming "runs anywhere" from a single box is a guess.

## Red flags that mean "measure before you conclude"

- A trivial endpoint that is sometimes fast and sometimes slow. That is queueing, always.
- Advice to resize a machine offered before anyone has timed a single call.
- A page that fires more than a handful of requests at once.
- A number quoted from a development machine with a small database.
- "It got faster after we upgraded" — which proves the jam got shorter, not that the
  software got better.

## See also

- `~/deploys/higashi-analytics/measure_dashboard.sh` — the before/after timing harness,
  including the cheap-call-under-load test. Output lands in
  `~/deploys/higashi-analytics/evidence/`.
- `docs/LIVE_BYOK_REVIEW.md` — the launch gate list, where the daily rollup sits.
- `~/deploys/higashi-analytics/OPS_LOG.md`, 2026-09-19 and 2026-09-20 — the earlier round
  of this same lesson: a regex classification running over every event on every request,
  fixed by classifying once at import instead of every time anyone looked.
