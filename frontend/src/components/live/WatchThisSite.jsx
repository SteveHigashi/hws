import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../utils/api";
import { useSiteStore } from "../../store/siteStore";

// The dashboard's entry point into Higashi Live. No key configured → routes
// to the Live settings card in Intelligence. Key set → calls /live/watch and
// renders the reading in the same card language as the Catalogue Protection
// verdict box (bordered card, uppercase eyebrow label, large headline).
export default function WatchThisSite() {
  const navigate = useNavigate();
  const { currentSiteId } = useSiteStore();
  const [keySet, setKeySet] = useState(null);
  const [reading, setReading] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/admin/settings/live")
      .then(({ data }) => setKeySet(data.live_key_set))
      .catch(() => setKeySet(false));
  }, []);

  useEffect(() => {
    if (!currentSiteId || keySet !== true) return;
    api.get("/live/reading").then(({ data }) => setReading(data)).catch(() => {});
  }, [currentSiteId, keySet]);

  const handleClick = async () => {
    if (!keySet) {
      navigate("/dashboard/intelligence?openLive=1");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/live/watch");
      setReading(data);
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.detail || "Could not reach Higashi Live");
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
            <p className="text-xs uppercase tracking-widest text-violet-300/70">Higashi Live</p>
            <h2 className="text-2xl font-semibold text-white mt-2 leading-snug">{reading.headline}</h2>
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
