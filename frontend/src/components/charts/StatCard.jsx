export default function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 glow">
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-3xl font-semibold ${accent ? "text-accent-glow" : "text-white"}`}>
        {value ?? "—"}
      </p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}
