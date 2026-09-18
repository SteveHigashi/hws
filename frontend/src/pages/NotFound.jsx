import { useEffect, useState } from "react";
import api from "../utils/api";

export default function NotFound() {
  const [pages, setPages] = useState([]);
  const [seo404s, setSeo404s] = useState(null);
  const [exitPages, setExitPages] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState("seo_actionable");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/analytics/not-found?days=${days}`),
      api.get(`/analytics/seo-404s?days=${days}`),
      api.get(`/analytics/exit-pages?days=${days}`),
    ])
      .then(([nf, seo, ep]) => {
        setPages(nf.data);
        setSeo404s(seo.data);
        setExitPages(ep.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  const summary = seo404s?.summary || {};
  const visible404s = mode === "all" ? pages : (seo404s?.[mode] || []);
  const modeLabels = {
    seo_actionable: "SEO 404s",
    scanner_security: "Scanner Probes",
    platform_residue: "Archive Residue",
    all: "All Raw",
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Errors & Exits</h1>
          <p className="text-xs text-slate-500 mt-0.5">404s and where visitors leave</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${days === d ? "bg-accent text-white" : "bg-surface-700 text-slate-400 hover:text-white border border-surface-500"}`}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* 404s */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-danger" />
                <p className="text-sm font-medium text-slate-300">404 Not Found</p>
              </div>
              <p className="text-xs text-slate-500 mt-1">Default view filters out scanner and legacy platform noise</p>
            </div>
            {pages.length > 0 && <span className="text-xs text-danger shrink-0">{pages.length} raw URL{pages.length !== 1 ? "s" : ""}</span>}
          </div>
          <div className="flex flex-wrap gap-2 mb-4">
            {["seo_actionable", "scanner_security", "platform_residue", "all"].map((key) => (
              <button
                key={key}
                onClick={() => setMode(key)}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${mode === key ? "bg-accent text-white" : "bg-surface-700 text-slate-400 hover:text-white border border-surface-500"}`}
              >
                {modeLabels[key]} {key !== "all" && summary[key] != null ? `(${summary[key].toLocaleString()})` : ""}
              </button>
            ))}
          </div>
          {loading ? <p className="text-xs text-slate-500">Loading…</p>
          : visible404s.length === 0 ? (
            <div className="flex items-center gap-2">
              <span className="text-success">✓</span>
              <p className="text-xs text-slate-400">No URLs in this 404 category.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {visible404s.map((p, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
                  <span className="text-danger font-mono truncate max-w-[240px]">{_path(p.page)}</span>
                  <span className="text-slate-400 shrink-0 ml-2">{p.hits} hit{p.hits !== 1 ? "s" : ""}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Exit pages */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-1">Top Exit Pages</p>
          <p className="text-xs text-slate-500 mb-4">Last page viewed before leaving</p>
          {loading ? <p className="text-xs text-slate-500">Loading…</p>
          : exitPages.length === 0 ? <p className="text-xs text-slate-500">No exit data yet.</p>
          : (
            <div className="space-y-2">
              {exitPages.map((p, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
                  <span className="text-slate-300 font-mono truncate max-w-[240px]">{_path(p.page)}</span>
                  <span className="text-slate-400 shrink-0 ml-2">{p.exits.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function _path(url) {
  try { return new URL(url).pathname || url; } catch { return url; }
}
