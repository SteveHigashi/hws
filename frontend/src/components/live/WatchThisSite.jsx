import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../utils/api";
import { useSiteStore } from "../../store/siteStore";

// The reading card on Overview. Every install gets a reading: by default the
// fixed rules on this box (free, nothing sent anywhere); with the customer's own
// model key, the same prompt through that key (still local); with a Live key,
// Higashi Live's reading with history and comparisons. The eyebrow names who
// wrote it. "Watch this site" asks Live for a fresh reading (or routes to the
// Live card in Intelligence when there is no key yet).
export default function WatchThisSite() {
  const navigate = useNavigate();
  const { currentSiteId } = useSiteStore();
  const [keySet, setKeySet] = useState(null);
  const [reading, setReading] = useState(null);
  const [label, setLabel] = useState("Higashi rules");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/admin/settings/live")
      .then(({ data }) => setKeySet(data.live_key_set))
      .catch(() => setKeySet(false));
  }, []);

  useEffect(() => {
    if (!currentSiteId) return;
    setReading(null);
    setNote("");
    api.get("/reading")
      .then(({ data }) => {
        setReading(data.reading);
        setLabel(data.label || "Higashi rules");
        setNote(data.note || "");
      })
      .catch(() => {});
  }, [currentSiteId]);

  const handleClick = async () => {
    if (!keySet) {
      navigate("/dashboard/intelligence?openLive=1");
      return;
    }
    setLoading(true);
    setError("");
    try {
      // POSTs do not get site_id from the interceptor; without it the backend reports
      // the first site in the table, whatever the page shows (found 2026-09-20).
      const { data } = await api.post("/live/watch", null, { params: { site_id: currentSiteId } });
      setReading(data);
      setLabel("Higashi Live");
      setNote("");
    } catch (err) {
      const detail = err.response?.data?.error || err.response?.data?.detail;
      // 502 = Live itself did not answer; anything else is this install failing to keep the reading.
      setError(detail || (err.response?.status === 502 ? "Could not reach Higashi Live" : "Live answered, but this install could not save the reading. Try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <button
        onClick={handleClick}
        disabled={loading}
        className="flex items-center gap-2 bg-violet-500/15 hover:bg-violet-500/25 border border-violet-500/40 disabled:opacity-50 text-violet-300 text-sm px-4 py-2 rounded-lg transition-colors"
      >
        <span>✦</span>
        {loading ? "Watching…" : "Watch this site"}
      </button>

      {error && (
        <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</p>
      )}

      {reading && (
        <div className="border border-violet-500/40 bg-violet-500/5 rounded-xl p-6 space-y-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-violet-300/70">{label}</p>
            <h2 className="text-2xl font-semibold text-white mt-2 leading-snug">{reading.headline}</h2>
            {note && <p className="text-xs text-slate-500 mt-1">{note}</p>}
          </div>

          {reading.paragraphs?.map((p, i) => (
            <p key={i} className="text-sm text-slate-300 leading-relaxed">{p}</p>
          ))}

          {reading.changes?.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Since last time</p>
              <ul className="space-y-1">
                {reading.changes.map((c, i) => (
                  <li key={i} className="text-sm text-slate-300 flex gap-2">
                    <span className="text-violet-400 shrink-0">·</span>{c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {reading.benchmarks?.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Normal for a site your size</p>
              <ul className="space-y-1">
                {reading.benchmarks.map((b, i) => (
                  <li key={i} className="text-sm text-slate-400 flex gap-2">
                    <span className="text-violet-400 shrink-0">·</span>{b}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
