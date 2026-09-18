import { useEffect, useState } from "react";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [queries, setQueries] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/analytics/utm-campaigns?days=${days}`),
      api.get(`/analytics/search-queries?days=${days}`),
    ])
      .then(([c, q]) => { setCampaigns(c.data); setQueries(q.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  const totalSessions = campaigns.reduce((s, r) => s + r.sessions, 0);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Campaigns</h1>
          <p className="text-xs text-slate-500 mt-0.5">UTM attribution and search queries</p>
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
        {/* UTM campaigns */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">UTM Campaigns</p>
          {loading ? <p className="text-xs text-slate-500">Loading…</p>
          : campaigns.length === 0 ? <p className="text-xs text-slate-500">No campaign traffic yet. Add UTM parameters to your links.</p>
          : (
            <div className="space-y-3">
              {campaigns.map((c, i) => {
                const pct = totalSessions ? Math.round((c.sessions / totalSessions) * 100) : 0;
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <div className="flex gap-2 min-w-0">
                        <span className="text-accent shrink-0">{c.source}</span>
                        {c.medium && <span className="text-slate-500">/{c.medium}</span>}
                        {c.campaign && <span className="text-slate-400 truncate">— {c.campaign}</span>}
                      </div>
                      <span className="text-slate-400 shrink-0 ml-2">{c.sessions.toLocaleString()}</span>
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

        {/* Search queries */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-1">Search Queries</p>
          <p className="text-xs text-slate-500 mb-4">What people searched to find you</p>
          {loading ? <p className="text-xs text-slate-500">Loading…</p>
          : queries.length === 0 ? <p className="text-xs text-slate-500">No search referrals captured yet.</p>
          : (
            <div className="space-y-2">
              {queries.map((q, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
                  <span className="text-slate-300 font-mono truncate max-w-[220px]">"{q.query}"</span>
                  <span className="text-slate-400 shrink-0 ml-2">{q.arrivals} arrival{q.arrivals !== 1 ? "s" : ""}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
