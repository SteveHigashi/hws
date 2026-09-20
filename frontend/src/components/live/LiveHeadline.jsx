import { useEffect, useState } from "react";
import api from "../../utils/api";
import { useSiteStore } from "../../store/siteStore";

function timeAgo(isoString) {
  if (!isoString) return "";
  const diff = Math.floor((Date.now() - new Date(isoString + "Z").getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// Shown at the top of Catalogue Protection and AI Crawlers: the headline of the
// current reading from whichever provider is set (rules by default, so every
// install sees one). Silent (renders nothing) only when there is no site.
export default function LiveHeadline() {
  const [data, setData] = useState(null);
  const { currentSiteId } = useSiteStore();

  useEffect(() => {
    if (!currentSiteId) {
      setData(null);
      return;
    }
    api.get("/reading").then(({ data }) => setData(data)).catch(() => setData(null));
  }, [currentSiteId]);

  if (!data?.reading) return null;
  const when = data.provider_used === "live" ? timeAgo(data.generated_at) : "just now";

  return (
    <div className="flex items-center gap-2 bg-violet-500/10 border border-violet-500/30 rounded-xl px-4 py-2.5 text-sm">
      <span className="text-violet-400 shrink-0">✦</span>
      <span className="text-slate-200 truncate">{data.reading.headline}</span>
      <span className="text-xs text-slate-500 ml-auto shrink-0">{data.label} · {when}</span>
    </div>
  );
}
