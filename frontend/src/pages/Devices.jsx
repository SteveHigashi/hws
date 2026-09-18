import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

export default function Devices() {
  const [devices, setDevices] = useState([]);
  const [browsers, setBrowsers] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/analytics/devices?days=${days}`),
      api.get(`/analytics/browsers?days=${days}`),
    ])
      .then(([dev, brow]) => {
        setDevices(dev.data);
        setBrowsers(brow.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  const DEVICE_ICON = { desktop: "🖥", mobile: "📱", tablet: "📟" };
  const totalViews = devices.reduce((s, d) => s + d.views, 0);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Devices</h1>
          <p className="text-xs text-slate-500 mt-0.5">Hardware and browser breakdown</p>
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
        {/* Device type */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">Device Type</p>
          {loading ? (
            <p className="text-xs text-slate-500">Loading…</p>
          ) : devices.length === 0 ? (
            <p className="text-xs text-slate-500">No device data yet</p>
          ) : (
            <div className="space-y-4">
              {devices.map((d, i) => {
                const pct = totalViews ? Math.round((d.views / totalViews) * 100) : 0;
                return (
                  <div key={i} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 text-slate-300">
                        <span>{DEVICE_ICON[d.device] || "🌐"}</span>
                        <span className="capitalize">{d.device || "Unknown"}</span>
                      </span>
                      <span className="text-white font-medium">{d.views.toLocaleString()}</span>
                    </div>
                    <div className="h-2 bg-surface-600 rounded-full overflow-hidden">
                      <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                    <p className="text-xs text-slate-500 text-right">{pct}% of traffic</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Browser bar chart */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">Browsers</p>
          {loading ? (
            <p className="text-xs text-slate-500">Loading…</p>
          ) : browsers.length === 0 ? (
            <p className="text-xs text-slate-500">No browser data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={browsers} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a2235" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="browser" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} width={72} />
                <Tooltip
                  contentStyle={{ background: "#1a2235", border: "1px solid #232d42", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#94a3b8" }}
                  itemStyle={{ color: "#e2e8f0" }}
                />
                <Bar dataKey="views" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Views" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
