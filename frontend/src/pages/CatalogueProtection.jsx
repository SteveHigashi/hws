import { useEffect, useState } from "react";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";
import LiveHeadline from "../components/live/LiveHeadline";

const DAYS = [7, 30, 90];

function pct(value) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

function EvidenceCard({ label, value, note, warning }) {
  return (
    <div className={`bg-surface-800 border rounded-xl p-5 ${warning ? "border-amber-500/40" : "border-surface-600"}`}>
      <p className="text-xs text-slate-500 uppercase tracking-widest">{label}</p>
      <p className={`text-2xl font-mono mt-2 ${warning ? "text-amber-300" : "text-white"}`}>{value}</p>
      <p className="text-xs text-slate-500 mt-2 leading-relaxed">{note}</p>
    </div>
  );
}

function verdictStyle(verdict) {
  if (verdict === "walk_detected") return "border-red-500/50 bg-red-500/10 text-red-200";
  if (verdict === "suspicious") return "border-amber-500/50 bg-amber-500/10 text-amber-200";
  if (verdict === "no_walk_detected") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  return "border-surface-500 bg-surface-800 text-slate-300";
}

function ClaimBadge({ state }) {
  const styles = {
    forged: "text-red-300 bg-red-500/10 border-red-500/40",
    verified: "text-emerald-300 bg-emerald-500/10 border-emerald-500/40",
    unverified: "text-amber-300 bg-amber-500/10 border-amber-500/40",
  };
  return <span className={`text-xs px-2 py-0.5 rounded border ${styles[state] || styles.unverified}`}>{state}</span>;
}

export default function CatalogueProtection() {
  const [days, setDays] = useState(30);
  const [overview, setOverview] = useState(null);
  const [runs, setRuns] = useState([]);
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(false);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    if (!currentSiteId) {
      setOverview(null);
      setRuns([]);
      setClaims([]);
      return;
    }
    setLoading(true);
    const site = encodeURIComponent(currentSiteId);
    Promise.all([
      api.get(`/walk-detection/overview?site_id=${site}&days=${days}`),
      api.get(`/walk-detection/runs?site_id=${site}&days=${days}&limit=25`),
      api.get(`/walk-detection/crawler-claims?site_id=${site}&days=${days}`),
    ])
      .then(([summary, windows, crawlerClaims]) => {
        setOverview(summary.data);
        setRuns(windows.data);
        setClaims(crawlerClaims.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [currentSiteId, days]);

  if (!currentSiteId) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-6 text-center max-w-lg">
          <p className="text-white font-medium">Choose one site to inspect</p>
          <p className="text-xs text-slate-500 mt-2">Catalogue detections are deliberately site-scoped and are never combined across customers or domains.</p>
        </div>
      </div>
    );
  }

  const evidence = overview?.evidence || {};
  const forged = claims.filter((claim) => claim.verification_state === "forged");

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Catalogue Protection</h1>
          <p className="text-xs text-slate-500 mt-0.5">After-the-fact detection from access logs — visibility, never enforcement</p>
        </div>
        <div className="flex gap-2">
          {DAYS.map((value) => (
            <button key={value} onClick={() => setDays(value)} className={`text-xs px-3 py-1.5 rounded-lg ${days === value ? "bg-accent text-white" : "bg-surface-700 border border-surface-500 text-slate-400"}`}>
              {value}d
            </button>
          ))}
        </div>
      </div>

      <LiveHeadline />

      <div className={`border rounded-xl p-6 ${verdictStyle(overview?.verdict)}`}>
        <p className="text-xs uppercase tracking-widest opacity-70">Plain-language verdict</p>
        <p className="text-2xl font-semibold mt-2">{loading ? "Analyzing…" : overview?.headline || "No analysis available."}</p>
        <p className="text-xs mt-3 opacity-70">
          {overview?.windows_analyzed?.toLocaleString() || 0} half-hour windows analyzed · evidence score {overview?.score || 0}/100
        </p>
      </div>

      {forged.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-5">
          <p className="text-sm font-semibold text-red-300">Forged crawler identity — highest-confidence warning</p>
          <p className="text-xs text-red-200/70 mt-1">These requests used a crawler name from an address outside that operator's published network.</p>
          <div className="mt-3 space-y-2">
            {forged.map((claim) => (
              <div key={`${claim.bot_name}-${claim.verification_state}`} className="flex justify-between text-xs">
                <span className="text-red-200 font-mono">{claim.bot_name}</span>
                <span className="text-red-300">{claim.requests.toLocaleString()} requests · {claim.addresses.toLocaleString()} salted identities</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
        <EvidenceCard label="Records Taken" value={(overview?.records_taken || 0).toLocaleString()} note="Counted only when response bytes match the rolling path-family baseline. A status 200 alone does not count." />
        <EvidenceCard label="One-shot Pool" value={(evidence.max_oneshot_identities || 0).toLocaleString()} note={`${pct(evidence.max_shape_share)} of full catalogue responses at the strongest window came from one-request identities.`} warning={(evidence.max_shape_share || 0) >= 0.7} />
        <EvidenceCard label="Ordered Steps" value={pct(evidence.max_order_ratio)} note="Adjacent record slugs moving consistently in one lexical direction; independent of the rotating-pool test." warning={(evidence.max_order_ratio || 0) >= 0.85} />
        <EvidenceCard label="Asset-less Share" value={pct(evidence.max_assetless_share)} note="Catalogue identities that fetched no same-origin JS, CSS, font, or image asset." warning={(evidence.max_assetless_share || 0) >= 0.8} />
        <EvidenceCard label="Missing Referers" value={pct(evidence.max_referer_absence)} note="Full catalogue responses requested without navigation or discovery context. This is supporting evidence only." warning={(evidence.max_referer_absence || 0) >= 0.8} />
        <EvidenceCard label="Queue Correlation" value={pct(evidence.max_shared_queue_ratio)} note="Consecutive records sent to different identities that still shared a first letter." warning={(evidence.max_shared_queue_ratio || 0) >= 0.6} />
      </div>

      {evidence.max_engagement_absence != null && (
        <p className="text-xs text-slate-500 bg-surface-800 border border-surface-600 rounded-xl p-4">
          Engagement corroboration: as many as {pct(evidence.max_engagement_absence)} of sessions in an analyzed window had no behavior event. This never triggers a finding by itself.
        </p>
      )}

      {overview?.rate_warning && (
        <div className="bg-amber-500/10 border border-amber-500/40 rounded-xl p-4 text-xs text-amber-200 leading-relaxed">
          <span className="font-medium">Per-address rate blind spot:</span> {overview.rate_warning}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300">Who claimed to be a crawler</p>
          <p className="text-xs text-slate-500 mt-1 mb-4">Verified means the address matched a published prefix or forward-confirmed reverse DNS.</p>
          {claims.length === 0 ? <p className="text-xs text-slate-500">No crawler claims in this period.</p> : claims.map((claim) => (
            <div key={`${claim.bot_name}-${claim.verification_state}`} className="grid grid-cols-4 items-center py-2.5 border-b border-surface-700 last:border-0 text-xs">
              <span className="text-slate-200 font-mono">{claim.bot_name}</span>
              <ClaimBadge state={claim.verification_state} />
              <span className="text-right text-slate-400">{claim.requests.toLocaleString()} requests</span>
              <span className="text-right text-slate-500">{claim.addresses.toLocaleString()} identities</span>
            </div>
          ))}
        </div>

        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300">Strongest recent windows</p>
          <p className="text-xs text-slate-500 mt-1 mb-4">SHAPE and ORDER are independent; either can detect a walk on its own.</p>
          {runs.length === 0 ? <p className="text-xs text-slate-500">No imported log windows yet.</p> : runs.slice().sort((a, b) => b.score - a.score).slice(0, 8).map((run) => (
            <div key={run.id} className="flex items-start justify-between gap-4 py-2.5 border-b border-surface-700 last:border-0">
              <div>
                <p className="text-xs text-slate-300">{new Date(run.window_start).toLocaleString()}</p>
                <p className="text-xs text-slate-600 mt-0.5">{run.triggers.length ? run.triggers.join(" + ").toUpperCase() : "No primary trigger"} · {run.records_taken} records</p>
              </div>
              <span className={`font-mono text-sm ${run.score >= 50 ? "text-amber-300" : "text-slate-400"}`}>{run.score}/100</span>
            </div>
          ))}
        </div>
      </div>

      <details className="bg-surface-800 border border-surface-600 rounded-xl p-4 text-xs text-slate-500">
        <summary className="cursor-pointer text-slate-400">What this cannot prove</summary>
        <p className="mt-3 leading-relaxed">A careful extractor can fetch assets, send plausible referers, shuffle requests, and simulate behavior. Low traffic may not give the detector enough examples. Engagement absence only corroborates other evidence; it never triggers a finding by itself. This page reports what the imported log supports and does not block or modify any request.</p>
      </details>
    </div>
  );
}
