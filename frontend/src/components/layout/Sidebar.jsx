import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useAuthStore } from "../../hooks/useAuth";
import { useSiteStore } from "../../store/siteStore";
import api from "../../utils/api";
import clsx from "clsx";

const nav = [
  { label: "Overview",        path: "/dashboard" },
  { label: "Intelligence",    path: "/dashboard/intelligence" },
  { label: "GEO Visibility",  path: "/dashboard/geo-visibility" },
  { label: "AI Crawlers",     path: "/dashboard/ai-crawlers" },
  { label: "Catalogue Protection", path: "/dashboard/catalogue-protection" },
  { label: "Real-time",       path: "/dashboard/realtime" },
  { label: "Live Traffic",    path: "/dashboard/live-traffic" },
  { label: "Session Flow",    path: "/dashboard/flow" },
  { label: "Geography",       path: "/dashboard/geo" },
  { label: "Pages",           path: "/dashboard/pages" },
  { label: "Traffic Sources", path: "/dashboard/sources" },
  { label: "Campaigns",       path: "/dashboard/campaigns" },
  { label: "Devices",         path: "/dashboard/devices" },
  { label: "Errors & Exits",  path: "/dashboard/errors" },
  { label: "Behavior",        path: "/dashboard/behavior" },
  { label: "Import Data",     path: "/dashboard/import" },
];

function instanceLabel() {
  const { hostname, port } = window.location;
  const isLocal = hostname === "localhost" || hostname === "127.0.0.1";
  if (isLocal) return { text: port ? `local :${port}` : "local", dot: "bg-amber-400" };
  return { text: hostname, dot: "bg-emerald-400" };
}

export default function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const { sites, currentSiteId, setSites, setCurrentSite } = useSiteStore();
  const instance = instanceLabel();

  useEffect(() => {
    api.get("/analytics/sites").then(({ data }) => {
      setSites(data);
      // Auto-select first site if nothing persisted
      if (!currentSiteId && data.length > 0) {
        setCurrentSite(data[0].id);
      }
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <aside className="w-52 shrink-0 bg-surface-800 border-r border-surface-600 flex flex-col min-h-screen">
      <div className="p-5 border-b border-surface-600">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2 h-2 rounded-full bg-accent pulse-dot" />
          <span className="text-xs font-mono text-slate-400 uppercase tracking-widest">Higashi</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${instance.dot}`} />
          <span className="text-xs font-mono text-slate-500 truncate" title={instance.text}>{instance.text}</span>
        </div>

        {/* Site switcher */}
        {sites.length > 0 && (
          <select
            value={currentSiteId || ""}
            onChange={(e) => setCurrentSite(e.target.value || null)}
            className="w-full text-xs bg-surface-700 border border-surface-500 text-slate-300 rounded-lg px-2 py-1.5 focus:outline-none focus:border-accent transition-colors cursor-pointer"
          >
            <option value="">All sites</option>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.domain}
              </option>
            ))}
          </select>
        )}
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {nav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/dashboard"}
            className={({ isActive }) =>
              clsx(
                "block px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-accent/10 text-accent font-medium"
                  : "text-slate-400 hover:text-white hover:bg-surface-600"
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-surface-600 space-y-2">
        <NavLink to="/dashboard/account" className="block text-xs text-slate-500 hover:text-slate-300 transition-colors">
          Account
        </NavLink>
        <button
          onClick={logout}
          className="w-full text-left text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
