import { useEffect, useState, useRef } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "../components/layout/Sidebar";
import StatCard from "../components/charts/StatCard";
import StatTooltip from "../components/charts/StatTooltip";
import TrafficChart from "../components/charts/TrafficChart";
import InsightsFeed from "../components/charts/InsightsFeed";
import RealtimeFeed from "../components/charts/RealtimeFeed";
import api from "../utils/api";
import { cachedGet, isCached, PRIORITY } from "../utils/dataCache";
import HeadlineCounts from "../components/overview/HeadlineCounts";
import WhoFetchedYou from "../components/overview/WhoFetchedYou";
import { useSiteStore } from "../store/siteStore";
import Intelligence from "./Intelligence";
import Account from "./Account";
import GeoVisibility from "./GeoVisibility";
import Realtime from "./Realtime";
import Flow from "./Flow";
import Geo from "./Geo";
import Pages from "./Pages";
import Sources from "./Sources";
import Devices from "./Devices";
import Campaigns from "./Campaigns";
import NotFound from "./NotFound";
import Behavior from "./Behavior";
import AICrawlers from "./AICrawlers";
import LiveTraffic from "./LiveTraffic";
import Import from "./Import";
import CatalogueProtection from "./CatalogueProtection";
import WatchThisSite from "../components/live/WatchThisSite";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

// ---------------------------------------------------------------------------
// Country flag helper — maps 2-letter ISO code to flag emoji
// ---------------------------------------------------------------------------
function countryFlag(code) {
  if (!code || code.length !== 2) return "";
  try {
    return String.fromCodePoint(
      ...[...code.toUpperCase()].map((c) => 0x1f1e0 - 65 + c.charCodeAt(0))
    );
  } catch (_) {
    return "";
  }
}

// ---------------------------------------------------------------------------
// Time-ago helper
// ---------------------------------------------------------------------------
function timeAgo(isoString) {
  if (!isoString) return "";
  const diff = Math.floor((Date.now() - new Date(isoString + "Z").getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ---------------------------------------------------------------------------
// Duration formatter — seconds to "1m 42s" / "38s"
// ---------------------------------------------------------------------------
function formatDuration(seconds) {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// ---------------------------------------------------------------------------
// Page label — path only
// ---------------------------------------------------------------------------
// The importer stores a full page_url ("https://example.com/vendor/contabo"), so
// a list of pages on one site repeats the same origin on every row and spends the
// truncation budget on the part that never varies. Show the path.
function pagePath(page) {
  const raw = page?.page || page?.path || page?.url || "";
  if (!raw) return "—";
  try {
    const parsed = new URL(raw);
    return (parsed.pathname + parsed.search) || "/";
  } catch {
    return raw; // already a bare path
  }
}

// ---------------------------------------------------------------------------
// RecentVisitors widget
// ---------------------------------------------------------------------------
function RecentVisitors() {
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef(null);
  const { currentSiteId } = useSiteStore();

  function fetchVisitors() {
    api
      .get("/analytics/recent-visitors?limit=10")
      .then(({ data }) => setVisitors(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchVisitors();
    intervalRef.current = setInterval(fetchVisitors, 30000);
    return () => clearInterval(intervalRef.current);
  }, [currentSiteId]);

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
      <p className="text-sm font-medium text-slate-300 mb-4">Recent Visitors</p>
      {loading ? (
        <p className="text-xs text-slate-500">Loading...</p>
      ) : visitors.length === 0 ? (
        <p className="text-xs text-slate-500">No data yet</p>
      ) : (
        <div className="space-y-2">
          {visitors.map((v, i) => {
            const flag = countryFlag(v.country);
            const path = v.page_url
              ? v.page_url.length > 40
                ? v.page_url.slice(0, 40) + "…"
                : v.page_url
              : "—";
            const ref = v.referrer_domain || "Direct";
            return (
              <div
                key={i}
                className="flex items-center gap-2 text-xs text-slate-400 font-mono"
              >
                <span className="text-slate-600 shrink-0 w-14">{timeAgo(v.timestamp)}</span>
                <span className="shrink-0">{flag || "🌐"}</span>
                <span className="text-slate-300 truncate flex-1">{path}</span>
                <span className="text-slate-500 shrink-0">← {ref}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LiveNow badge
// ---------------------------------------------------------------------------
function LiveNow() {
  const [count, setCount] = useState(null);
  const intervalRef = useRef(null);
  const { currentSiteId } = useSiteStore();

  function fetchCount() {
    api
      .get("/analytics/live-count")
      .then(({ data }) => setCount(data.count))
      .catch(() => {});
  }

  useEffect(() => {
    fetchCount();
    intervalRef.current = setInterval(fetchCount, 30000);
    return () => clearInterval(intervalRef.current);
  }, [currentSiteId]);

  return (
    <div className="flex items-center gap-2 bg-surface-700 border border-surface-500 rounded-lg px-3 py-1.5">
      <span className="w-2 h-2 rounded-full bg-green-400 pulse-dot shrink-0" />
      <span className="text-xs text-green-400 font-mono font-semibold">LIVE NOW</span>
      <span className="text-xs text-white font-semibold ml-1">
        <StatTooltip id="live_now" value={count} showIcon={false}>{count === null ? "—" : count}</StatTooltip>
      </span>
      <span className="text-xs text-slate-500">visitor{count !== 1 ? "s" : ""}</span>
    </div>
  );
}

function TrafficQualityPanel({ data, loading }) {
  const rows = data?.classes || [];
  const total = data?.total_sessions || 0;

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="text-sm font-medium text-slate-300"><StatTooltip id="traffic_quality" value={data?.total_sessions}>Traffic Quality</StatTooltip></p>
          <p className="text-xs text-slate-500 mt-0.5">Log sessions split by human proof and noise signals</p>
        </div>
        <span className="text-xs text-slate-500 shrink-0"><StatTooltip id="traffic_quality" value={data?.total_sessions} showIcon={false}>{total.toLocaleString()} sessions</StatTooltip></span>
      </div>
      {loading ? (
        <p className="text-xs text-slate-500">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="text-xs text-slate-500">No session data yet</p>
      ) : (
        <div className="space-y-3">
          {rows
            .filter((row) => ["verified_human", "likely_human", "suspicious", "unknown"].includes(row.class))
            .map((row) => (
              <div key={row.class}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-300">{row.label}</span>
                  <span className="font-mono text-slate-400"><StatTooltip id={{ verified_human: "verified_humans", likely_human: "likely_humans", suspicious: "suspicious_sessions", unknown: "unknown_sessions" }[row.class]} value={row.count} showIcon={false}>{row.count.toLocaleString()} · {row.share}%</StatTooltip></span>
                </div>
                <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div className={`h-full ${qualityBar(row.class)}`} style={{ width: `${Math.max(row.share, row.count ? 2 : 0)}%` }} />
                </div>
              </div>
            ))}
        </div>
      )}
      {data?.note && (
        <p className="text-xs text-warn mt-4">{data.note}</p>
      )}
    </div>
  );
}

function ScannerNoisePanel({ data, loading }) {
  const paths = data?.top_paths || [];
  const reasons = data?.top_reasons || [];
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="text-sm font-medium text-slate-300"><StatTooltip id="scanner_noise" value={data?.sessions}>Scanner Noise</StatTooltip></p>
          <p className="text-xs text-slate-500 mt-0.5">Security probes, fake-browser hits, and 404-only sessions</p>
        </div>
        <span className="text-xs text-danger shrink-0"><StatTooltip id="scanner_noise" value={data?.sessions} showIcon={false}>{(data?.sessions || 0).toLocaleString()} sessions</StatTooltip></span>
      </div>
      {loading ? (
        <p className="text-xs text-slate-500">Loading...</p>
      ) : paths.length === 0 ? (
        <p className="text-xs text-slate-500">No scanner pattern detected in this period</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wider text-slate-500">Top Paths</p>
            {paths.slice(0, 5).map((p, i) => (
              <div key={i} className="flex items-center justify-between text-xs gap-3">
                <span className="text-slate-300 font-mono truncate">{p.path}</span>
                <span className="text-slate-500 shrink-0"><StatTooltip id="scanner_path_hits" value={p.hits} showIcon={false}>{p.hits.toLocaleString()}</StatTooltip></span>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wider text-slate-500">Reasons</p>
            {reasons.slice(0, 5).map((r, i) => (
              <div key={i} className="flex items-center justify-between text-xs gap-3">
                <span className="text-slate-300 truncate">{r.reason}</span>
                <span className="text-slate-500 shrink-0"><StatTooltip id="scanner_reason_sessions" value={r.sessions} showIcon={false}>{r.sessions.toLocaleString()}</StatTooltip></span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function qualityBar(kind) {
  if (kind === "verified_human") return "bg-success";
  if (kind === "likely_human") return "bg-accent";
  if (kind === "suspicious") return "bg-danger";
  return "bg-slate-500";
}

function SplitTooltip({ active, payload }) {
  const item = payload?.[0];
  if (!active || !item) return null;
  return (
    <div className="rounded-lg border border-surface-500 bg-surface-700 px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400">{item.name}</p>
      <p className="mt-1 font-mono font-semibold text-white">{(item.value ?? 0).toLocaleString()} visits</p>
    </div>
  );
}

function VisitorsSplit({ data, loading }) {
  const people = data?.real_traffic_estimate ?? 0;
  const ai = data?.ai_crawlers ?? 0;
  const otherBots = data?.known_bots ?? 0;
  const total = people + ai + otherBots;
  const chartData = [
    { name: "People", value: people, color: "#10b981" },
    { name: "AI crawlers", value: ai, color: "#ef4444" },
    { name: "Other bots", value: otherBots, color: "#f59e0b" },
  ];

  return (
    <section className="rounded-xl border border-surface-600 bg-surface-800 p-5">
      <div>
        <h2 className="text-sm font-medium text-slate-200">Visitors vs Automated</h2>
        <p className="mt-0.5 text-xs text-slate-500">Every visit, classified by who or what made it</p>
      </div>
      {loading ? (
        <div className="flex h-[286px] items-center justify-center text-xs text-slate-500">Classifying traffic…</div>
      ) : total === 0 ? (
        <div className="flex h-[286px] items-center justify-center text-xs text-slate-500">No traffic data yet</div>
      ) : (
        <div className="mt-3 grid grid-cols-1 items-center gap-2 sm:grid-cols-[minmax(180px,1fr)_minmax(170px,0.8fr)] xl:grid-cols-1 2xl:grid-cols-[minmax(180px,1fr)_minmax(170px,0.8fr)]">
          <div className="relative h-[210px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={62} outerRadius={86} paddingAngle={2} stroke="#0d1220" strokeWidth={3}>
                  {chartData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                </Pie>
                <Tooltip content={<SplitTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-2xl font-semibold text-white">{total.toLocaleString()}</span>
              <span className="text-[10px] uppercase tracking-wider text-slate-500">total visits</span>
            </div>
          </div>
          <div className="space-y-3">
            {chartData.map((entry) => {
              const percent = total ? (entry.value / total) * 100 : 0;
              return (
                <div key={entry.name} className="flex items-center gap-2 text-xs">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: entry.color }} />
                  <span className="text-slate-400">{entry.name}</span>
                  <span className="ml-auto font-mono text-slate-200">{entry.value.toLocaleString()}</span>
                  <span className="w-12 text-right font-mono text-slate-500">{percent.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Overview page
// ---------------------------------------------------------------------------
function Overview() {
  const [stats, setStats] = useState(null);
  const [trafficQuality, setTrafficQuality] = useState(null);
  const [suspiciousTraffic, setSuspiciousTraffic] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [topPages, setTopPages] = useState([]);
  const [geo, setGeo] = useState([]);
  const [actors, setActors] = useState([]);
  const [insights, setInsights] = useState([]);
  const [enrichMeta, setEnrichMeta] = useState(null);
  const [enrichLoading, setEnrichLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [ready, setReady] = useState({});   // which panels have their own answer yet
  const [insightsLoading, setInsightsLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  // Six separate requests, each rendering the moment it lands, cheapest first.
  //
  // This was one Promise.all, so nothing appeared until the slowest of the six
  // finished — 31.7 s on the walk box, with the whole page blank throughout. The
  // requests are not faster now; they simply stop waiting for each other, and the
  // 1.5 s call no longer sits behind the 8.8 s one.
  useEffect(() => {
    let live = true;
    const set = (fn) => (data) => { if (live) fn(data); };

    const calls = [
      ["quality", `/analytics/traffic-quality?days=${days}`, PRIORITY.quick, setTrafficQuality],
      ["actors", `/ai-crawlers/crawlers?days=${days}`, PRIORITY.quick, setActors],
      ["geo", `/analytics/geo?days=${days}`, PRIORITY.quick, setGeo],
      ["trend", `/analytics/traffic-quality/timeseries?days=${days}`, PRIORITY.normal, setTimeseries],
      ["pages", `/analytics/top-pages?days=${days}&limit=5&traffic=humans`, PRIORITY.normal, setTopPages],
      ["stats", `/analytics/overview?days=${days}`, PRIORITY.slow, setStats],
      ["suspicious", `/analytics/suspicious-traffic?days=${days}&limit=8`, PRIORITY.slow, setSuspiciousTraffic],
    ];

    // Each panel waits only for its own call. A shared flag would have kept the whole
    // page on skeletons until the slowest one landed, which is what we just stopped doing.
    setReady(Object.fromEntries(calls.map(([name, path]) => [name, isCached(path)])));

    Promise.allSettled(
      calls.map(([name, path, priority, setter]) =>
        cachedGet(path, { priority })
          .then(set(setter))
          .finally(() => { if (live) setReady((r) => ({ ...r, [name]: true })); })
      )
    );

    return () => { live = false; };
  }, [days, currentSiteId]);

  useEffect(() => {
    setInsightsLoading(!isCached("/intelligence/insights?days=7"));
    setEnrichMeta(null);
    cachedGet("/intelligence/insights?days=7", { priority: PRIORITY.slow })
      .then((raw) => {
        const data = Array.isArray(raw) ? raw : [];
        setInsights(data);
        setInsightsLoading(false);
        if (data.length > 0) {
          setEnrichLoading(true);
          api
            .post("/intelligence/enrich", { insights: data, days: 7 })
            .then(({ data: ed }) => {
              setInsights(Array.isArray(ed?.enriched) ? ed.enriched : data);
              if (!ed.skipped) setEnrichMeta(ed);
            })
            .catch(() => {})
            .finally(() => setEnrichLoading(false));
        }
      })
      .catch(() => {
        setInsights([]);
        setInsightsLoading(false);
      });
  }, [currentSiteId]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white">Overview</h1>
          <p className="text-xs text-slate-500 mt-0.5">People, crawlers, and site activity at a glance</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <LiveNow />
          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  days === d
                    ? "bg-accent text-white"
                    : "bg-surface-700 text-slate-400 hover:text-white border border-surface-500"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      <HeadlineCounts data={trafficQuality} stats={stats} loading={!ready.quality} />

      <div className="-mt-3 text-xs text-slate-500">
        Last {days} days · average time spent{" "}
        <StatTooltip id="avg_time_spent" value={stats?.avg_session_duration} showIcon={false}>{formatDuration(stats?.avg_session_duration)}</StatTooltip>
        {" · "}
        <StatTooltip id="raw_sessions" value={stats?.sessions} showIcon={false}>{stats?.sessions?.toLocaleString() ?? "—"} raw sessions</StatTooltip>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <WhoFetchedYou rows={actors} loading={!ready.actors} />
        <VisitorsSplit data={trafficQuality} loading={!ready.quality} />
      </div>

      <TrafficChart data={timeseries} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <div className="mb-4">
            <p className="text-sm font-medium text-slate-200">Top Pages</p>
            <p className="mt-0.5 text-xs text-slate-500">Where real visitors spent their attention</p>
          </div>
          {!ready.pages ? (
            <p className="text-xs text-slate-500">Loading...</p>
          ) : !Array.isArray(topPages) || topPages.length === 0 ? (
            <p className="text-xs text-slate-500">No data yet</p>
          ) : (() => {
            // Log-imported rows have no client-side timing, so avg_duration is null for
            // every page and the column renders as a stack of dashes. Show it only when
            // at least one page actually has a figure.
            const hasDuration = topPages.some((p) => p?.avg_duration != null);
            return (
            <div className="space-y-3">
              {topPages.map((page, index) => {
                const width = topPages[0]?.views ? Math.max(4, ((page?.views ?? 0) / topPages[0].views) * 100) : 0;
                return (
                  <div key={`${page?.page || page?.path || "page"}-${index}`}>
                    <div className="mb-1.5 flex items-center gap-3 text-xs">
                      <span className="w-5 font-mono text-slate-600">{String(index + 1).padStart(2, "0")}</span>
                      <span className="min-w-0 flex-1 truncate font-mono text-slate-300">{pagePath(page)}</span>
                      <span className="font-mono text-slate-300"><StatTooltip id="top_page_views" value={page?.views} showIcon={false}>{(page?.views ?? 0).toLocaleString()}</StatTooltip></span>
                      {hasDuration && (
                        <span className="w-12 text-right text-slate-500"><StatTooltip id="top_page_time" value={page?.avg_duration} showIcon={false}>{formatDuration(page?.avg_duration)}</StatTooltip></span>
                      )}
                    </div>
                    <div className="ml-8 h-1 overflow-hidden rounded-full bg-surface-600">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${width}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
            );
          })()}
        </div>

        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <div className="mb-4">
            <p className="text-sm font-medium text-slate-200">Geography</p>
            <p className="mt-0.5 text-xs text-slate-500">Countries sending the most real visitors</p>
          </div>
          {!ready.geo ? (
            <p className="text-xs text-slate-500">Loading...</p>
          ) : !Array.isArray(geo) || geo.length === 0 ? (
            <p className="text-xs text-slate-500">No data yet</p>
          ) : (
            <div className="space-y-3">
              {geo.slice(0, 5).map((country, index) => {
                const peak = geo[0]?.visitors ?? geo[0]?.visits ?? 0;
                const visits = country?.visitors ?? country?.visits ?? 0;
                const width = peak ? Math.max(4, (visits / peak) * 100) : 0;
                return (
                  <div key={`${country?.country || "unknown"}-${index}`}>
                    <div className="mb-1.5 flex items-center gap-2 text-xs">
                      <span className="text-base">{countryFlag(country?.country) || "🌐"}</span>
                      <span className="text-slate-300">{country?.country || "Unknown"}</span>
                      <span className="ml-auto font-mono text-slate-300"><StatTooltip id="top_country_visitors" value={visits} showIcon={false}>{visits.toLocaleString()}</StatTooltip></span>
                    </div>
                    <div className="ml-7 h-1 overflow-hidden rounded-full bg-surface-600">
                      <div className="h-full rounded-full bg-pulse" style={{ width: `${width}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-medium text-slate-200">Watch this site</h2>
          <p className="mt-0.5 text-xs text-slate-500">Plain-language monitoring detail and crawler activity</p>
        </div>
        <WatchThisSite />
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-medium text-slate-200">Supporting metrics</h2>
          <p className="mt-0.5 text-xs text-slate-500">The detail behind the headline numbers</p>
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard id="verified_humans" label="Verified Humans" value={stats?.verified_humans?.toLocaleString()} accent />
          <StatCard id="likely_humans" label="Likely Humans" value={stats?.likely_humans?.toLocaleString()} sub={stats?.has_js_proof ? "with proof mix" : "log estimate"} />
          <StatCard id="avg_time_spent" label="Avg. Time Spent" value={stats?.avg_session_duration == null ? null : formatDuration(stats.avg_session_duration)} sub="per real session" />
          <StatCard id="ai_crawlers" label="AI Crawlers" value={stats?.ai_crawlers?.toLocaleString()} sub="bot visits" />
          <StatCard id="suspicious_sessions" label="Suspicious Sessions" value={stats?.suspicious_sessions?.toLocaleString()} sub="scanner/noise" />
          <StatCard id="known_bots" label="Known Bots" value={stats?.known_bots?.toLocaleString()} sub="non-AI bot visits" />
          <StatCard id="page_views" label="Page Views" value={stats?.page_views?.toLocaleString()} />
          <StatCard id="errors_404" label="404 Errors" value={stats?.errors_404?.toLocaleString()} sub={stats?.errors_404 > 0 ? "triaged below" : "clean"} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <TrafficQualityPanel data={trafficQuality} loading={!ready.quality} />
        <ScannerNoisePanel data={suspiciousTraffic} loading={!ready.suspicious} />
      </div>

      <RecentVisitors />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <InsightsFeed insights={insights} loading={insightsLoading} enrichMeta={enrichMeta} enrichLoading={enrichLoading} />
        <RealtimeFeed />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Placeholder
// ---------------------------------------------------------------------------
function Placeholder({ title }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <p className="text-slate-500 text-sm">{title}</p>
        <p className="text-slate-600 text-xs mt-1">Coming in next version</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard shell
// ---------------------------------------------------------------------------
export default function Dashboard() {
  return (
    <div className="flex min-h-screen bg-surface-900">
      <Sidebar />
      <Routes>
        <Route index element={<Overview />} />
        <Route path="intelligence" element={<Intelligence />} />
        <Route path="account" element={<Account />} />
        <Route path="geo-visibility" element={<GeoVisibility />} />
        <Route path="realtime" element={<Realtime />} />
        <Route path="live-traffic" element={<LiveTraffic />} />
        <Route path="flow" element={<Flow />} />
        <Route path="geo" element={<Geo />} />
        <Route path="pages" element={<Pages />} />
        <Route path="sources" element={<Sources />} />
        <Route path="campaigns" element={<Campaigns />} />
        <Route path="devices" element={<Devices />} />
        <Route path="errors" element={<NotFound />} />
        <Route path="behavior" element={<Behavior />} />
        <Route path="ai-crawlers" element={<AICrawlers />} />
        <Route path="catalogue-protection" element={<CatalogueProtection />} />
        <Route path="import" element={<Import />} />
      </Routes>
    </div>
  );
}
