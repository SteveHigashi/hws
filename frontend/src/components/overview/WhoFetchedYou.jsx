import { Link } from "react-router-dom";
import StatTooltip from "../charts/StatTooltip";

// Second on the first screen, gate 6(c): who fetched you, and what they took.
//
// The reference sweep found no mainstream analytics dashboard leads with this. They show
// "bots: 12%" and stop. The owner's actual question is which ones, whether they were who
// they said they were, and how much of the site they walked off with. That is three
// columns, not a percentage.
//
// Nothing here is a recommendation. Counting what arrived is all Higashi does.

function Verification({ v }) {
  const forged = v?.forged || 0;
  const verified = v?.verified || 0;
  const unverified = v?.unverified || 0;

  if (forged > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-rose-300">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
        Forged{forged > 1 ? ` ×${forged.toLocaleString()}` : ""}
      </span>
    );
  }
  if (verified > 0 && unverified === 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-300">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        Verified
      </span>
    );
  }
  if (verified > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sky-300">
        <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
        Partly verified
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-slate-400">
      <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />
      Unverified
    </span>
  );
}

const CATEGORY_TONE = {
  ai_crawler: "text-violet-300 bg-violet-500/10 border-violet-500/30",
  seo_crawler: "text-sky-300 bg-sky-500/10 border-sky-500/30",
  search_crawler: "text-sky-300 bg-sky-500/10 border-sky-500/30",
  generic_bot: "text-slate-400 bg-surface-700 border-surface-500",
};

function sinceText(iso) {
  if (!iso) return "—";
  const secs = Math.max(0, (Date.now() - new Date(iso + "Z").getTime()) / 1000);
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

export default function WhoFetchedYou({ rows, loading, limit = 6 }) {
  const all = Array.isArray(rows) ? rows : [];
  const top = all.slice(0, limit);
  const busiest = top[0]?.total || 1;

  return (
    <section className="rounded-xl border border-surface-600 bg-surface-800 overflow-hidden">
      <div className="flex items-baseline justify-between gap-3 px-5 pt-4 pb-3">
        <div>
          <h2 className="text-sm font-medium text-slate-200">Who fetched your site</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Ranked by requests. "Pages taken" is how many different pages each one pulled.
          </p>
        </div>
        {all.length > limit && (
          <Link to="/dashboard/ai-crawlers" className="text-xs text-accent hover:underline shrink-0">
            All {all.length}
          </Link>
        )}
      </div>

      {loading ? (
        <p className="px-5 pb-5 text-xs text-slate-500">Counting what arrived…</p>
      ) : top.length === 0 ? (
        <p className="px-5 pb-5 text-xs text-slate-500">
          Nothing automated reached your site in this period.
        </p>
      ) : (
        <div className="divide-y divide-surface-700/70">
          <div className="px-5 pb-2 hidden sm:flex items-center justify-end gap-5 text-[10px] uppercase tracking-wider text-slate-500 border-b border-surface-600">
            <span className="mr-auto">Crawler</span>
            <span className="w-28 text-left">Claimed identity</span>
            <span className="w-20 text-right">Requests</span>
            <span className="w-20 text-right">Pages taken</span>
            <span className="w-16 text-right hidden sm:inline">Last seen</span>
          </div>
          {top.map((r) => (
            <div key={`${r.name}-${r.category}`} className="px-5 py-3">
              {/* Stacks below sm: at 375px the fixed columns collided and "pages taken"
                  fell off the right edge, so the phone gets labelled rows instead. */}
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                <div className="min-w-0 flex items-center gap-2.5">
                  <span className="text-sm text-slate-100 font-medium truncate">{r.name}</span>
                  <span
                    className={`shrink-0 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border ${
                      CATEGORY_TONE[r.category] || CATEGORY_TONE.generic_bot
                    }`}
                  >
                    {r.category_label}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4 sm:justify-end sm:gap-5 sm:shrink-0">
                  <span className="text-xs sm:w-28 sm:text-left order-1">
                    <Verification v={r.verification} />
                  </span>
                  <span className="text-sm text-slate-200 tabular-nums sm:w-20 sm:text-right order-2">
                    <StatTooltip id="crawler_requests" value={r.total} showIcon={false}>
                      {r.total.toLocaleString()}
                      <span className="sm:hidden text-[10px] text-slate-500 ml-1">reqs</span>
                    </StatTooltip>
                  </span>
                  <span className="text-sm text-violet-300 tabular-nums sm:w-20 sm:text-right order-3">
                    <StatTooltip id="crawler_pages_taken" value={r.unique_pages} showIcon={false}>
                      {r.unique_pages.toLocaleString()}
                      <span className="sm:hidden text-[10px] text-violet-400/70 ml-1">pages</span>
                    </StatTooltip>
                  </span>
                  <span className="text-xs text-slate-500 tabular-nums sm:w-16 sm:text-right order-4">
                    {sinceText(r.last_seen)}
                  </span>
                </div>
              </div>
              <div className="mt-2 h-1 w-full rounded-full bg-surface-700 overflow-hidden">
                <div
                  className={r.category === "ai_crawler" ? "h-full bg-violet-400/80" : "h-full bg-sky-400/50"}
                  style={{ width: `${Math.max(2, (r.total / busiest) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
