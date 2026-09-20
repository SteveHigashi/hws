import StatTooltip from "./StatTooltip";

export default function StatCard({ id, label, value, sub, accent }) {
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 glow">
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">
        <StatTooltip id={id} value={value}>{label}</StatTooltip>
      </p>
      <p className={`text-3xl font-semibold ${accent ? "text-accent-glow" : "text-white"}`}>
        <StatTooltip id={id} value={value} showIcon={false}>{value ?? "—"}</StatTooltip>
      </p>
      {sub && <p className="text-xs text-slate-500 mt-1"><StatTooltip id={id} value={value} showIcon={false}>{sub}</StatTooltip></p>}
    </div>
  );
}
