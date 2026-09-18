import { useEffect, useState } from "react";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

function Section({ title, sub, children }) {
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
      <p className="text-sm font-medium text-slate-300 mb-1">{title}</p>
      {sub && <p className="text-xs text-slate-500 mb-4">{sub}</p>}
      {!sub && <div className="mb-4" />}
      {children}
    </div>
  );
}

function EmptyState({ text }) {
  return <p className="text-xs text-slate-500">{text}</p>;
}

// ---------------------------------------------------------------------------
// Composite-index helpers — tiers and narrative copy
// ---------------------------------------------------------------------------

function IndexCard({ label, value, suffix, tier, narrative, accent }) {
  return (
    <div className={`bg-surface-800 border rounded-xl p-5 ${accent ? "border-violet-500/40" : "border-surface-600"}`}>
      <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">{label}</p>
      <p className={`text-2xl font-mono font-semibold ${accent ? "text-violet-400" : "text-white"}`}>
        {value ?? "—"}
        {suffix && <span className="text-sm text-slate-500 ml-1">{suffix}</span>}
      </p>
      {tier && <p className={`text-xs font-medium mt-1 ${tier.color}`}>{tier.label}</p>}
      {narrative && <p className="text-xs text-slate-500 mt-2 leading-relaxed">{narrative}</p>}
    </div>
  );
}

function frustrationTier(v) {
  if (v == null) return null;
  if (v < 1)   return { label: "Calm — frictionless",         color: "text-emerald-400" };
  if (v < 5)   return { label: "Mostly fine",                 color: "text-teal-400" };
  if (v < 15)  return { label: "Some friction",               color: "text-amber-400" };
  if (v < 40)  return { label: "Irritated visitors",          color: "text-orange-400" };
  return            { label: "Broken UI — investigate now",   color: "text-danger" };
}

function readingTier(v) {
  if (v == null) return null;
  if (v < 5)   return { label: "Skimmers — bounce-heavy",     color: "text-slate-500" };
  if (v < 15)  return { label: "Browsing, not reading",        color: "text-slate-400" };
  if (v < 35)  return { label: "Engaged readers present",      color: "text-teal-400" };
  if (v < 60)  return { label: "Strong reading intent",        color: "text-violet-400" };
  return            { label: "Devoted audience",                color: "text-amber-400" };
}

function silentTier(v) {
  if (v == null) return null;
  if (v > 90)  return { label: "Pure read-only audience",     color: "text-slate-400" };
  if (v > 70)  return { label: "Mostly lurkers",              color: "text-slate-300" };
  if (v > 50)  return { label: "Mixed — some interact",       color: "text-teal-400" };
  if (v > 25)  return { label: "Interactive crowd",           color: "text-violet-400" };
  return            { label: "Hands-on visitors",              color: "text-amber-400" };
}

// Narrative copy. Returns null when the data can't support a sentence.
function frustrationNarrative(indices) {
  if (!indices?.total_sessions) return null;
  const { frustration_components: c, total_sessions } = indices;
  const total = c.rage + c.dead + c.errors;
  if (total === 0)
    return `Zero rage clicks, dead clicks, or JS errors across ${total_sessions.toLocaleString()} session${total_sessions === 1 ? "" : "s"} — either the UI is solid or visitors didn't hit a problem area yet.`;
  const parts = [];
  if (c.rage)   parts.push(`${c.rage} rage click${c.rage === 1 ? "" : "s"}`);
  if (c.dead)   parts.push(`${c.dead} dead click${c.dead === 1 ? "" : "s"}`);
  if (c.errors) parts.push(`${c.errors} JS error${c.errors === 1 ? "" : "s"}`);
  return `${parts.join(" + ")} across ${total_sessions.toLocaleString()} sessions. Each one is a moment a visitor was frustrated — worth looking at the pages below.`;
}

function readingNarrative(indices) {
  if (!indices?.total_sessions) return null;
  const n = indices.reading_intent_sessions, t = indices.total_sessions;
  if (n === 0)
    return `No visitors selected text or scrolled deep yet. That's a skim-and-leave pattern — common for landing pages or short content.`;
  return `${n.toLocaleString()} of ${t.toLocaleString()} sessions either highlighted text, copied a passage, or scrolled past 75% — signals of actual reading rather than skimming.`;
}

function silentNarrative(indices) {
  if (!indices?.total_sessions) return null;
  const silent = indices.total_sessions - indices.sessions_with_behavior;
  if (silent === indices.total_sessions)
    return `Every session was silent — no clicks, no selections, nothing. Either you're seeing pure read-then-leave traffic or the tracker just started collecting.`;
  return `${silent.toLocaleString()} sessions never clicked, selected, or interacted with anything visible — they just read (or bounced). The other ${indices.sessions_with_behavior.toLocaleString()} actively did something.`;
}

export default function Behavior() {
  const [indices, setIndices] = useState(null);
  const [summary, setSummary] = useState([]);
  const [rageclicks, setRageClicks] = useState([]);
  const [deadclicks, setDeadClicks] = useState([]);
  const [selected, setSelected] = useState([]);
  const [formAbandons, setFormAbandons] = useState([]);
  const [errors, setErrors] = useState([]);
  const [externalClicks, setExternalClicks] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/behavior/indices?days=${days}`),
      api.get(`/behavior/summary?days=${days}`),
      api.get(`/behavior/rage-clicks?days=${days}`),
      api.get(`/behavior/dead-clicks?days=${days}`),
      api.get(`/behavior/selected-text?days=${days}`),
      api.get(`/behavior/form-abandonment?days=${days}`),
      api.get(`/behavior/errors?days=${days}`),
      api.get(`/behavior/external-clicks?days=${days}`),
    ])
      .then(([idx, s, r, d, sel, fa, err, ext]) => {
        setIndices(idx.data);
        setSummary(s.data);
        setRageClicks(r.data);
        setDeadClicks(d.data);
        setSelected(sel.data);
        setFormAbandons(fa.data);
        setErrors(err.data);
        setExternalClicks(ext.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  const noBehaviorYet = !loading && (indices?.total_sessions ?? 0) > 0 && (indices?.sessions_with_behavior ?? 0) === 0;

  const EVENT_LABELS = {
    click: "Clicks", external_click: "External clicks", select: "Text selections",
    copy: "Copies", scroll_pause: "Scroll pauses", tab_blur: "Tab switches",
    tab_focus: "Tab returns", form_field: "Form interactions",
    media: "Media events", error: "JS errors", print: "Prints",
  };
  const EVENT_COLORS = {
    click: "#3b82f6", external_click: "#22d3ee", select: "#10b981",
    copy: "#8b5cf6", scroll_pause: "#f59e0b", tab_blur: "#ef4444",
    error: "#ef4444", print: "#94a3b8", media: "#ec4899",
  };

  const totalEvents = summary.reduce((s, r) => s + r.count, 0);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Behavior</h1>
          <p className="text-xs text-slate-500 mt-0.5">How visitors actually interact with your site</p>
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

      {/* Composite "story" indices */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <IndexCard
          label="Frustration Index"
          value={indices ? indices.frustration_index.toFixed(1) : null}
          suffix="per 100 sessions"
          tier={frustrationTier(indices?.frustration_index)}
          narrative={frustrationNarrative(indices)}
          accent
        />
        <IndexCard
          label="Reading Intent"
          value={indices ? `${indices.reading_intent_pct}%` : null}
          suffix="of sessions"
          tier={readingTier(indices?.reading_intent_pct)}
          narrative={readingNarrative(indices)}
        />
        <IndexCard
          label="Silent Audience"
          value={indices ? `${indices.silent_audience_pct}%` : null}
          suffix="never interact"
          tier={silentTier(indices?.silent_audience_pct)}
          narrative={silentNarrative(indices)}
        />
      </div>

      {/* Tracker-just-started banner: sessions exist but no behavior events */}
      {noBehaviorYet && (
        <div className="bg-surface-800 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3">
          <span className="text-amber-400 text-lg leading-none mt-0.5">⌁</span>
          <div className="text-xs text-slate-400 leading-relaxed">
            <span className="text-amber-400 font-medium">Tracker just started collecting.</span> You have{" "}
            {indices.total_sessions.toLocaleString()} session{indices.total_sessions === 1 ? "" : "s"} but no behavioural events yet.
            Clicks, scrolls, text selections, and JS errors will populate this page as visitors return. The numbers above
            will move from zero as that data arrives.
          </div>
        </div>
      )}

      {/* What these indices mean */}
      <details className="bg-surface-800 border border-surface-600 rounded-xl p-4 text-xs text-slate-500">
        <summary className="cursor-pointer text-slate-400 hover:text-slate-200 select-none">How these three indices are computed</summary>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
          <div className="space-y-1">
            <p className="text-slate-300 font-medium">Frustration Index</p>
            <p>(rage clicks + dead clicks + JS errors) ÷ sessions × 100. Lower is better. Anything &gt;15 means a real chunk of visitors hit something broken or confusing.</p>
          </div>
          <div className="space-y-1">
            <p className="text-slate-300 font-medium">Reading Intent</p>
            <p>% of sessions where someone selected/copied text or scrolled past 75% of a page. A leading indicator of actual engagement — not just pageviews.</p>
          </div>
          <div className="space-y-1">
            <p className="text-slate-300 font-medium">Silent Audience</p>
            <p>% of sessions with zero behavioural events. High silent share isn't bad — it's typical for blog readers or AI-summary fodder. Watch the trend, not the absolute number.</p>
          </div>
        </div>
      </details>

      {/* Event type summary */}
      <Section title="Event Breakdown" sub="All behavioral signals captured">
        {loading ? <EmptyState text="Loading…" />
        : summary.length === 0 ? <EmptyState text="No behavioral data yet. Make sure the tracker is installed." />
        : (
          <div className="space-y-2">
            {summary.map((s, i) => {
              const pct = totalEvents ? Math.round((s.count / totalEvents) * 100) : 0;
              return (
                <div key={i} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300">{EVENT_LABELS[s.type] || s.type}</span>
                    <span className="text-slate-400">{s.count.toLocaleString()} <span className="text-slate-600">({pct}%)</span></span>
                  </div>
                  <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: EVENT_COLORS[s.type] || "#3b82f6" }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Rage clicks */}
        <Section title="Rage Clicks" sub="3+ rapid clicks in same spot — frustration or broken element">
          {loading ? <EmptyState text="Loading…" />
          : rageclicks.length === 0 ? <EmptyState text="No rage clicks detected — good sign." />
          : rageclicks.map((r, i) => (
            <div key={i} className="flex justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
              <span className="text-danger font-mono truncate max-w-[220px]">{_path(r.page)}</span>
              <span className="text-slate-400 shrink-0 ml-2">{r.rage_clicks}×</span>
            </div>
          ))}
        </Section>

        {/* Dead clicks */}
        <Section title="Dead Clicks" sub="Clicks on non-interactive elements — UX confusion">
          {loading ? <EmptyState text="Loading…" />
          : deadclicks.length === 0 ? <EmptyState text="No dead clicks detected." />
          : deadclicks.map((r, i) => (
            <div key={i} className="flex justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
              <div className="min-w-0">
                <span className="text-warn font-mono truncate block max-w-[200px]">{_path(r.page)}</span>
                {r.text && <span className="text-slate-500">"{r.text}"</span>}
              </div>
              <span className="text-slate-400 shrink-0 ml-2">{r.count}×</span>
            </div>
          ))}
        </Section>

        {/* Text selections */}
        <Section title="What People Highlight" sub="Text selected or copied — reading intent signal">
          {loading ? <EmptyState text="Loading…" />
          : selected.length === 0 ? <EmptyState text="No text selection data yet." />
          : selected.map((r, i) => (
            <div key={i} className="flex justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
              <span className="text-slate-300 italic truncate max-w-[220px]">"{r.text}"</span>
              <span className="text-slate-400 shrink-0 ml-2">{r.count}×</span>
            </div>
          ))}
        </Section>

        {/* Form abandonment */}
        <Section title="Form Abandonment" sub="Which field stops visitors from completing forms">
          {loading ? <EmptyState text="Loading…" />
          : formAbandons.length === 0 ? <EmptyState text="No form abandonment data yet." />
          : formAbandons.map((r, i) => (
            <div key={i} className="flex justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
              <div>
                <span className="text-slate-300">{r.field || "unknown field"}</span>
                {r.type && <span className="text-slate-500 ml-2">({r.type})</span>}
                <span className="text-slate-500 block font-mono text-xs">{_path(r.page)}</span>
              </div>
              <span className="text-warn shrink-0 ml-2">{r.abandons} abandon{r.abandons !== 1 ? "s" : ""}</span>
            </div>
          ))}
        </Section>

        {/* JS Errors */}
        <Section title="JavaScript Errors" sub="Errors visitors experienced in their browser">
          {loading ? <EmptyState text="Loading…" />
          : errors.length === 0 ? (
            <div className="flex items-center gap-2">
              <span className="text-success">✓</span>
              <p className="text-xs text-slate-400">No JS errors recorded.</p>
            </div>
          ) : errors.map((r, i) => (
            <div key={i} className="text-xs py-1.5 border-b border-surface-600/50 last:border-0">
              <p className="text-danger truncate">{r.message}</p>
              <p className="text-slate-500 font-mono">{_path(r.page)} — {r.count}×</p>
            </div>
          ))}
        </Section>

        {/* External clicks */}
        <Section title="External Links Clicked" sub="Where you're sending visitors">
          {loading ? <EmptyState text="Loading…" />
          : externalClicks.length === 0 ? <EmptyState text="No external click data yet." />
          : externalClicks.map((r, i) => (
            <div key={i} className="flex justify-between text-xs py-1.5 border-b border-surface-600/50 last:border-0">
              <span className="text-pulse font-mono truncate max-w-[220px]">{_domain(r.url)}</span>
              <span className="text-slate-400 shrink-0 ml-2">{r.clicks}×</span>
            </div>
          ))}
        </Section>
      </div>
    </div>
  );
}

function _path(url) {
  try { return new URL(url).pathname || url; } catch { return url; }
}
function _domain(url) {
  try { return new URL(url).hostname; } catch { return url; }
}
