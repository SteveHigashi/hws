const SEVERITY_STYLE = {
  high:   { dot: "bg-danger",    bg: "border-danger/20 bg-danger/5" },
  medium: { dot: "bg-warn",      bg: "border-warn/20 bg-warn/5" },
  info:   { dot: "bg-accent",    bg: "border-accent/20 bg-accent/5" },
  low:    { dot: "bg-slate-500", bg: "border-surface-500 bg-surface-700" },
};

export default function InsightsFeed({ insights: rawInsights = [], loading, enrichMeta, enrichLoading }) {
  const insights = Array.isArray(rawInsights) ? rawInsights : [];
  if (loading) {
    return (
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
        <p className="text-sm font-medium text-slate-300 mb-3">Intelligence</p>
        <p className="text-xs text-slate-500">Analyzing patterns…</p>
      </div>
    );
  }

  const hasEnrichment = insights.some((ins) => ins.interpretation);

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 glow">
      <div className="flex items-center gap-2 mb-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" />
        <p className="text-sm font-medium text-slate-300">Intelligence</p>
        <span className="ml-auto text-xs text-slate-500">
          {insights.length} insight{insights.length !== 1 ? "s" : ""}
        </span>
        {enrichLoading && (
          <span className="text-xs text-slate-600 animate-pulse">Enriching…</span>
        )}
        {!enrichLoading && enrichMeta && !enrichMeta.skipped && !enrichMeta.budget_exceeded && (
          <span className="text-xs text-slate-600 font-mono" title={`${enrichMeta.input_tokens} in / ${enrichMeta.output_tokens} out tokens`}>
            {enrichMeta.model_display_name} · ${enrichMeta.estimated_cost_usd?.toFixed(4)}
          </span>
        )}
        {!enrichLoading && enrichMeta?.budget_exceeded && (
          <span className="text-xs text-amber-500/80" title="Set a higher budget in Intelligence → AI Settings">
            Budget limit reached
          </span>
        )}
      </div>

      {insights.length === 0 ? (
        <p className="text-xs text-slate-500">
          No significant patterns detected yet. Insights appear as traffic accumulates.
        </p>
      ) : (
        <div className="space-y-3">
          {insights.map((ins, i) => {
            const s = SEVERITY_STYLE[ins.severity] || SEVERITY_STYLE.info;
            return (
              <div key={i} className={`border rounded-lg px-4 py-3 ${s.bg}`}>
                <div className="flex items-start gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${s.dot}`} />
                  <div className="flex-1">
                    <p className="text-sm text-slate-200 leading-relaxed">{ins.text}</p>
                    {ins.interpretation && (
                      <div className="mt-2.5 pt-2.5 border-t border-slate-700/50 space-y-2">
                        <p className="text-xs text-slate-400 leading-relaxed">{ins.interpretation}</p>
                        {ins.options?.length > 0 && (
                          <div className="space-y-1.5">
                            <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Possible approaches</p>
                            {ins.options.map((opt, j) => (
                              <p key={j} className="text-xs text-slate-300 leading-relaxed pl-3 border-l border-slate-600">
                                {opt}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
