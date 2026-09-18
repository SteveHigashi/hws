import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

const COLORS = ["#3b82f6", "#22d3ee", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

const CHANNEL_MAP = {
  "google.com": "Search", "bing.com": "Search", "duckduckgo.com": "Search", "yahoo.com": "Search",
  "t.co": "Social", "twitter.com": "Social", "facebook.com": "Social", "instagram.com": "Social",
  "linkedin.com": "Social", "reddit.com": "Social", "pinterest.com": "Social",
};

function classifySource(domain) {
  if (!domain) return "Direct";
  for (const [key, val] of Object.entries(CHANNEL_MAP)) {
    if (domain.includes(key)) return val;
  }
  return "Referral";
}

export default function Sources() {
  const [sources, setSources] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    api.get(`/analytics/traffic-sources?days=${days}&limit=20`)
      .then(({ data }) => setSources(data))
      .catch(() => setSources([]))
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  const total = sources.reduce((s, r) => s + r.sessions, 0);

  // Channel rollup for pie
  const channels = sources.reduce((acc, s) => {
    const ch = classifySource(s.source);
    acc[ch] = (acc[ch] || 0) + s.sessions;
    return acc;
  }, {});
  const pieData = Object.entries(channels).map(([name, value]) => ({ name, value }));

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Traffic Sources</h1>
          <p className="text-xs text-slate-500 mt-0.5">Where your visitors come from</p>
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
        {/* Channel pie */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">By Channel</p>
          {pieData.length === 0 ? (
            <p className="text-xs text-slate-500">No source data yet</p>
          ) : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={160} height={160}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={3} dataKey="value">
                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#1a2235", border: "1px solid #232d42", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#94a3b8" }}
                    itemStyle={{ color: "#e2e8f0" }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 flex-1">
                {pieData.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="text-slate-300 flex-1">{d.name}</span>
                    <span className="text-slate-400">{total ? Math.round((d.value / total) * 100) : 0}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Top referrers */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">Top Referrers</p>
          {loading ? (
            <p className="text-xs text-slate-500">Loading…</p>
          ) : sources.length === 0 ? (
            <p className="text-xs text-slate-500">No referrer data yet</p>
          ) : (
            <div className="space-y-2">
              {sources.map((s, i) => {
                const pct = total ? Math.round((s.sessions / total) * 100) : 0;
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-300 truncate max-w-[200px]">{s.source}</span>
                      <span className="text-slate-400 shrink-0 ml-2">{s.sessions.toLocaleString()} <span className="text-slate-600">({pct}%)</span></span>
                    </div>
                    <div className="h-1 bg-surface-600 rounded-full overflow-hidden">
                      <div className="h-full bg-pulse rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
