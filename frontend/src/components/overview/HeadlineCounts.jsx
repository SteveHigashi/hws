import StatTooltip from "../charts/StatTooltip";

// The first screen, gate 6(c).
//
// The reference sweep (docs/DASHBOARD_REFERENCE_SWEEP_2026-09-20.md) found that none of
// Plausible, Fathom, Umami, Cloudflare or Matomo puts human and automated traffic side by
// side as two equal headline numbers. They lead with visitors and mention bots somewhere
// below, if at all. That absence is the whole reason this product exists, so it is the
// first thing on the page: how many people, how many machines, and how much of it looked
// wrong — at the same size, in one glance.
//
// The split bar underneath is the point of the row. Two numbers invite arithmetic; a bar
// answers "how much of my traffic is not people?" before you have finished reading it.

function Count({ tone, label, value, sub, tooltipId, loading }) {
  const tones = {
    people: {
      bar: "bg-emerald-400",
      text: "text-emerald-300",
      edge: "border-t-emerald-400/70",
      glow: "from-emerald-500/[0.07]",
    },
    machines: {
      bar: "bg-violet-400",
      text: "text-violet-300",
      edge: "border-t-violet-400/70",
      glow: "from-violet-500/[0.07]",
    },
    wrong: {
      bar: "bg-amber-400",
      text: "text-amber-300",
      edge: "border-t-amber-400/70",
      glow: "from-amber-500/[0.07]",
    },
  }[tone];

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-surface-600 border-t-2 ${tones.edge}
                  bg-gradient-to-b ${tones.glow} to-transparent bg-surface-800 px-5 py-4`}
    >
      <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400 font-medium">
        <StatTooltip id={tooltipId} value={value}>{label}</StatTooltip>
      </p>
      <p className={`mt-2 text-4xl sm:text-5xl font-semibold tabular-nums leading-none ${tones.text}`}>
        {loading ? <span className="text-slate-700">—</span> : (value ?? 0).toLocaleString()}
      </p>
      <p className="mt-2 text-xs text-slate-400 leading-relaxed min-h-[2rem]">
        {loading ? " " : sub}
      </p>
    </div>
  );
}

export default function HeadlineCounts({ data, loading }) {
  const people = data?.real_traffic_estimate ?? 0;
  const machines = data?.bot_visits ?? 0;
  const suspicious = data?.suspicious_sessions ?? 0;
  const ai = data?.ai_crawlers ?? 0;
  const otherBots = Math.max(0, machines - ai);

  const total = people + machines;
  const peopleShare = total ? (people / total) * 100 : 0;
  const machineShare = total ? (machines / total) * 100 : 0;

  return (
    <section className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Count
          tone="people"
          tooltipId="real_traffic"
          label="People"
          value={people}
          loading={loading}
          sub={
            <>
              {(data?.verified_humans ?? 0).toLocaleString()} verified ·{" "}
              {(data?.likely_humans ?? 0).toLocaleString()} likely
              {data?.traffic_confidence ? ` · ${data.traffic_confidence} confidence` : ""}
            </>
          }
        />
        <Count
          tone="machines"
          tooltipId="automated_traffic"
          label="Automated"
          value={machines}
          loading={loading}
          sub={
            <>
              {ai.toLocaleString()} AI crawler{ai === 1 ? "" : "s"} ·{" "}
              {otherBots.toLocaleString()} other bot{otherBots === 1 ? "" : "s"}
            </>
          }
        />
        <Count
          tone="wrong"
          tooltipId="suspicious_sessions"
          label="Looked wrong"
          value={suspicious}
          loading={loading}
          sub="Sessions that behaved like scanners, or claimed to be something they were not"
        />
      </div>

      {/* The comparison the other dashboards never draw. */}
      {!loading && total > 0 && (
        <div>
          <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-700">
            <div className="bg-emerald-400/90" style={{ width: `${peopleShare}%` }} />
            <div className="bg-violet-400/90" style={{ width: `${machineShare}%` }} />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            <span className="text-emerald-300 font-medium">{peopleShare.toFixed(0)}% people</span>
            {" · "}
            <span className="text-violet-300 font-medium">{machineShare.toFixed(0)}% machines</span>
            {" — "}
            {machineShare > peopleShare
              ? "most of what reached your site this period was not a person."
              : "of everything that reached your site this period."}
          </p>
        </div>
      )}

      {data?.note && <p className="text-xs text-amber-300/80">{data.note}</p>}
    </section>
  );
}
