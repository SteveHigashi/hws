import { useEffect, useState } from "react";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";
import LiveHeadline from "../components/live/LiveHeadline";

const DAYS_OPTIONS = [7, 30, 90];

const CATEGORY_COLORS = {
  ai_crawler:     "text-violet-400 bg-violet-400/10 border-violet-500/30",
  seo_crawler:    "text-blue-400 bg-blue-400/10 border-blue-500/30",
  seo_audit:      "text-sky-400 bg-sky-400/10 border-sky-500/30",
  social_crawler: "text-pink-400 bg-pink-400/10 border-pink-500/30",
  generic_bot:    "text-slate-400 bg-slate-400/10 border-slate-500/30",
  // Amber, not the neutral crawler palette: these actively misrepresented
  // themselves as human, so they should read as a warning rather than as
  // another routine crawler.
  deceptive:      "text-amber-400 bg-amber-400/10 border-amber-500/40",
};

function shadowReachTier(score) {
  if (score == null) return null;
  if (score < 5)   return { label: "Minimal — barely indexed",        color: "text-slate-500" };
  if (score < 30)  return { label: "Light — personal / niche site",   color: "text-blue-400" };
  if (score < 100) return { label: "Moderate — regular crawling",     color: "text-teal-400" };
  if (score < 500) return { label: "Strong — heavy AI attention",     color: "text-violet-400" };
  return                   { label: "Exceptional — multi-crawler",    color: "text-amber-400" };
}

function MetricCard({ label, value, sub, accent, tier }) {
  return (
    <div className={`bg-surface-800 border rounded-xl p-5 ${accent ? "border-violet-500/40" : "border-surface-600"}`}>
      <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">{label}</p>
      <p className={`text-2xl font-mono font-semibold ${accent ? "text-violet-400" : "text-white"}`}>
        {value ?? "—"}
      </p>
      {tier && <p className={`text-xs font-medium mt-1 ${tier.color}`}>{tier.label}</p>}
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function CategoryBadge({ category, label }) {
  const cls = CATEGORY_COLORS[category] ?? CATEGORY_COLORS.generic_bot;
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-mono ${cls}`}>
      {label ?? category}
    </span>
  );
}

function VerificationBadge({ counts }) {
  if (counts?.forged > 0) {
    return <span className="text-xs font-medium text-red-300">forged · {counts.forged}</span>;
  }
  if (counts?.verified > 0 && !counts?.unverified) {
    return <span className="text-xs font-medium text-emerald-400">verified</span>;
  }
  return <span className="text-xs text-amber-400">unverified</span>;
}

function MagnetismBar({ score }) {
  const color =
    score >= 70 ? "bg-violet-500" :
    score >= 40 ? "bg-blue-500" :
    "bg-slate-600";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-surface-700 rounded-full h-1.5 max-w-[80px]">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>

      {(overview?.crawler_verification?.forged ?? 0) > 0 && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-5">
          <p className="text-sm font-semibold text-red-300">Crawler identity forgery detected</p>
          <p className="text-xs text-red-200/70 mt-1 leading-relaxed">
            {overview.crawler_verification.forged.toLocaleString()} request{overview.crawler_verification.forged === 1 ? "" : "s"} claimed
            a published crawler identity from outside that operator's network. Treat these as impersonation, not crawler traffic.
          </p>
        </div>
      )}
      <span className="text-xs text-slate-400 font-mono w-8 text-right">{score}</span>
    </div>
  );
}

export default function AICrawlers() {
  const [days, setDays] = useState(30);
  const [overview, setOverview] = useState(null);
  const [crawlers, setCrawlers] = useState([]);
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/ai-crawlers/overview?days=${days}`),
      api.get(`/ai-crawlers/crawlers?days=${days}`),
      api.get(`/ai-crawlers/pages?days=${days}&category=ai_crawler&verification=verified`),
    ])
      .then(([ov, cr, pg]) => {
        setOverview(ov.data);
        setCrawlers(cr.data);
        setPages(pg.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days, currentSiteId]);

  const aiCrawlers    = crawlers.filter((c) => c.category === "ai_crawler");
  const otherCrawlers = crawlers.filter((c) => c.category !== "ai_crawler");

  // Pixel snippet for site owners
  const trackerKey = "[YOUR-TRACKER-KEY]";
  const pixelSnippet = `<!-- Higashi AI Crawler Tracking Pixel -->
<img src="/collect/pixel?k=${trackerKey}&p=" id="hpx"
     width="1" height="1" style="position:absolute;opacity:0" alt="">
<script>document.getElementById('hpx').src += location.pathname;</script>`;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <LiveHeadline />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">AI Crawlers</h1>
          <p className="text-xs text-slate-500 mt-0.5">Who's reading your site — and how much</p>
        </div>
        <div className="flex gap-2">
          {DAYS_OPTIONS.map((d) => (
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

      {/* Metric cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          label="AI Visibility Index"
          value={overview?.ai_visibility_index != null ? `${overview.ai_visibility_index} / 100` : null}
          sub="weighted AI indexing depth"
          accent
        />
        <MetricCard
          label="Shadow Reach Index"
          value={overview?.shadow_reach_index?.toLocaleString()}
          sub="relative AI-mediated exposure"
          tier={shadowReachTier(overview?.shadow_reach_index)}
        />
        <MetricCard
          label="Verified AI Visits"
          value={overview?.total_ai_visits?.toLocaleString()}
          sub={`${overview?.total_ai_claims?.toLocaleString() ?? "—"} AI identity claims in total`}
        />
        <MetricCard
          label="AI-to-Human Ratio"
          value={overview?.ai_human_ratio != null ? `${overview.ai_human_ratio}%` : null}
          sub="of all traffic is verified AI crawling"
        />
      </div>

      {/* Explainer row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 text-xs text-slate-500">
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-4 space-y-2">
          <p className="text-slate-300 font-medium">AI Visibility Index</p>
          <p>0–100 score. Weighted by crawler importance (GPTBot = 1.5×, ClaudeBot = 1.3×) × unique pages indexed × log of crawl depth.</p>
          <div className="border-t border-surface-600 pt-2 space-y-1">
            <div className="flex justify-between"><span>0–20</span><span className="text-slate-400">Minimal — few pages indexed</span></div>
            <div className="flex justify-between"><span>20–50</span><span className="text-slate-400">Growing — AI systems are finding you</span></div>
            <div className="flex justify-between"><span>50–75</span><span className="text-teal-500">Active — content well-indexed</span></div>
            <div className="flex justify-between"><span>75+</span><span className="text-violet-400">Excellent — deep, broad indexing</span></div>
          </div>
        </div>
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-4 space-y-2">
          <p className="text-slate-300 font-medium">Shadow Reach Index</p>
          <p>Relative exposure estimate. Each crawler has a reach multiplier (GPTBot = 200×, Google-Extended = 150×, ClaudeBot = 50×) based on platform size. Not a literal user count — use it to track growth and compare pages.</p>
          <div className="border-t border-surface-600 pt-2 space-y-1">
            <div className="flex justify-between"><span>0–5</span><span className="text-slate-400">Minimal AI attention</span></div>
            <div className="flex justify-between"><span>5–30</span><span className="text-blue-400">Light — personal or niche site</span></div>
            <div className="flex justify-between"><span>30–100</span><span className="text-teal-400">Moderate — regular crawling</span></div>
            <div className="flex justify-between"><span>100–500</span><span className="text-violet-400">Strong — heavy AI attention</span></div>
            <div className="flex justify-between"><span>500+</span><span className="text-amber-400">Exceptional</span></div>
          </div>
        </div>
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-4 space-y-2">
          <p className="text-slate-300 font-medium">Content Magnetism Score</p>
          <p>Crawls per day per page, normalized 0–100. High scores mean AI systems keep returning — a signal that the content is considered valuable or frequently changing.</p>
          <div className="border-t border-surface-600 pt-2 space-y-1">
            <div className="flex justify-between"><span>0–40</span><span className="text-slate-400">Low — infrequent revisits</span></div>
            <div className="flex justify-between"><span>40–70</span><span className="text-blue-400">Good — content getting traction</span></div>
            <div className="flex justify-between"><span>70+</span><span className="text-violet-400">High signal — AI keeps returning</span></div>
          </div>
        </div>
      </div>

      {/* Main data grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* AI Crawlers table */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">AI Crawlers</p>
          {loading ? (
            <p className="text-xs text-slate-500">Loading…</p>
          ) : aiCrawlers.length === 0 ? (
            <p className="text-xs text-slate-500">No AI crawler visits yet. Add the tracking pixel below.</p>
          ) : (
            <div className="space-y-0">
              <div className="grid grid-cols-5 text-xs text-slate-600 uppercase tracking-widest pb-2 border-b border-surface-600">
                <span className="col-span-2">Crawler</span>
                <span>Identity</span>
                <span className="text-right">Visits</span>
                <span className="text-right">Pages</span>
              </div>
              {aiCrawlers.map((c) => (
                <div key={c.name} className="grid grid-cols-5 text-sm py-2.5 border-b border-surface-700 last:border-0 items-center">
                  <div className="col-span-2">
                    <p className="text-slate-200 font-mono text-xs">{c.name}</p>
                    {c.last_seen && (
                      <p className="text-slate-600 text-xs mt-0.5">
                        last seen {new Date(c.last_seen).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <VerificationBadge counts={c.verification} />
                  <span className="text-right text-slate-400 font-mono text-xs">{c.total.toLocaleString()}</span>
                  <span className="text-right text-slate-400 font-mono text-xs">{c.unique_pages}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top crawled pages */}
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-1">Top Verified Crawled Pages</p>
          <p className="text-xs text-slate-500 mb-4">Forged and unverified identity claims are excluded.</p>
          {loading ? (
            <p className="text-xs text-slate-500">Loading…</p>
          ) : pages.length === 0 ? (
            <p className="text-xs text-slate-500">No page data yet.</p>
          ) : (
            <div className="space-y-0">
              <div className="grid grid-cols-5 text-xs text-slate-600 uppercase tracking-widest pb-2 border-b border-surface-600">
                <span className="col-span-2">Page</span>
                <span className="text-right">Crawls</span>
                <span className="text-right">Bots</span>
                <span className="text-right">Magnetism</span>
              </div>
              {pages.map((p, i) => (
                <div key={i} className="grid grid-cols-5 text-sm py-2.5 border-b border-surface-700 last:border-0 items-center">
                  <span className="col-span-2 text-slate-300 font-mono text-xs truncate pr-2" title={p.page_path}>
                    {p.page_path || "/"}
                  </span>
                  <span className="text-right text-slate-400 font-mono text-xs">{p.total_crawls.toLocaleString()}</span>
                  <span className="text-right text-slate-400 font-mono text-xs">{p.unique_bots}</span>
                  <div className="flex justify-end">
                    <MagnetismBar score={p.magnetism_score} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Other crawler types */}
      {otherCrawlers.length > 0 && (
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5">
          <p className="text-sm font-medium text-slate-300 mb-4">Other Crawlers</p>
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
            {otherCrawlers.map((c) => (
              <div key={c.name} className="bg-surface-700 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-300 font-mono">{c.name}</span>
                  <CategoryBadge category={c.category} label={c.category_label} />
                </div>
                <p className="text-lg font-mono text-white">{c.total.toLocaleString()}</p>
                <p className="text-xs text-slate-500">{c.unique_pages} pages</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Setup: pixel snippet */}
      <div className="bg-surface-800 border border-amber-500/30 rounded-xl p-5">
        <p className="text-sm font-medium text-amber-400 mb-1">Setup: Tracking Pixel</p>
        <p className="text-xs text-slate-400 mb-4">
          AI crawlers don't execute JavaScript, so they never hit the standard tracker.
          Add this one-line pixel to your HTML <code className="text-slate-300">&lt;body&gt;</code> to
          capture them. Replace <code className="text-slate-300">[YOUR-TRACKER-KEY]</code> with the key
          from your admin settings.
        </p>
        <pre className="bg-surface-900 border border-surface-600 rounded-lg p-4 text-xs text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap">
          {pixelSnippet}
        </pre>
        <p className="text-xs text-slate-600 mt-3">
          The inline script appends the current page path dynamically so one snippet works across all pages.
        </p>
      </div>
    </div>
  );
}
