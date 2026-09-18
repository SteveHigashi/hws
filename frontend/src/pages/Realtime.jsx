import { useEffect, useRef, useState } from "react";
import RealtimeFeed from "../components/charts/RealtimeFeed";
import api from "../utils/api";

const DEVICE_ICONS = { desktop: "Desktop", mobile: "Mobile", tablet: "Tablet" };
const DEVICE_COLORS = {
  desktop: "bg-blue-500",
  mobile:  "bg-violet-500",
  tablet:  "bg-sky-500",
};

function ActiveStat({ label, value, large, pulse }) {
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 flex flex-col justify-between">
      <p className="text-xs text-slate-500 uppercase tracking-widest">{label}</p>
      <div className="flex items-end gap-2 mt-3">
        {pulse && (
          <span className="w-2 h-2 rounded-full bg-success pulse-dot mb-1 shrink-0" />
        )}
        <p className={`font-mono font-semibold text-white leading-none ${large ? "text-4xl" : "text-2xl"}`}>
          {value ?? "—"}
        </p>
      </div>
    </div>
  );
}

function LiveBar({ label, value, max, color = "bg-accent" }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 font-mono w-28 truncate shrink-0">{label}</span>
      <div className="flex-1 bg-surface-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-400 w-6 text-right shrink-0">{value}</span>
    </div>
  );
}

export default function Realtime() {
  const [stats, setStats] = useState(null);
  const [prevActive, setPrevActive] = useState(null);
  const [flash, setFlash] = useState(false);
  const intervalRef = useRef(null);

  const fetchStats = () => {
    api.get("/intelligence/active-stats")
      .then(({ data }) => {
        setStats((prev) => {
          if (prev && data.active_sessions !== prev.active_sessions) {
            setFlash(true);
            setTimeout(() => setFlash(false), 600);
          }
          setPrevActive(prev?.active_sessions ?? null);
          return data;
        });
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchStats();
    intervalRef.current = setInterval(fetchStats, 5000);
    return () => clearInterval(intervalRef.current);
  }, []);

  const maxPageHits  = Math.max(...(stats?.top_pages     ?? []).map((p) => p.hits),    1);
  const maxCountry   = Math.max(...(stats?.top_countries ?? []).map((c) => c.visitors), 1);

  const delta = prevActive != null && stats != null
    ? stats.active_sessions - prevActive
    : null;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Real-time</h1>
          <p className="text-xs text-slate-500 mt-0.5">Live visitor activity — refreshes every 5 seconds</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" />
          <span className="text-xs text-slate-500">live</span>
        </div>
      </div>

      {/* Top stat row */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <div className={`bg-surface-800 border rounded-xl p-5 transition-colors duration-300 col-span-1
          ${flash ? "border-success/60" : "border-surface-600"}`}>
          <p className="text-xs text-slate-500 uppercase tracking-widest">Active Now</p>
          <div className="flex items-end gap-3 mt-3">
            <span className="w-2 h-2 rounded-full bg-success pulse-dot mb-1 shrink-0" />
            <p className="text-4xl font-mono font-semibold text-white leading-none">
              {stats?.active_sessions ?? "—"}
            </p>
            {delta !== null && delta !== 0 && (
              <span className={`text-sm font-mono mb-0.5 ${delta > 0 ? "text-green-400" : "text-slate-500"}`}>
                {delta > 0 ? `+${delta}` : delta}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-600 mt-1">sessions in last 5 min</p>
        </div>

        <ActiveStat
          label="Views / min"
          value={stats?.pageviews_last_60s ?? "—"}
        />
        <ActiveStat
          label="Views last 5 min"
          value={stats?.pageviews_last_5m ?? "—"}
        />

        {/* Device split */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-xs text-slate-500 uppercase tracking-widest mb-3">Devices</p>
          {stats?.devices && Object.keys(stats.devices).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(stats.devices)
                .sort(([, a], [, b]) => b - a)
                .map(([type, pct]) => (
                  <div key={type} className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${DEVICE_COLORS[type] ?? "bg-slate-500"}`} />
                    <span className="text-xs text-slate-400 flex-1">{DEVICE_ICONS[type] ?? type}</span>
                    <span className="text-xs font-mono text-slate-300">{pct}%</span>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-xs text-slate-600">No data yet</p>
          )}
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Live event stream — existing component, unchanged */}
        <RealtimeFeed />

        {/* Active pages */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" />
            <p className="text-sm font-medium text-slate-300">Active Pages</p>
            <span className="ml-auto text-xs text-slate-600">last 5 min</span>
          </div>
          {!stats || stats.top_pages.length === 0 ? (
            <p className="text-xs text-slate-500">No page activity yet</p>
          ) : (
            <div className="space-y-3">
              {stats.top_pages.map((p, i) => (
                <LiveBar
                  key={i}
                  label={p.page}
                  value={p.hits}
                  max={maxPageHits}
                  color={i === 0 ? "bg-accent" : "bg-slate-500"}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Countries */}
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <p className="text-sm font-medium text-slate-300">Active Countries</p>
          <span className="ml-auto text-xs text-slate-600">last 5 min</span>
        </div>
        {!stats || stats.top_countries.length === 0 ? (
          <p className="text-xs text-slate-500">No location data yet</p>
        ) : (
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
            {stats.top_countries.map((c, i) => (
              <div key={i} className="bg-surface-700 rounded-lg px-4 py-2.5 flex items-center justify-between">
                <span className="text-sm font-mono text-slate-300">{c.country}</span>
                <div className="flex items-center gap-2">
                  <div className="w-12 bg-surface-600 rounded-full h-1">
                    <div
                      className="h-1 rounded-full bg-accent"
                      style={{ width: `${Math.round((c.visitors / maxCountry) * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-slate-400 w-4 text-right">{c.visitors}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
