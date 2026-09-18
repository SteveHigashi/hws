import { useEffect, useRef, useState } from "react";
import * as d3Sankey from "d3-sankey";

export default function SankeyChart({ data = { nodes: [], links: [] } }) {
  const svgRef = useRef(null);
  const [renderError, setRenderError] = useState(false);

  useEffect(() => {
    setRenderError(false);
    if (!svgRef.current || !data.nodes.length) return;

    const svg = svgRef.current;
    svg.innerHTML = "";

    try {
      const width = svg.parentElement?.offsetWidth || 600;
      const height = 340;
      svg.setAttribute("width", width);
      svg.setAttribute("height", height);

      const graph = {
        nodes: data.nodes.map((n) => ({ ...n })),
        links: data.links.map((l) => ({ ...l })),
      };

      const sankey = d3Sankey.sankey()
        .nodeId((d) => d.id)
        .nodeWidth(12)
        .nodePadding(14)
        .extent([[16, 16], [width - 16, height - 16]]);

      const { nodes, links } = sankey(graph);

      // Bail if layout produced NaN (remaining cycle or degenerate graph)
      if (nodes.some((n) => isNaN(n.x0) || isNaN(n.y0))) {
        setRenderError(true);
        return;
      }

      const ns = svg.namespaceURI;
      const g = document.createElementNS(ns, "g");
      svg.appendChild(g);

      links.forEach((link) => {
        const path = document.createElementNS(ns, "path");
        path.setAttribute("d", d3Sankey.sankeyLinkHorizontal()(link));
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", "#3b82f6");
        path.setAttribute("stroke-opacity", "0.18");
        path.setAttribute("stroke-width", Math.max(1, link.width));
        g.appendChild(path);
      });

      nodes.forEach((node) => {
        const rect = document.createElementNS(ns, "rect");
        rect.setAttribute("x", node.x0);
        rect.setAttribute("y", node.y0);
        rect.setAttribute("width", node.x1 - node.x0);
        rect.setAttribute("height", Math.max(1, node.y1 - node.y0));
        rect.setAttribute("fill", "#60a5fa");
        rect.setAttribute("rx", "3");
        g.appendChild(rect);

        const text = document.createElementNS(ns, "text");
        const isRight = node.x1 > width / 2;
        text.setAttribute("x", isRight ? node.x0 - 4 : node.x1 + 4);
        text.setAttribute("y", (node.y0 + node.y1) / 2);
        text.setAttribute("dy", "0.35em");
        text.setAttribute("text-anchor", isRight ? "end" : "start");
        text.setAttribute("fill", "#94a3b8");
        text.setAttribute("font-size", "11");
        text.setAttribute("font-family", "Inter, sans-serif");
        text.textContent = node.id.length > 28 ? node.id.slice(0, 26) + "…" : node.id;
        g.appendChild(text);
      });
    } catch (_) {
      setRenderError(true);
    }
  }, [data]);

  if (!data.nodes.length || renderError) {
    return (
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 flex items-center justify-center" style={{ height: 380 }}>
        <p className="text-slate-500 text-sm">
          {renderError ? "Not enough multi-page sessions to draw a flow yet." : "Not enough session data yet for flow analysis"}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 glow">
      <p className="text-sm font-medium text-slate-300 mb-1">Session Flow</p>
      <p className="text-xs text-slate-500 mb-4">How visitors move through your site</p>
      <svg ref={svgRef} style={{ width: "100%", overflow: "visible" }} />
    </div>
  );
}
