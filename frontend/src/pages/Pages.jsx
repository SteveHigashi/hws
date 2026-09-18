import { useEffect, useState } from "react";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

export default function Pages() {
  const [pages, setPages] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("views");
  const [traffic, setTraffic] = useState("all");
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    api.get(`/analytics/top-pages?days=${days}&limit=50&traffic=${traffic}`)
      .then(({ data }) => setPages(data))
      .catch(() => setPages([]))
      .finally(() => setLoading(false));
  }, [days, traffic, currentSiteId]);

  const sorted = [...pages].sort((a, b) => b[sort] - a[sort]);
  const maxViews = sorted[0]?.views || 1;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Pages</h1>
          <p className="text-xs text-slate-500 mt-0.5">Performance of individual pages</p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <button key={d} onClick={() => setDays(d)}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${days === d ? "bg-accent text-white" : "bg-surface-700 text-slate-400 hover:text-white border border-surface-500"}`}>
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          ["all", "All Traffic"],
          ["humans", "Verified + Likely Humans"],
          ["ai_crawlers", "AI Crawlers"],
          ["suspicious", "Suspicious"],
        ].map(([value, label]) => (
          <button
            key={value}
            onClick={() => setTraffic(value)}
            className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${traffic === value ? "bg-accent text-white" : "bg-surface-700 text-slate-400 hover:text-white border border-surface-500"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-xl overflow-hidden">
        <div className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-surface-600 text-xs text-slate-500 uppercase tracking-wider">
          <span className="col-span-7">Page</span>
          <span className="col-span-2 text-right cursor-pointer hover:text-white transition-colors" onClick={() => setSort("views")}>
            Views {sort === "views" && "↓"}
          </span>
          <span className="col-span-3 text-right">Traffic share</span>
        </div>

        {loading ? (
          <div className="px-5 py-8 text-center text-xs text-slate-500">Loading…</div>
        ) : sorted.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-slate-500">No page data yet</div>
        ) : (
          <div>
            {sorted.map((p, i) => {
              const share = Math.round((p.views / maxViews) * 100);
              return (
                <div key={i} className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-surface-600/50 last:border-0 hover:bg-surface-700/50 transition-colors items-center">
                  <span className="col-span-7 text-xs font-mono text-slate-300 truncate">{_path(p.page)}</span>
                  <span className="col-span-2 text-right text-sm text-white font-medium">{p.views.toLocaleString()}</span>
                  <div className="col-span-3 flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                      <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${share}%` }} />
                    </div>
                    <span className="text-xs text-slate-500 w-8 text-right">{share}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function _path(url) {
  try { return new URL(url).pathname || url; } catch { return url; }
}
