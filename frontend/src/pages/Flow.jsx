import { useEffect, useState } from "react";
import SankeyChart from "../components/charts/SankeyChart";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

export default function Flow() {
  const [data, setData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    api.get(`/intelligence/paths?days=${days}`)
      .then(({ data }) => setData(data))
      .catch(() => setData({ nodes: [], links: [] }))
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Session Flow</h1>
          <p className="text-xs text-slate-500 mt-0.5">How visitors navigate your site</p>
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

      {loading ? (
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 flex items-center justify-center" style={{ height: 380 }}>
          <p className="text-slate-500 text-sm">Building flow map…</p>
        </div>
      ) : (
        <SankeyChart data={data} />
      )}

      {data.links.length > 0 && (
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-3">Top Transitions</p>
          <div className="space-y-2">
            {data.links.slice(0, 10).map((l, i) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <span className="text-slate-400 font-mono truncate max-w-[180px]">{l.source}</span>
                <span className="text-slate-600">→</span>
                <span className="text-slate-400 font-mono truncate max-w-[180px]">{l.target}</span>
                <span className="text-accent ml-auto shrink-0">{l.value}×</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
