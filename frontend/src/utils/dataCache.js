// A small read cache and a request scheduler for dashboard data.
//
// Why this exists, measured on the walk box (1 vCPU, 954 MB database, 571k events)
// on 2026-09-23:
//
//   - The Overview fired eleven requests at once. Solo they add up to about 29 s;
//     fired together the burst took 31.7 s wall clock. Parallelism bought nothing —
//     one core and one SQLite file answer them one at a time whatever we do. All the
//     concurrency achieved was burying a 9 ms config read behind an 8 s scan, so
//     every card looked broken at the same time.
//   - Leaving a page and coming back re-ran every fetch from scratch, because React
//     Router unmounts the page and each useEffect runs again on mount.
//
// So: run a couple at a time, cheapest first, and remember the answer for a minute.
// Neither of these makes the expensive queries cheaper — only a rollup does that —
// but they decide whether the page is readable in a second or blank for half a minute.
//
// In memory only, on purpose: analytics data does not belong in localStorage, and a
// reload should ask the server again.

import api from "./api";

export const FRESH_MS = 60_000;

// The server answers serially, so a wide burst only delays the cheap calls. Two keeps
// one slot free for whatever the person just clicked.
const MAX_PARALLEL = 2;

// Lower runs sooner. Pick by how long the call takes, not by how much you want it.
export const PRIORITY = {
  instant: 0,   // under ~100 ms: live count, recent visitors, settings, status
  quick: 1,     // a second or two: traffic quality, geo
  normal: 2,    // a few seconds: timeseries, top pages
  slow: 3,      // the window scans: overview, suspicious traffic, insights
};

const entries = new Map();   // key -> { at, data }
const inflight = new Map();  // key -> promise
const waiting = [];          // { priority, seq, start }
let running = 0;
let seq = 0;

function siteId() {
  try {
    return JSON.parse(localStorage.getItem("ha-site") || "{}")?.state?.currentSiteId || "-";
  } catch (_) {
    return "-";
  }
}

// The site is part of the identity of a result: the same path for another site is a
// different answer, never a cache hit.
function keyFor(path) {
  return `${siteId()}::${path}`;
}

function pump() {
  while (running < MAX_PARALLEL && waiting.length > 0) {
    waiting.sort((a, b) => a.priority - b.priority || a.seq - b.seq);
    const next = waiting.shift();
    running += 1;
    next.start();
  }
}

function schedule(priority, work) {
  return new Promise((resolve, reject) => {
    const start = () => {
      work().then(resolve, reject).finally(() => {
        running -= 1;
        pump();
      });
    };
    waiting.push({ priority, seq: (seq += 1), start });
    pump();
  });
}

/**
 * GET a path, served from the cache when the answer is younger than `ttl`.
 *
 * Returns the response body, not the axios response — callers only ever wanted `.data`.
 * Concurrent callers for the same path share one request rather than racing.
 */
export function cachedGet(path, { ttl = FRESH_MS, priority = PRIORITY.normal, force = false } = {}) {
  const key = keyFor(path);

  if (!force) {
    const hit = entries.get(key);
    if (hit && Date.now() - hit.at < ttl) return Promise.resolve(hit.data);
    const pending = inflight.get(key);
    if (pending) return pending;
  }

  const request = schedule(priority, () => api.get(path).then(({ data }) => data))
    .then((data) => {
      entries.set(key, { at: Date.now(), data });
      return data;
    })
    .finally(() => {
      inflight.delete(key);
    });

  inflight.set(key, request);
  return request;
}

/** Whether a path would answer from the cache right now — used to skip a spinner. */
export function isCached(path, ttl = FRESH_MS) {
  const hit = entries.get(keyFor(path));
  return Boolean(hit && Date.now() - hit.at < ttl);
}

/** Forget cached answers. No prefix forgets everything (sign-out, site removed). */
export function invalidate(prefix) {
  if (!prefix) {
    entries.clear();
    return;
  }
  for (const key of [...entries.keys()]) {
    if (key.includes(prefix)) entries.delete(key);
  }
}

export default cachedGet;
