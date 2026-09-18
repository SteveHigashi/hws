import { useEffect, useState } from "react";
import { apiUrl } from "../../utils/api";

const DEVICE_ICON = { desktop: "🖥", mobile: "📱", tablet: "📟" };

export default function RealtimeFeed() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = JSON.parse(localStorage.getItem("ha-auth") || "{}")?.state?.token;
    if (!token) return;
    const siteId = JSON.parse(localStorage.getItem("ha-site") || "{}")?.state?.currentSiteId;
    const qs = siteId ? `&site_id=${siteId}` : "";

    const es = new EventSource(apiUrl(`/intelligence/realtime?token=${token}${qs}`));
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.length) {
          setEvents((prev) => {
            const merged = [...data, ...prev];
            const seen = new Set();
            return merged.filter((ev) => {
              if (seen.has(ev.id)) return false;
              seen.add(ev.id);
              return true;
            }).slice(0, 30);
          });
        }
      } catch {}
    };

    return () => es.close();
  }, []);

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 glow">
      <div className="flex items-center gap-2 mb-4">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-success pulse-dot" : "bg-slate-600"}`} />
        <p className="text-sm font-medium text-slate-300">Real-time</p>
        <span className="ml-auto text-xs text-slate-500">{connected ? "live" : "connecting…"}</span>
      </div>

      {events.length === 0 ? (
        <p className="text-xs text-slate-500">Waiting for visitors…</p>
      ) : (
        <div className="space-y-1.5 max-h-72 overflow-y-auto">
          {events.map((ev) => (
            <div key={ev.id} className="flex items-center gap-3 text-xs py-1.5 border-b border-surface-600 last:border-0">
              <span className="text-base shrink-0">{DEVICE_ICON[ev.device] || "🌐"}</span>
              <span className="text-slate-400 shrink-0 w-6 font-mono">{ev.country || "—"}</span>
              <span className="text-slate-300 truncate font-mono">{_shortPath(ev.page)}</span>
              <span className="text-slate-600 shrink-0 ml-auto">{_relTime(ev.time)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function _shortPath(url) {
  try { return new URL(url).pathname; } catch { return url; }
}

function _relTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return `${diff}s`;
  return `${Math.floor(diff / 60)}m`;
}
