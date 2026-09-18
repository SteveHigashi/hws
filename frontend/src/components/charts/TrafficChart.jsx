import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-xs shadow-xl">
      <p className="text-slate-500 mb-1.5">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
          <span className="text-slate-400">{p.name}</span>
          <span className="text-white font-medium ml-auto tabular-nums">{p.value.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-4 text-xs text-slate-400">
      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-0.5 rounded-full bg-[#3b82f6]" /> Page views
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-0.5 rounded-full bg-[#94a3b8]" /> Visitors
      </span>
    </div>
  );
}

export default function TrafficChart({ data = [] }) {
  const formatted = data.map((d) => ({
    ...d,
    label: format(parseISO(d.date), "MMM d"),
  }));

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-medium text-slate-300">Traffic over time</p>
        <Legend />
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={formatted} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="gViews" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gVisitors" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#94a3b8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a2235" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="views" name="Page views" stroke="#3b82f6" fill="url(#gViews)" strokeWidth={2} dot={false} />
          <Area type="monotone" dataKey="visitors" name="Visitors" stroke="#94a3b8" fill="url(#gVisitors)" strokeWidth={1.5} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
