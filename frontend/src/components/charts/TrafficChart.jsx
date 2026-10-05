import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format, parseISO } from "date-fns";

const PEOPLE_COLOR = "#10b981";
const AUTOMATED_COLOR = "#ef4444";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-surface-500 bg-surface-700 px-3 py-2.5 text-xs shadow-xl">
      <p className="mb-1.5 text-slate-500">{label}</p>
      {payload.map((point) => (
        <p key={point.name} className="flex items-center gap-2 py-0.5">
          <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: point.color }} />
          <span className="text-slate-400">{point.name}</span>
          <span className="ml-auto font-mono font-medium tabular-nums text-white">{(point.value ?? 0).toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

/**
 * One series, one chart, one y-axis.
 *
 * People and automated traffic differ by two orders of magnitude on a typical
 * site, so drawing them together flattens the human line onto the baseline and
 * the reader learns nothing from it. A second y-axis would be worse: it lets the
 * viewer compare two scales as if they were one. These are small multiples
 * instead, stacked and sharing a time range, each panel scaled to its own series
 * and labelled with its own peak so the difference is stated rather than implied.
 */
function SeriesPanel({ rows, dataKey, name, color, gradientId, height, showAxis }) {
  const peak = rows.reduce((max, row) => Math.max(max, row[dataKey] ?? 0), 0);
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="h-0.5 w-3 rounded-full" style={{ backgroundColor: color }} />
          {name}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-slate-500">
          peak {peak.toLocaleString()}/day
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={rows} margin={{ top: 4, right: 10, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.22} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1a2235" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={showAxis ? { fill: "#64748b", fontSize: 11 } : false}
            height={showAxis ? 20 : 0}
            minTickGap={24}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#64748b", fontSize: 11 }}
            width={42}
            allowDecimals={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#475569", strokeWidth: 1, strokeDasharray: "3 3" }} />
          <Area
            type="monotone"
            dataKey={dataKey}
            name={name}
            stroke={color}
            fill={`url(#${gradientId})`}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function TrafficChart({ data = [] }) {
  const rows = Array.isArray(data) ? data : [];
  const formatted = rows.length
    ? rows.map((row) => ({
        ...row,
        label: format(parseISO(row.date), "MMM d"),
        people: (row?.verified_human ?? 0) + (row?.likely_human ?? 0),
        automated: (row?.ai_crawler_visits ?? 0) + (row?.known_bot_visits ?? 0),
      }))
    : [];

  return (
    <div className="rounded-xl border border-surface-600 bg-surface-800 p-5">
      <div className="mb-4">
        <p className="text-sm font-medium text-slate-200">Visits over time</p>
        <p className="mt-0.5 text-xs text-slate-500">
          Automated and human visits over the selected period. Each chart is scaled to its own
          series, so compare the shapes rather than the heights.
        </p>
      </div>
      {formatted.length === 0 ? (
        <div className="flex h-[240px] items-center justify-center text-xs text-slate-500">No trend data yet</div>
      ) : (
        <div className="space-y-4">
          <SeriesPanel
            rows={formatted}
            dataKey="automated"
            name="Automated"
            color={AUTOMATED_COLOR}
            gradientId="automatedArea"
            height={160}
            showAxis={false}
          />
          <SeriesPanel
            rows={formatted}
            dataKey="people"
            name="People"
            color={PEOPLE_COLOR}
            gradientId="peopleArea"
            height={110}
            showAxis
          />
        </div>
      )}
    </div>
  );
}
