import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const AI_COLOR = "#ef4444";
const BOT_COLOR = "#f59e0b";

function verificationText(verification) {
  if ((verification?.forged ?? 0) > 0) return "Forged identity";
  if ((verification?.verified ?? 0) > 0 && (verification?.unverified ?? 0) === 0) return "Verified identity";
  if ((verification?.verified ?? 0) > 0) return "Partly verified";
  return "Unverified identity";
}

function CrawlerTooltip({ active, payload }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="min-w-[190px] rounded-lg border border-surface-500 bg-surface-700 px-3 py-2.5 text-xs shadow-xl">
      <p className="font-mono font-semibold text-white">{row.name}</p>
      <p className="mt-1 text-slate-400">{row.category_label || "Automated traffic"} · {verificationText(row.verification)}</p>
      <div className="mt-2 flex items-center justify-between gap-5">
        <span className="text-slate-500">Requests</span>
        <span className="font-mono text-white">{(row.total ?? 0).toLocaleString()}</span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-5">
        <span className="text-slate-500">Pages taken</span>
        <span className="font-mono text-white">{(row.unique_pages ?? 0).toLocaleString()}</span>
      </div>
    </div>
  );
}

export default function WhoFetchedYou({ rows, loading, limit = 6 }) {
  const all = Array.isArray(rows) ? rows : [];
  const top = all.length ? all.slice(0, limit) : [];

  return (
    <section className="overflow-hidden rounded-xl border border-surface-600 bg-surface-800">
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pb-2 pt-5">
        <div>
          <h2 className="text-sm font-medium text-slate-200">Crawler breakdown</h2>
          <p className="mt-0.5 text-xs text-slate-500">Requests by crawler, with identity and pages-taken detail on hover</p>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400">
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-danger" />AI crawlers</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-warn" />Other bots</span>
          {all.length > limit && <Link to="/dashboard/ai-crawlers" className="text-accent hover:underline">All {all.length}</Link>}
        </div>
      </div>

      {loading ? (
        <p className="px-5 pb-5 text-xs text-slate-500">Counting what arrived…</p>
      ) : top.length === 0 ? (
        <p className="px-5 pb-5 text-xs text-slate-500">Nothing automated reached your site in this period.</p>
      ) : (
        <div className="h-[286px] px-2 pb-4 pr-5">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top} layout="vertical" margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="#1a2235" horizontal={false} strokeDasharray="3 3" />
              <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: "#64748b", fontSize: 10 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={104} tick={{ fill: "#cbd5e1", fontSize: 11, fontFamily: "JetBrains Mono" }} />
              <Tooltip content={<CrawlerTooltip />} cursor={{ fill: "#121829", opacity: 0.7 }} />
              <Bar dataKey="total" name="Requests" radius={[0, 5, 5, 0]} maxBarSize={16}>
                {top.map((row) => (
                  <Cell key={`${row?.name}-${row?.category}`} fill={row?.category === "ai_crawler" ? AI_COLOR : BOT_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
