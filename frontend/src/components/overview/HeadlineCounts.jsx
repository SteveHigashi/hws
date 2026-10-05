import StatTooltip from "../charts/StatTooltip";

function PeopleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-5 w-5">
      <path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8-1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" stroke="currentColor" strokeWidth="1.7" />
      <path d="M3.5 19c.3-3.2 1.8-5 4.5-5s4.2 1.8 4.5 5M13 14c.7-.8 1.7-1.2 3-1.2 2.6 0 4 1.7 4.3 4.7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function AutomatedIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-5 w-5">
      <rect x="4" y="7" width="16" height="12" rx="3" stroke="currentColor" strokeWidth="1.7" />
      <path d="M12 3v4M8 13h.01M16 13h.01M8.5 16h7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function PageviewIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-5 w-5">
      <path d="M2.8 12s3.3-5 9.2-5 9.2 5 9.2 5-3.3 5-9.2 5-9.2-5-9.2-5Z" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

function KpiCard({ icon, label, value, tooltipId, tone, children, loading }) {
  const tones = {
    people: { edge: "border-t-success", icon: "text-success bg-success/10" },
    automated: { edge: "border-t-danger", icon: "text-danger bg-danger/10" },
    pageviews: { edge: "border-t-accent", icon: "text-accent-glow bg-accent/10" },
  }[tone];

  return (
    <div className={`rounded-xl border border-surface-600 border-t-2 bg-surface-800 p-5 ${tones.edge}`}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400">
          <StatTooltip id={tooltipId} value={value}>{label}</StatTooltip>
        </p>
        <span className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${tones.icon}`}>{icon}</span>
      </div>
      <p className="mt-3 font-mono text-3xl font-semibold leading-none tabular-nums text-white sm:text-4xl">
        {loading ? <span className="text-slate-700">—</span> : (value ?? 0).toLocaleString()}
      </p>
      <div className="mt-3 min-h-[1.25rem] text-xs text-slate-400">{loading ? "\u00a0" : children}</div>
    </div>
  );
}

export default function HeadlineCounts({ data, stats, loading }) {
  const people = data?.real_traffic_estimate ?? 0;
  const machines = data?.bot_visits ?? 0;
  const ai = data?.ai_crawlers ?? 0;
  const otherBots = data?.known_bots ?? Math.max(0, machines - ai);
  const total = people + machines;
  const peopleShare = total ? (people / total) * 100 : 0;
  const machineShare = total ? (machines / total) * 100 : 0;

  return (
    <section className="space-y-3">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <KpiCard icon={<PeopleIcon />} label="People" value={people} tooltipId="real_traffic" tone="people" loading={loading}>
          <span className="text-success">{peopleShare.toFixed(1)}%</span> of traffic · {(data?.verified_humans ?? 0).toLocaleString()} verified
        </KpiCard>
        <KpiCard icon={<AutomatedIcon />} label="Automated" value={machines} tooltipId="automated_traffic" tone="automated" loading={loading}>
          <span className="text-danger">{machineShare.toFixed(1)}%</span> of traffic · {ai.toLocaleString()} AI · {otherBots.toLocaleString()} other
        </KpiCard>
        {/* page_views counts rows in `events`, which holds non-bot traffic only; crawler
            activity lives in `bot_visits` and is reported by the Automated card beside this
            one. Labelling this "Pageviews" read as a site-wide total and quietly hid the
            12k machine requests sitting next to it. */}
        <KpiCard icon={<PageviewIcon />} label="Human pageviews" value={stats?.page_views} tooltipId="page_views" tone="pageviews" loading={loading || !stats}>
          {(stats?.sessions ?? 0).toLocaleString()} sessions · excludes {machines.toLocaleString()} automated
        </KpiCard>
      </div>
      {data?.note && <p className="text-xs text-warn">{data.note}</p>}
    </section>
  );
}
