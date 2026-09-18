import { useEffect, useRef, useState } from "react";
import api from "../utils/api";

// Raw nginx feed, tailed over SSH by the backend. Unlike Real-time (which
// reports beacons the tracker sent us) this shows every request the server
// actually answered, including the ones from clients that never run our JS —
// which is precisely the traffic worth watching during a scraping incident.

const SEGMENT_STYLE = {
  commercial_dc:      "text-amber-300  bg-amber-500/10",
  commercial_network: "text-emerald-300 bg-emerald-500/10",
  telco:              "text-emerald-300 bg-emerald-500/10",
  enterprise:         "text-sky-300    bg-sky-500/10",
  education:          "text-sky-300    bg-sky-500/10",
  government:         "text-sky-300    bg-sky-500/10",
  military:           "text-sky-300    bg-sky-500/10",
  dead:               "text-slate-400  bg-slate-500/10",
};

const UA_STYLE = {
  declared:    "text-violet-300",
  "browser-ua": "text-slate-200",
  none:        "text-slate-500",
  other:       "text-slate-400",
};

function Stat({ label, value, tone = "text-white", hint }) {
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
      <p className="text-[10px] text-slate-500 uppercase tracking-widest">{label}</p>
      <p className={`font-mono font-semibold text-2xl leading-none mt-2 ${tone}`}>
        {value ?? "—"}
      </p>
      {hint && <p className="text-[10px] text-slate-500 mt-1.5">{hint}</p>}
    </div>
  );
}

function Row({ r }) {
  // A block is a good outcome here, so it reads green rather than red.
  const status = r.blocked
    ? "text-emerald-400"
    : r.status >= 500 ? "text-red-400"
    : r.status >= 300 && r.status < 400 ? "text-slate-500"
    : "text-slate-300";

  const seg = SEGMENT_STYLE[r.segment] || "text-slate-400 bg-slate-500/10";

  return (
    <tr className={`border-b border-surface-700/50 ${r.suspect && !r.blocked ? "bg-amber-500/[0.04]" : ""}`}>
      <td className="py-1 pr-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">{r.time}</td>
      <td className={`py-1 pr-3 font-mono text-[11px] font-semibold ${status}`}>{r.status}</td>
      <td className="py-1 pr-3 font-mono text-[11px] text-slate-400 max-w-[10rem] truncate" title={r.ip}>
        {r.ip}
      </td>
      <td className="py-1 pr-3">
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${seg}`}>
          {r.segment || "unknown"}
        </span>
      </td>
      <td className="py-1 pr-3 text-[11px] text-slate-400 max-w-[11rem] truncate" title={r.org || ""}>
        {r.org || "—"}
      </td>
      <td className={`py-1 pr-3 font-mono text-[11px] max-w-[22rem] truncate ${r.is_record ? "text-cyan-300" : "text-slate-300"}`} title={r.path}>
        {r.path}
      </td>
      <td className="py-1 pr-3 font-mono text-[10px] text-slate-500 whitespace-nowrap">
        {r.ip_hits}
        <span className={r.ip_assets === 0 ? "text-amber-400" : "text-slate-600"}>
          {" "}/{r.ip_assets}
        </span>
      </td>
      <td className={`py-1 text-[10px] max-w-[14rem] truncate ${UA_STYLE[r.ua_class] || "text-slate-400"}`} title={r.ua}>
        {r.ua_class === "declared" ? r.ua : r.ua_class}
      </td>
    </tr>
  );
}

export default function LiveTraffic() {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [meta, setMeta] = useState({ connected: false, error: null, host: null });
  const [paused, setPaused] = useState(false);
  const [onlySuspect, setOnlySuspect] = useState(false);
  const cursor = useRef(0);
  const pausedRef = useRef(false);

  useEffect(() => { pausedRef.current = paused; }, [paused]);

  useEffect(() => {
    let alive = true;

    const poll = () => {
      if (pausedRef.current) return;
      api.get(`/live-traffic/feed?since=${cursor.current}`)
        .then(({ data }) => {
          if (!alive) return;
          setMeta({ connected: data.connected, error: data.error, host: data.host });
          if (data.rows?.length) {
            cursor.current = data.cursor;
            // Newest first, bounded so the DOM cannot grow without limit.
            setRows((prev) => [...data.rows.reverse(), ...prev].slice(0, 300));
          }
        })
        .catch(() => {});
      api.get("/live-traffic/stats")
        .then(({ data }) => alive && setStats(data))
        .catch(() => {});
    };

    poll();
    const id = setInterval(poll, 2000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const shown = onlySuspect ? rows.filter((r) => r.suspect && !r.blocked) : rows;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-white">Live Traffic</h1>
          <p className="text-xs text-slate-500 mt-1">
            Raw nginx log{meta.host ? ` from ${meta.host}` : ""}, tailed and classified against the ASN atlas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOnlySuspect((v) => !v)}
            className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
              onlySuspect
                ? "bg-amber-500/15 border-amber-500/40 text-amber-300"
                : "bg-surface-800 border-surface-600 text-slate-400 hover:text-slate-200"
            }`}
          >
            Suspect only
          </button>
          <button
            onClick={() => setPaused((v) => !v)}
            className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
              paused
                ? "bg-surface-700 border-surface-600 text-slate-300"
                : "bg-surface-800 border-surface-600 text-slate-400 hover:text-slate-200"
            }`}
          >
            {paused ? "Resume" : "Pause"}
          </button>
          <span className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className={`w-2 h-2 rounded-full ${meta.connected ? "bg-success pulse-dot" : "bg-slate-600"}`} />
            {meta.connected ? "live" : "disconnected"}
          </span>
        </div>
      </div>

      {meta.error && !meta.connected && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-xs text-red-300 font-mono">
          {meta.error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat label="Page requests" value={stats?.page_requests} hint="assets excluded" />
        <Stat label="Blocked" value={stats?.blocked} tone="text-emerald-400" hint="403 / 429" />
        <Stat label="Distinct IPs" value={stats?.distinct_ips} />
        <Stat
          label="One-shot IPs"
          value={stats?.single_request_ips}
          tone={stats && stats.single_request_ips > stats.distinct_ips * 0.6 ? "text-amber-300" : "text-white"}
          hint="1 request, never returned"
        />
        <Stat label="Suspect" value={stats?.suspect} tone="text-amber-300" hint="browser UA, no assets" />
        <Stat label="Records served" value={stats?.records_served} tone="text-cyan-300" hint="profile pages, not blocked" />
      </div>

      {stats?.by_segment && Object.keys(stats.by_segment).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.by_segment).map(([seg, n]) => (
            <span
              key={seg}
              className={`px-2 py-1 rounded text-[11px] font-mono ${SEGMENT_STYLE[seg] || "text-slate-400 bg-slate-500/10"}`}
            >
              {seg} {n}
            </span>
          ))}
        </div>
      )}

      <div className="bg-surface-800 border border-surface-600 rounded-xl overflow-hidden">
        <div className="overflow-x-auto max-h-[34rem] overflow-y-auto">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-surface-800 z-10">
              <tr className="text-[10px] uppercase tracking-widest text-slate-500 border-b border-surface-600">
                <th className="py-2 pr-3 font-normal">Time</th>
                <th className="py-2 pr-3 font-normal">St</th>
                <th className="py-2 pr-3 font-normal">Client IP</th>
                <th className="py-2 pr-3 font-normal">Segment</th>
                <th className="py-2 pr-3 font-normal">Network</th>
                <th className="py-2 pr-3 font-normal">Path</th>
                <th className="py-2 pr-3 font-normal" title="requests from this IP / how many were assets">
                  Hits/Ast
                </th>
                <th className="py-2 font-normal">Client</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => <Row key={r.seq} r={r} />)}
            </tbody>
          </table>
          {shown.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-10">
              {meta.connected ? "Waiting for requests…" : "Not connected to the log."}
            </p>
          )}
        </div>
      </div>

      <p className="text-[11px] text-slate-600 leading-relaxed">
        Amber rows are browser user-agents that have never fetched a stylesheet — the shape of a
        scripted client rather than a person. <span className="text-slate-500">Hits/Ast</span> is
        requests from that address and how many were assets; a column of{" "}
        <span className="font-mono">1/0</span> across many different addresses is a rotating proxy
        pool. Segment labels come from the ASN atlas and are advisory: AWS is labelled{" "}
        <span className="font-mono">enterprise</span> and Google{" "}
        <span className="font-mono">commercial_dc</span>, so read them, don't block on them.
      </p>
    </div>
  );
}
