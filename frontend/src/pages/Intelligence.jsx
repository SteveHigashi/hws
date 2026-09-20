import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import InsightsFeed from "../components/charts/InsightsFeed";
import api, { apiUrl } from "../utils/api";
import { useSiteStore } from "../store/siteStore";
import { useAuthStore } from "../hooks/useAuth";

const SITE_TYPES = [
  { value: "business", label: "Business" },
  { value: "blog", label: "Blog" },
  { value: "shop", label: "Shop" },
  { value: "directory", label: "Directory" },
  { value: "other", label: "Other" },
];

// The five stance options come from the backend (higashi_reading.crawlers.STANCES) so the
// dashboard, the signup page and the reading rules say the same thing. This is the fallback
// while /admin/settings/live has not answered yet.
const AI_STANCES = [
  { value: "allow_all", label: "Allow all known crawlers" },
  { value: "refuse_training", label: "Refuse training crawlers" },
  { value: "refuse_training_seo", label: "Refuse training crawlers and SEO tools" },
  { value: "keep_search_only", label: "Keep search only" },
  { value: "refuse_all", label: "Refuse all crawler classes" },
];

function timeAgo(isoString) {
  if (!isoString) return "";
  const diff = Math.floor((Date.now() - new Date(isoString + "Z").getTime()) / 1000);
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function LiveSettingsPanel({ forceOpen }) {
  const cardRef = useRef(null);
  const keyRef = useRef(null);
  const savedTimer = useRef(null);
  const [settings, setSettings] = useState(null); // {live_key_set, live_url, site_type, ai_stance}
  const [status, setStatus] = useState(null); // {key_set, last_send, last_reading_at}
  const [keyInput, setKeyInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [siteType, setSiteType] = useState("other");
  const [aiStance, setAiStance] = useState("refuse_training");
  const [stanceOptions, setStanceOptions] = useState(AI_STANCES);
  const [showUrl, setShowUrl] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [keyError, setKeyError] = useState("");

  const refresh = () => {
    api.get("/admin/settings/live").then(({ data }) => {
      setSettings(data);
      setUrlInput(data.live_url || "");
      setSiteType(data.site_type || "other");
      setAiStance(data.stance || data.ai_stance || "refuse_training");
      if (Array.isArray(data.stance_options) && data.stance_options.length) setStanceOptions(data.stance_options);
    }).catch(() => {});
    api.get("/live/status").then(({ data }) => setStatus(data)).catch(() => {});
  };

  useEffect(() => { refresh(); return () => clearTimeout(savedTimer.current); }, []);
  useEffect(() => {
    if (!forceOpen) return;
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    keyRef.current?.focus({ preventScroll: true });
  }, [forceOpen]);

  const watching = status?.key_set ?? settings?.live_key_set;
  const validKey = /^hl_\S{43}$/.test(keyInput);
  const invalidKey = keyInput.length > 0 && !validKey;

  const handleSave = async (keyRequired = false) => {
    if (saving) return;
    if (keyRequired && !validKey) {
      setKeyError("That is not a Live key — it should start with hl_ and be 46 characters");
      return;
    }
    setSaving(true);
    setSaved(false);
    setKeyError("");
    clearTimeout(savedTimer.current);
    try {
      await api.post("/admin/settings/live", {
        live_key: keyInput.trim(),
        live_url: urlInput.trim(),
        site_type: siteType,
        ai_stance: aiStance,
      });
      setKeyInput("");
      refresh();
      setSaved(true);
      savedTimer.current = setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setKeyError(err.response?.data?.detail || "Could not save the Live key");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    if (!window.confirm("Stop watching this site with Higashi Live?")) return;
    await api.delete("/admin/settings/live");
    refresh();
  };

  const statusLine = watching
    ? status?.last_reading_at
      ? `Watching · last reading ${timeAgo(status.last_reading_at)}`
      : "Watching · no reading yet"
    : "Not watching";

  return (
    <div ref={cardRef} className="bg-violet-500/5 border border-violet-500/40 rounded-xl px-5 py-5 space-y-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-violet-400 text-sm" aria-hidden="true">✦</span>
        <h2 className="text-xs font-semibold uppercase tracking-widest text-violet-300">HIGASHI LIVE</h2>
        <span className="text-xs text-slate-400 sm:ml-auto">{statusLine}</span>
      </div>
      <p className="text-sm text-slate-200">The key from your Higashi Live email goes here. It is not an AI key.</p>
      <div className="space-y-5">
          <p className="text-xs text-slate-500 leading-relaxed">
            Higashi Live checks whether this is normal for a site your size and tells you when
            something changes.{" "}
            <a
              href="https://cloudanalyst.net/live"
              target="_blank"
              rel="noopener noreferrer"
              className="text-violet-400 hover:text-violet-300 underline"
            >
              What is Live?
            </a>
          </p>

          {watching ? (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
              <span>Live key configured</span>
              <button onClick={handleRemove} className="text-slate-600 hover:text-red-400 ml-2">Remove</button>
              {saved && <button disabled className="ml-auto px-4 py-2 bg-violet-600 text-white text-sm rounded-lg">Saved ✓</button>}
            </div>
          ) : (
            <div>
              <label htmlFor="live-key" className="text-xs text-slate-300 font-medium block mb-1.5">Live key</label>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  ref={keyRef}
                  id="live-key"
                  type="password"
                  value={keyInput}
                  onChange={(e) => { setKeyInput(e.target.value); setKeyError(""); setSaved(false); }}
                  onPaste={(e) => { e.preventDefault(); setKeyInput(e.clipboardData.getData("text").trim()); setKeyError(""); setSaved(false); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && validKey) handleSave(true); }}
                  placeholder="hl_…"
                  autoComplete="off"
                  aria-invalid={invalidKey || Boolean(keyError)}
                  aria-describedby="live-key-help live-key-error"
                  className="w-full min-w-0 flex-1 bg-surface-700 border border-surface-500 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/60 font-mono"
                />
                <button
                  onClick={() => handleSave(true)}
                  disabled={saving || !validKey}
                  className="w-full sm:w-auto px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm rounded-lg transition-colors whitespace-nowrap"
                >
                  {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
                </button>
              </div>
              <p id="live-key-help" className="text-xs text-slate-500 mt-1.5">46 characters, starts with hl_</p>
            </div>
          )}
          {(invalidKey || keyError) && <p id="live-key-error" role="alert" className="text-xs text-red-400">{keyError || "That is not a Live key — it should start with hl_ and be 46 characters"}</p>}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider font-medium block mb-1.5">
                What is this site?
              </label>
              <select
                value={siteType}
                onChange={(e) => setSiteType(e.target.value)}
                className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500/60"
              >
                {SITE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider font-medium block mb-1.5">
                How do you feel about AI reading your site?
              </label>
              <select
                value={aiStance}
                onChange={(e) => setAiStance(e.target.value)}
                className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500/60"
              >
                {stanceOptions.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              {(() => {
                const chosen = stanceOptions.find((s) => s.value === aiStance);
                return chosen?.does ? (
                  <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                    {chosen.does} {chosen.does_not} <span className="text-slate-400">Cost: {chosen.cost}</span>
                  </p>
                ) : null;
              })()}
            </div>
          </div>

          {watching && (siteType !== settings?.site_type || aiStance !== (settings?.stance || settings?.ai_stance)) && (
            <button onClick={() => handleSave()} disabled={saving} className="text-xs text-accent hover:underline">
              {saving ? "Saving…" : "Save changes to site type / AI stance"}
            </button>
          )}
          {!watching && (
            <p className="text-xs text-slate-600">These shape the reading Live sends back — change them anytime.</p>
          )}

          <details className="text-xs" open={showUrl}>
            <summary
              onClick={(e) => { e.preventDefault(); setShowUrl((v) => !v); }}
              className="cursor-pointer text-slate-500"
            >
              Advanced: Live URL
            </summary>
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://intel.cloudanalyst.net"
              className="mt-2 w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-violet-500/60"
            />
          </details>
      </div>
    </div>
  );
}

const QUALITY_BADGE = {
  fast:     "bg-green-500/15 text-green-400",
  balanced: "bg-blue-500/15 text-blue-400",
  premium:  "bg-violet-500/15 text-violet-400",
};

const PROVIDER_LABEL = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
};

// One choice: who writes the walk reading shown on Overview. The rules are the
// ceiling whichever is picked; the model, if any, only writes the prose.
function ReadingProviderPanel() {
  const [cfg, setCfg] = useState(null); // {provider, model, live_key_set, keys_set}
  const [provider, setProvider] = useState("local");
  const [msg, setMsg] = useState("");

  const load = () => api.get("/admin/settings/reading").then(({ data }) => { setCfg(data); setProvider(data.provider); }).catch(() => {});
  useEffect(() => { load(); }, []);

  const save = async (value) => {
    setProvider(value);
    setMsg("");
    try {
      await api.post("/admin/settings/reading", { provider: value, model: cfg?.model || "" });
      setMsg("Saved");
      setTimeout(() => setMsg(""), 2000);
      load();
    } catch (err) {
      setMsg(err.response?.data?.detail || "Error");
      load();
    }
  };

  const anyKey = cfg && Object.values(cfg.keys_set || {}).some(Boolean);
  const options = [
    { value: "local", label: "Higashi rules", hint: "Fixed rules on this install. Free. Nothing leaves this box." },
    { value: "byok", label: "Bring your own AI key", hint: anyKey ? `Your own model key (${cfg?.model}). Still local; the rules stay the ceiling.` : "Add a model key below first." },
    { value: "live", label: "Use Higashi Live", hint: cfg?.live_key_set ? "History, comparisons to similar sites, weekly email." : "Add a Live key above first." },
  ];

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl px-5 py-4 space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-slate-300">Explain crawler activity with</span>
        {msg && <span className="text-xs text-slate-500">{msg}</span>}
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {options.map((o) => {
          const disabled = (o.value === "byok" && !anyKey) || (o.value === "live" && !cfg?.live_key_set);
          const active = provider === o.value;
          return (
            <button
              key={o.value}
              type="button"
              disabled={disabled}
              onClick={() => save(o.value)}
              className={`text-left rounded-lg border px-3 py-2.5 transition-colors disabled:opacity-40 ${active ? "border-violet-500/60 bg-violet-500/10" : "border-surface-600 hover:bg-surface-700/50"}`}
            >
              <p className="text-sm text-slate-200">{o.label}</p>
              <p className="text-xs text-slate-500 mt-0.5">{o.hint}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}


function AISettingsPanel() {
  const [open, setOpen] = useState(false);
  const [usage, setUsage] = useState(null);
  const [models, setModels] = useState(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [keyInputs, setKeyInputs] = useState({ openai: "", google: "" });
  const [keyMsg, setKeyMsg] = useState({});

  const refresh = () => {
    api.get("/admin/settings/ai/usage").then(({ data }) => setUsage(data)).catch(() => {});
    api.get("/admin/settings/ai/models").then(({ data }) => setModels(data)).catch(() => {});
  };

  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    if (models) setBudgetInput(models.monthly_budget_usd > 0 ? String(models.monthly_budget_usd) : "");
  }, [models]);

  const handleSaveBudget = async () => {
    if (!models) return;
    setSaving(true); setSaveMsg("");
    try {
      await api.post("/admin/settings/ai/budget", {
        monthly_budget_usd: parseFloat(budgetInput) || 0,
        default_model: models.default_model,
      });
      refresh();
      setSaveMsg("Saved");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch { setSaveMsg("Error"); } finally { setSaving(false); }
  };

  const selectModel = async (modelId) => {
    if (!models) return;
    setModels((prev) => ({
      ...prev,
      default_model: modelId,
      models: prev.models.map((m) => ({ ...m, is_default: m.id === modelId })),
    }));
    try {
      await api.post("/admin/settings/ai/budget", {
        monthly_budget_usd: parseFloat(budgetInput) || 0,
        default_model: modelId,
      });
      setSaveMsg("Model saved"); setTimeout(() => setSaveMsg(""), 2000);
    } catch { setSaveMsg("Error"); }
  };

  const saveProviderKey = async (provider) => {
    const key = keyInputs[provider]?.trim();
    if (!key) return;
    try {
      await api.post("/admin/settings/ai/provider-key", { provider, api_key: key });
      setKeyInputs((p) => ({ ...p, [provider]: "" }));
      setKeyMsg((p) => ({ ...p, [provider]: "Saved" }));
      setTimeout(() => setKeyMsg((p) => ({ ...p, [provider]: "" })), 2000);
      refresh();
    } catch { setKeyMsg((p) => ({ ...p, [provider]: "Error" })); }
  };

  const removeProviderKey = async (provider) => {
    try {
      await api.delete(`/admin/settings/ai/provider-key/${provider}`);
      setKeyMsg((p) => ({ ...p, [provider]: "Removed" }));
      setTimeout(() => setKeyMsg((p) => ({ ...p, [provider]: "" })), 2000);
      refresh();
    } catch { }
  };

  const defaultModel = models?.models?.find((m) => m.is_default);
  const spendPct = usage?.budget_set && usage.monthly_budget_usd > 0
    ? Math.min(100, (usage.monthly_spend_usd / usage.monthly_budget_usd) * 100)
    : null;

  const modelsByProvider = models
    ? ["anthropic", "openai", "google"].map((p) => ({
        provider: p,
        configured: models.configured_providers?.includes(p),
        models: models.models.filter((m) => m.provider === p),
      }))
    : [];

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-surface-700/50 transition-colors"
      >
        <span className="text-slate-500 text-xs">⚙</span>
        <span className="text-sm font-medium text-slate-300">AI Enrichment Settings</span>
        {defaultModel && <span className="text-xs text-slate-500 ml-1">{defaultModel.display_name}</span>}
        {usage && (
          <span className="text-xs text-slate-500 ml-auto mr-2">
            ${usage.monthly_spend_usd.toFixed(4)} this month
            {usage.budget_set && ` / $${usage.monthly_budget_usd}`}
          </span>
        )}
        <span className="text-slate-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      <p className="px-5 pb-3 text-xs text-slate-500">Your own model keys. Not the Live key.</p>

      {open && (
        <div className="border-t border-surface-600 px-5 py-5 space-y-6">

          {/* Usage meter */}
          {usage && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Usage this month</span>
                <span className="font-mono">
                  ${usage.monthly_spend_usd.toFixed(4)}
                  {usage.budget_set ? ` / $${usage.monthly_budget_usd} budget` : " (no budget set)"}
                </span>
              </div>
              {spendPct !== null && (
                <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${spendPct >= 90 ? "bg-danger" : spendPct >= 70 ? "bg-warn" : "bg-accent"}`}
                    style={{ width: `${spendPct}%` }}
                  />
                </div>
              )}
              <p className="text-xs text-slate-600">{usage.calls_this_month} AI calls this month</p>
            </div>
          )}

          {/* Provider keys */}
          <div className="space-y-3">
            <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">API Keys</p>
            {/* Anthropic already managed above — show status only */}
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className={`w-1.5 h-1.5 rounded-full ${models?.configured_providers?.includes("anthropic") ? "bg-green-400" : "bg-slate-600"}`} />
              <span>Anthropic — managed in "Ask your data" panel above</span>
            </div>
            {["openai", "google"].map((p) => {
              const configured = models?.configured_providers?.includes(p);
              return (
                <div key={p} className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${configured ? "bg-green-400" : "bg-slate-600"}`} />
                  <span className="text-xs text-slate-400 w-20 shrink-0">{PROVIDER_LABEL[p]}</span>
                  {configured ? (
                    <>
                      <span className="text-xs text-green-400 font-mono">Configured</span>
                      <button onClick={() => removeProviderKey(p)} className="text-xs text-slate-600 hover:text-red-400 ml-2">Remove</button>
                    </>
                  ) : (
                    <input
                      type="password"
                      value={keyInputs[p] || ""}
                      onChange={(e) => setKeyInputs((prev) => ({ ...prev, [p]: e.target.value }))}
                      onKeyDown={(e) => e.key === "Enter" && saveProviderKey(p)}
                      placeholder={p === "openai" ? "sk-…" : "AIza…"}
                      className="flex-1 bg-surface-700 border border-surface-500 rounded-lg px-3 py-1 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent/60 font-mono"
                    />
                  )}
                  {!configured && (
                    <button
                      onClick={() => saveProviderKey(p)}
                      disabled={!keyInputs[p]?.trim()}
                      className="px-3 py-1 bg-accent/20 hover:bg-accent/40 disabled:opacity-30 text-accent text-xs rounded-lg transition-colors"
                    >
                      Save
                    </button>
                  )}
                  {keyMsg[p] && <span className="text-xs text-green-400">{keyMsg[p]}</span>}
                </div>
              );
            })}
          </div>

          {/* Model selector grouped by provider */}
          {models && (
            <div className="space-y-3">
              <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Default enrichment model</p>
              {modelsByProvider.map(({ provider, configured, models: pModels }) => (
                <div key={provider}>
                  <p className="text-[11px] text-slate-500 mb-2 flex items-center gap-1.5">
                    <span className={`w-1 h-1 rounded-full ${configured ? "bg-green-400" : "bg-slate-600"}`} />
                    {PROVIDER_LABEL[provider]}
                    {!configured && <span className="text-slate-600">— add key above to enable</span>}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {pModels.map((m) => (
                      <button
                        key={m.id}
                        onClick={() => configured && selectModel(m.id)}
                        disabled={!configured}
                        className={`text-left p-3 rounded-lg border transition-colors space-y-1 ${
                          m.is_default
                            ? "border-accent/60 bg-accent/5"
                            : configured
                            ? "border-surface-500 bg-surface-700 hover:border-slate-500"
                            : "border-surface-600 bg-surface-800 opacity-40 cursor-not-allowed"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-slate-200">{m.display_name}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${QUALITY_BADGE[m.quality_tier] || QUALITY_BADGE.fast}`}>
                            {m.quality_tier}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-snug">{m.description}</p>
                        <p className="text-[11px] font-mono text-slate-400">
                          ${m.input_cost_per_mtok}/M in · ${m.output_cost_per_mtok}/M out
                        </p>
                        {m.is_default && <span className="text-[10px] text-accent font-medium">● Selected</span>}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Budget */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400 uppercase tracking-wider font-medium block">Monthly budget cap (USD)</label>
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">$</span>
              <input
                type="number" min="0" step="0.50"
                value={budgetInput}
                onChange={(e) => setBudgetInput(e.target.value)}
                placeholder="0 = no limit"
                className="w-36 bg-surface-700 border border-surface-500 rounded-lg px-3 py-1.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent/60 font-mono"
              />
              <button onClick={handleSaveBudget} disabled={saving}
                className="px-4 py-1.5 bg-accent hover:bg-accent/80 disabled:opacity-40 text-white text-xs rounded-lg transition-colors">
                {saving ? "Saving…" : "Save"}
              </button>
              {saveMsg && <span className="text-xs text-green-400">{saveMsg}</span>}
            </div>
            <p className="text-xs text-slate-600">Enrichment stops for the rest of the month when the cap is hit. Set 0 for no limit.</p>
          </div>

        </div>
      )}
    </div>
  );
}

const SUGGESTED = [
  "What should I focus on improving first?",
  "Why did my traffic change recently?",
  "Which pages are performing best and why?",
];

function SummaryCard({ summary, loading }) {
  if (loading) {
    return (
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-6">
        <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">Site Brief</p>
        <p className="text-sm text-slate-500">Synthesizing data…</p>
      </div>
    );
  }
  if (!summary || !summary.narrative) return null;

  const delta = summary.stats?.view_delta_pct;
  const deltaColor = delta > 0 ? "text-green-400" : delta < 0 ? "text-danger" : "text-slate-400";
  const deltaSymbol = delta > 0 ? "↑" : delta < 0 ? "↓" : "";

  return (
    <div className="bg-surface-800 border border-violet-500/25 rounded-xl p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-widest mb-1">Site Brief</p>
          <h2 className="text-lg font-semibold text-white leading-snug">{summary.headline}</h2>
        </div>
        {delta != null && (
          <span className={`text-2xl font-mono font-bold shrink-0 ${deltaColor}`}>
            {deltaSymbol}{Math.abs(delta)}%
          </span>
        )}
      </div>

      <p className="text-sm text-slate-300 leading-relaxed">{summary.narrative}</p>

      <div className="flex flex-wrap gap-3 pt-1 border-t border-surface-600">
        {[
          { label: "Page Views",    value: summary.stats?.views?.toLocaleString() },
          { label: "Visitors",      value: summary.stats?.visitors?.toLocaleString() },
          { label: "Bounce Rate",   value: summary.stats?.bounce_rate != null ? `${summary.stats.bounce_rate}%` : null },
          { label: "AI Visibility", value: summary.stats?.ai_visibility_index != null ? `${summary.stats.ai_visibility_index}/100` : null },
          { label: "AI Systems",    value: summary.stats?.ai_crawler_systems > 0 ? summary.stats.ai_crawler_systems : null },
        ]
          .filter((s) => s.value != null)
          .map((s) => (
            <div key={s.label} className="bg-surface-700 rounded-lg px-3 py-1.5">
              <p className="text-xs text-slate-500">{s.label}</p>
              <p className="text-sm font-mono text-slate-200">{s.value}</p>
            </div>
          ))}
      </div>
    </div>
  );
}

function AskChat({ days, currentSiteId }) {
  const { role } = useAuthStore();
  const isAdmin = role === "admin";

  const [aiStatus, setAiStatus] = useState(null); // null=loading, {configured,key_preview}
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);

  // Setup form state
  const [keyInput, setKeyInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [securityAck, setSecurityAck] = useState(false);

  const bottomRef = useRef(null);

  useEffect(() => {
    if (isAdmin) {
      api.get("/admin/settings/ai")
        .then(({ data }) => setAiStatus(data))
        .catch(() => setAiStatus({ configured: false, key_preview: null }));
    } else {
      // Non-admins: assume configured (backend will return an error if not)
      setAiStatus({ configured: true, key_preview: null });
    }
  }, [isAdmin]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSaveKey = async () => {
    if (!keyInput.trim() || !securityAck) return;
    setSaving(true);
    setSaveError("");
    try {
      await api.post("/admin/settings/ai", { anthropic_api_key: keyInput.trim() });
      setKeyInput("");
      // Re-fetch status to get preview
      const { data } = await api.get("/admin/settings/ai");
      setAiStatus(data);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setSaveError(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveKey = async () => {
    if (!window.confirm("Remove the API key? The chat feature will stop working.")) return;
    await api.delete("/admin/settings/ai");
    setAiStatus({ configured: false, key_preview: null });
    setMessages([]);
  };

  const handleAsk = async (question) => {
    if (!question.trim() || streaming) return;
    const q = question.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setStreaming(true);
    setMessages((prev) => [...prev, { role: "assistant", text: "" }]);

    try {
      const stored = JSON.parse(localStorage.getItem("ha-auth") || "{}");
      const token = stored?.state?.token;
      const siteState = JSON.parse(localStorage.getItem("ha-site") || "{}");
      const siteId = currentSiteId || siteState?.state?.currentSiteId;

      const res = await fetch(apiUrl("/intelligence/ask"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ question: q, days, site_id: siteId }),
      });

      if (!res.ok) {
        setMessages((prev) => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = { role: "assistant", text: `Error: ${res.statusText}` };
          return msgs;
        });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = { role: "assistant", text: msgs[msgs.length - 1].text + chunk };
          return msgs;
        });
      }
    } catch (err) {
      setMessages((prev) => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = { role: "assistant", text: `Error: ${err.message}` };
        return msgs;
      });
    } finally {
      setStreaming(false);
    }
  };

  // --- Render: setup panel for admins when no key ---
  if (aiStatus === null) {
    return (
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
        <p className="text-xs text-slate-500">Checking AI status…</p>
      </div>
    );
  }

  if (!aiStatus.configured && isAdmin) {
    return (
      <div className="bg-surface-800 border border-violet-500/30 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-600 flex items-center gap-2">
          <span className="text-violet-400">✦</span>
          <p className="text-sm font-medium text-slate-200">Ask your data</p>
          <span className="text-xs text-slate-500 ml-auto">Powered by Claude</span>
        </div>
        <div className="px-5 py-6 space-y-4">
          <div>
            <p className="text-sm text-slate-300 font-medium mb-1">Add your Anthropic API key to enable AI chat</p>
            <p className="text-xs text-slate-500 leading-relaxed">
              It's used to call Claude with your real analytics data so you can ask questions in plain English.{" "}
              <a
                href="https://console.anthropic.com/settings/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-400 hover:text-violet-300 underline"
              >
                Get a key at console.anthropic.com
              </a>
            </p>
          </div>
          <div className="flex gap-2">
            <input
              type="password"
              value={keyInput}
              onChange={(e) => { setKeyInput(e.target.value); setSaveError(""); }}
              onKeyDown={(e) => e.key === "Enter" && handleSaveKey()}
              placeholder="sk-ant-api03-…"
              autoComplete="off"
              className="flex-1 bg-surface-700 border border-surface-500 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/60 font-mono"
            />
            <button
              onClick={handleSaveKey}
              disabled={saving || !keyInput.trim() || !securityAck}
              className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 text-white text-sm rounded-lg transition-colors whitespace-nowrap"
            >
              {saving ? "Verifying…" : "Save & Verify"}
            </button>
          </div>
          {saveError && (
            <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
              {saveError}
            </p>
          )}

          <div className="bg-surface-900/60 border border-surface-600 rounded-lg px-4 py-3.5">
            <p className="text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-2">Security, plainly</p>
            <ul className="text-xs text-slate-400 space-y-1.5 mb-3 list-disc pl-4">
              <li>Validated against Anthropic before saving, and never sent back to your browser afterward &mdash; only a masked preview.</li>
              <li>Only an admin account can add, view a preview of, or remove this key.</li>
              <li>It's stored in a config file outside the web root, not the downloadable database &mdash; but it is <strong className="text-slate-300">not encrypted at rest</strong>, unlike saved SSH pull passwords. Treat this server the way you'd treat any file holding a live API key.</li>
            </ul>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={securityAck}
                onChange={(e) => setSecurityAck(e.target.checked)}
                className="mt-0.5 shrink-0"
              />
              <span className="text-xs text-slate-400">I understand how this key is protected, and that keeping this server itself secure is on me.</span>
            </label>
          </div>

          <p className="text-xs text-slate-600">
            Use HTTPS in production. The key is validated against Anthropic before saving.
          </p>
        </div>
      </div>
    );
  }

  if (!aiStatus.configured && !isAdmin) {
    return (
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
        <p className="text-xs text-slate-500">AI chat is not configured. Ask your admin to add an Anthropic API key.</p>
      </div>
    );
  }

  // --- Render: chat interface ---
  return (
    <div className="bg-surface-800 border border-violet-500/30 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-surface-600 flex items-center gap-2">
        <span className="text-violet-400">✦</span>
        <p className="text-sm font-medium text-slate-200">Ask your data</p>
        {isAdmin && aiStatus.key_preview && (
          <span className="text-xs text-slate-600 font-mono ml-1">{aiStatus.key_preview}</span>
        )}
        <span className="text-xs text-slate-500 ml-auto">Powered by Claude</span>
        {isAdmin && (
          <button
            onClick={handleRemoveKey}
            className="text-xs text-slate-600 hover:text-red-400 transition-colors ml-2"
            title="Remove API key"
          >
            Remove key
          </button>
        )}
      </div>

      {messages.length > 0 && (
        <div className="px-5 py-4 space-y-4 max-h-96 overflow-y-auto">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user" ? "bg-accent text-white" : "bg-surface-700 text-slate-200"
                }`}
              >
                {msg.text}
                {streaming && i === messages.length - 1 && msg.role === "assistant" && msg.text === "" && (
                  <span className="inline-block w-1.5 h-3.5 bg-violet-400 animate-pulse rounded-sm" />
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {messages.length === 0 && (
        <div className="px-5 py-3 flex flex-wrap gap-2">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => handleAsk(s)}
              className="text-xs px-3 py-1.5 rounded-full bg-surface-700 border border-surface-500 text-slate-400 hover:text-white hover:border-violet-500/50 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="px-4 py-3 border-t border-surface-600 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk(input)}
          placeholder="Ask anything about your traffic…"
          disabled={streaming}
          className="flex-1 bg-surface-700 border border-surface-500 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/60 disabled:opacity-50"
        />
        <button
          onClick={() => handleAsk(input)}
          disabled={streaming || !input.trim()}
          className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 text-white text-sm rounded-lg transition-colors"
        >
          {streaming ? "…" : "Ask"}
        </button>
      </div>
    </div>
  );
}

export default function Intelligence() {
  const { role } = useAuthStore();
  const isAdmin = role === "admin";
  const [searchParams] = useSearchParams();
  const openLive = searchParams.get("openLive") === "1";
  const [insights, setInsights] = useState([]);
  const [enrichMeta, setEnrichMeta] = useState(null);
  const [enrichLoading, setEnrichLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [days, setDays] = useState(7);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    setSummaryLoading(true);
    setEnrichMeta(null);

    api.get(`/intelligence/insights?days=${days}`)
      .then(({ data }) => {
        setInsights(data);
        setLoading(false);
        if (data.length > 0) {
          setEnrichLoading(true);
          api
            .post("/intelligence/enrich", { insights: data, days })
            .then(({ data: ed }) => {
              setInsights(ed.enriched);
              if (!ed.skipped) setEnrichMeta(ed);
            })
            .catch(() => {})
            .finally(() => setEnrichLoading(false));
        }
      })
      .catch(() => {
        setInsights([]);
        setLoading(false);
      });

    api.get(`/intelligence/summary?days=${days}`)
      .then(({ data }) => setSummary(data))
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false));
  }, [days, currentSiteId]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Intelligence</h1>
          <p className="text-xs text-slate-500 mt-0.5">Patterns your data is trying to tell you</p>
        </div>
        <div className="flex gap-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                days === d
                  ? "bg-accent text-white"
                  : "bg-surface-700 text-slate-400 hover:text-white border border-surface-500"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <SummaryCard summary={summary} loading={summaryLoading} />

      <AskChat days={days} currentSiteId={currentSiteId} />

      {isAdmin && <LiveSettingsPanel forceOpen={openLive} />}

      {isAdmin && <ReadingProviderPanel />}

      {isAdmin && <AISettingsPanel />}

      <InsightsFeed insights={insights} loading={loading} enrichMeta={enrichMeta} enrichLoading={enrichLoading} />

      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
        <p className="text-sm font-medium text-slate-300 mb-3">Raw Signals</p>
        {loading ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : insights.length === 0 ? (
          <p className="text-xs text-slate-500">No signals detected in this period.</p>
        ) : (
          <div className="space-y-2">
            {insights.map((ins, i) => (
              <div key={i} className="grid grid-cols-3 gap-4 text-xs py-2 border-b border-surface-600 last:border-0">
                <span className="text-slate-500 font-mono">{ins.type}</span>
                <span className="text-slate-400 col-span-2">{JSON.stringify(ins.data)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
