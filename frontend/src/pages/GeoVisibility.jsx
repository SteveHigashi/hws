import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";
import { useAuthStore } from "../hooks/useAuth";

function MentionDot({ mentioned }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${mentioned ? "bg-green-400" : "bg-slate-600"}`} />
  );
}

function ProbeCard({ probe, onDelete, onRunOne, running }) {
  const [results, setResults] = useState([]);
  const [expanded, setExpanded] = useState(false);
  const { role } = useAuthStore();

  useEffect(() => {
    api.get(`/geo-probes/results?probe_id=${probe.id}&days=90`)
      .then(({ data }) => setResults(data))
      .catch(() => {});
  }, [probe.id, probe.last_run_at]);

  const chartData = results.map((r) => ({
    date: r.ran_at.slice(0, 10),
    mentioned: r.mentioned ? 1 : 0,
  }));

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl overflow-hidden">
      <div className="px-5 py-4 flex items-start gap-3">
        <MentionDot mentioned={probe.latest_mentioned} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 leading-snug">{probe.query_text}</p>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-xs text-slate-500">brand: <span className="text-slate-400 font-mono">{probe.brand_name}</span></span>
            {probe.mention_rate !== null && (
              <span className={`text-xs font-medium ${probe.mention_rate > 50 ? "text-green-400" : probe.mention_rate > 20 ? "text-warn" : "text-slate-500"}`}>
                {probe.mention_rate}% mention rate
              </span>
            )}
            {probe.last_run_at && (
              <span className="text-xs text-slate-600">
                last run {new Date(probe.last_run_at).toLocaleDateString()}
              </span>
            )}
            {!probe.last_run_at && (
              <span className="text-xs text-slate-600 italic">never run</span>
            )}
          </div>
          {probe.latest_mentioned && probe.latest_excerpt && (
            <p className="text-xs text-green-400/80 mt-1.5 leading-relaxed italic">"{probe.latest_excerpt}"</p>
          )}
          {probe.latest_mentioned === false && probe.result_count > 0 && (
            <p className="text-xs text-slate-600 mt-1 italic">Not mentioned in latest probe</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            {expanded ? "Hide" : "History"}
          </button>
          <button
            onClick={() => onRunOne(probe.id)}
            disabled={running}
            className="text-xs px-2.5 py-1 bg-accent/15 hover:bg-accent/30 disabled:opacity-40 text-accent rounded-lg transition-colors"
          >
            {running ? "Running…" : "Run"}
          </button>
          {role === "admin" && (
            <button
              onClick={() => onDelete(probe.id)}
              className="text-xs text-slate-600 hover:text-red-400 transition-colors"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {expanded && results.length > 0 && (
        <div className="border-t border-surface-600 px-5 py-4 space-y-3">
          <p className="text-xs text-slate-500 uppercase tracking-wider">Mention history</p>
          <ResponsiveContainer width="100%" height={60}>
            <LineChart data={chartData}>
              <XAxis dataKey="date" hide />
              <YAxis domain={[0, 1]} hide />
              <Tooltip
                formatter={(v) => [v === 1 ? "Mentioned ✓" : "Not mentioned", ""]}
                labelFormatter={(l) => l}
                contentStyle={{ background: "#1e2536", border: "1px solid #2d3748", borderRadius: 8, fontSize: 11 }}
              />
              <ReferenceLine y={0.5} stroke="#2d3748" strokeDasharray="3 3" />
              <Line
                type="stepAfter"
                dataKey="mentioned"
                stroke="#22d3ee"
                strokeWidth={2}
                dot={{ fill: "#22d3ee", r: 4 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {[...results].reverse().map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-slate-400">
                <MentionDot mentioned={r.mentioned} />
                <span className="text-slate-500 w-24 shrink-0">{r.ran_at.slice(0, 10)}</span>
                <span className={r.mentioned ? "text-green-400" : "text-slate-600"}>
                  {r.mentioned ? "Mentioned" : "Not mentioned"}
                </span>
                {r.mention_excerpt && (
                  <span className="text-slate-500 truncate italic">— "{r.mention_excerpt.slice(0, 80)}…"</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AddProbeForm({ siteId, onAdded }) {
  const [query, setQuery] = useState("");
  const [brand, setBrand] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const handleAdd = async () => {
    if (!query.trim() || !brand.trim()) return;
    setSaving(true); setErr("");
    try {
      await api.post("/geo-probes/queries", { query_text: query.trim(), brand_name: brand.trim(), site_id: siteId });
      setQuery(""); setBrand("");
      onAdded();
    } catch (e) {
      setErr(e.response?.data?.detail || "Error saving probe");
    } finally { setSaving(false); }
  };

  return (
    <div className="bg-surface-800 border border-surface-500 border-dashed rounded-xl p-5 space-y-3">
      <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Add probe query</p>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder='e.g. "best self-hosted analytics for privacy"'
        className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-accent/60"
      />
      <div className="flex gap-2">
        <input
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder='Brand name to detect, e.g. "Higashi"'
          className="flex-1 bg-surface-700 border border-surface-500 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-accent/60"
        />
        <button
          onClick={handleAdd}
          disabled={saving || !query.trim() || !brand.trim()}
          className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-40 text-white text-sm rounded-lg transition-colors"
        >
          {saving ? "Adding…" : "Add"}
        </button>
      </div>
      {err && <p className="text-xs text-red-400">{err}</p>}
      <p className="text-xs text-slate-600">Max 5 active probes per site. The AI is asked this question and the response is checked for your brand name.</p>
    </div>
  );
}

export default function GeoVisibility() {
  const { currentSiteId } = useSiteStore();
  const [probes, setProbes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runningId, setRunningId] = useState(null);

  const fetchProbes = () => {
    setLoading(true);
    api.get("/geo-probes/queries")
      .then(({ data }) => setProbes(data))
      .catch(() => setProbes([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchProbes(); }, [currentSiteId]);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this probe and all its history?")) return;
    await api.delete(`/geo-probes/queries/${id}`);
    fetchProbes();
  };

  const handleRunAll = async () => {
    setRunning(true); setRunResult(null);
    try {
      const { data } = await api.post("/geo-probes/run", {});
      setRunResult(data);
      fetchProbes();
    } catch (e) {
      setRunResult({ error: e.response?.data?.detail || "Error running probes" });
    } finally { setRunning(false); }
  };

  const handleRunOne = async (probeId) => {
    setRunningId(probeId);
    try {
      await api.post("/geo-probes/run", { probe_id: probeId });
      fetchProbes();
    } catch { } finally { setRunningId(null); }
  };

  const mentionedCount = probes.filter((p) => p.latest_mentioned === true).length;
  const totalRun = probes.filter((p) => p.result_count > 0).length;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white">GEO Visibility</h1>
          <p className="text-xs text-slate-500 mt-0.5">Does AI recommend you? Track your brand in AI-generated answers.</p>
        </div>
        {probes.length > 0 && (
          <button
            onClick={handleRunAll}
            disabled={running}
            className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
          >
            {running ? "Running all probes…" : "Run all probes now"}
          </button>
        )}
      </div>

      {/* Summary strip */}
      {totalRun > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-surface-800 border border-surface-600 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-white">{probes.length}</p>
            <p className="text-xs text-slate-500 mt-1">Active probes</p>
          </div>
          <div className="bg-surface-800 border border-surface-600 rounded-xl p-4 text-center">
            <p className={`text-2xl font-bold ${mentionedCount > 0 ? "text-green-400" : "text-slate-500"}`}>{mentionedCount}/{totalRun}</p>
            <p className="text-xs text-slate-500 mt-1">Probes with recent mention</p>
          </div>
          <div className="bg-surface-800 border border-surface-600 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-accent">
              {probes.filter(p => p.mention_rate !== null).length > 0
                ? Math.round(probes.filter(p => p.mention_rate !== null).reduce((a, p) => a + p.mention_rate, 0) / probes.filter(p => p.mention_rate !== null).length)
                : "—"}%
            </p>
            <p className="text-xs text-slate-500 mt-1">Avg mention rate</p>
          </div>
        </div>
      )}

      {/* Context note */}
      <div className="bg-surface-800 border border-violet-500/20 rounded-xl px-5 py-4">
        <p className="text-xs text-slate-400 leading-relaxed">
          <span className="text-violet-400 font-medium">How this works: </span>
          Each probe asks the configured AI model your question and checks whether your brand name appears in the response.
          A mention means the AI recommended you — not just indexed you. Check the <span className="text-accent">AI Crawlers</span> page
          to correlate: high crawl activity + low mention rate means models ingest your content but don't recommend it yet.
        </p>
      </div>

      {/* Run result flash */}
      {runResult && !runResult.error && (
        <div className="bg-surface-800 border border-green-500/20 rounded-xl px-5 py-3">
          <p className="text-xs text-slate-400">
            Ran {runResult.ran?.length} probe{runResult.ran?.length !== 1 ? "s" : ""} with <span className="font-mono text-slate-300">{runResult.model_used}</span>.{" "}
            {runResult.ran?.filter(r => r.mentioned).length} mentioned your brand.
          </p>
        </div>
      )}
      {runResult?.error && (
        <div className="bg-surface-800 border border-red-500/20 rounded-xl px-5 py-3">
          <p className="text-xs text-red-400">{runResult.error}</p>
        </div>
      )}

      {/* Probe list */}
      {loading ? (
        <p className="text-xs text-slate-500">Loading probes…</p>
      ) : (
        <div className="space-y-3">
          {probes.map((probe) => (
            <ProbeCard
              key={probe.id}
              probe={probe}
              onDelete={handleDelete}
              onRunOne={handleRunOne}
              running={runningId === probe.id}
            />
          ))}
          {probes.length < 5 && (
            <AddProbeForm siteId={currentSiteId} onAdded={fetchProbes} />
          )}
          {probes.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-4">No probes yet. Add one below to start tracking your GEO visibility.</p>
          )}
        </div>
      )}
    </div>
  );
}
