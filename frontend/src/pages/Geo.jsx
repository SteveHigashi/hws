import { useEffect, useState } from "react";
import GeoGlobe from "../components/charts/GeoGlobe";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

export default function Geo() {
  const [geo, setGeo] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    api.get(`/analytics/geo?days=${days}`)
      .then(({ data }) => setGeo(data))
      .catch(() => setGeo([]))
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  const total = geo.reduce((s, g) => s + g.visitors, 0);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Geography</h1>
          <p className="text-xs text-slate-500 mt-0.5">Where your visitors come from</p>
        </div>
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

      <GeoGlobe data={geo} />

      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
        <p className="text-sm font-medium text-slate-300 mb-4">Country Breakdown</p>
        {loading ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : geo.length === 0 ? (
          <p className="text-xs text-slate-500">No geographic data yet.</p>
        ) : (
          <div className="space-y-2">
            {geo.map((g, i) => {
              const pct = total ? Math.round((g.visitors / total) * 100) : 0;
              return (
                <div key={i} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300">{g.country || "Unknown"}</span>
                    <span className="text-slate-400">{g.visitors.toLocaleString()} <span className="text-slate-600">({pct}%)</span></span>
                  </div>
                  <div className="h-1 bg-surface-600 rounded-full overflow-hidden">
                    <div className="h-full bg-accent rounded-full" style={{ width: `${pct}%` }} />
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
