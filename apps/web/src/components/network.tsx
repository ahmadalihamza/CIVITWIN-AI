"use client";

import { useId, useState } from "react";
import type { Dataset } from "@/lib/types";
import { formatNumber } from "@/lib/api";

export function Network({ dataset }: { dataset: Dataset }) {
  const patternId = useId();
  const maskId = useId();
  const [layer, setLayer] = useState<"all" | "existing" | "candidate">("all");
  const [selected, setSelected] = useState<string | null>(null);
  const maxX = Math.max(...dataset.nodes.map((node) => node.display_x));
  const maxY = Math.max(...dataset.nodes.map((node) => node.display_y));
  const minX = Math.min(...dataset.nodes.map((node) => node.display_x));
  const minY = Math.min(...dataset.nodes.map((node) => node.display_y));
  const points = new Map(dataset.nodes.map((node) => [node.id, {
    x: 96 + (node.display_x - minX) * 530 / Math.max(1, maxX - minX),
    y: 68 + (node.display_y - minY) * 248 / Math.max(1, maxY - minY),
  }]));
  const communities = new Map(dataset.communities.map((row) => [row.node_id, row]));
  const selectedCommunity = dataset.communities.find((row) => row.id === selected);
  const selectedSite = dataset.sites.find((row) => row.id === selected);
  const shownSites = dataset.sites.filter((site) => layer === "all" || site.type === layer);
  const groupX = new Map<string, number>();
  const boundary = "M41 86 83 47 154 29 257 43 339 19 441 32 477 51 604 33 675 72 687 131 663 199 696 253 674 323 631 353 526 349 466 377 373 353 273 375 222 350 114 354 50 312 55 235 24 182Z";

  return <section className="panel map-panel" aria-label="Synthetic service network">
    <div className="section-head"><div><h2>Service network</h2><p className="muted">Schematic positions and modeled travel links</p></div>
      <label className="layer-control">Sites <select value={layer} onChange={(event) =>
        setLayer(event.target.value as typeof layer)}><option value="all">All sites</option>
        <option value="existing">Existing</option><option value="candidate">Candidates</option>
      </select></label>
    </div>
    <svg className="network" viewBox="0 0 720 395" role="group" aria-label="Interactive schematic. Select a cluster or site to inspect it.">
      <defs>
        <pattern id={patternId} width="21" height="36" patternUnits="userSpaceOnUse">
          <path d="M0 6 10.5 0 21 6v12l-10.5 6L0 18ZM0 30l10.5-6L21 30v6M0 30v6" fill="none" stroke="#adc5b8" strokeWidth=".7" />
        </pattern>
        <clipPath id={maskId}><path d={boundary} /></clipPath>
      </defs>
      <rect width="720" height="395" fill="#edf3ef" />
      <path d="M-30 259c120-65 190-35 255-73 69-42 143-44 211-11 108 55 187-11 301-69M-20 333c191-31 227 20 317-39 85-57 154-60 226-36 74 26 155 13 215-37M54-20c12 65 3 111-25 172s17 132 45 197 11 97-7 106" fill="none" stroke="#dce9e1" strokeWidth="14" />
      <path d={boundary} fill="#dfebe4" stroke="#60887c" strokeWidth="2" />
      <rect width="720" height="395" fill={"url(#" + patternId + ")"} clipPath={"url(#" + maskId + ")"} opacity=".63" />
      {dataset.edges.map((edge) => {
        const a = points.get(edge.from_node), b = points.get(edge.to_node);
        if (!a || !b) return null;
        return <line key={edge.from_node + "/" + edge.to_node} x1={a.x} x2={b.x} y1={a.y} y2={b.y}
          stroke="#789f94" strokeWidth="1.5" strokeDasharray={edge.direction === "forward" ? "4 3" : undefined}><title>{edge.minutes} minutes</title></line>;
      })}
      {dataset.nodes.map((node) => {
        const row = communities.get(node.id), point = points.get(node.id);
        if (!row || !point) return null;
        const active = selected === row.id;
        return <g key={row.id} role="button" tabIndex={0} aria-label={row.label}
          aria-pressed={active} className="map-target" onClick={() => setSelected(row.id)}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(row.id); } }}>
          <circle cx={point.x} cy={point.y} r={active ? 17 : 15} fill={active ? "#073d37" : "#316b60"} stroke="#f4fbf8" strokeWidth="2" />
          <text x={point.x} y={point.y + 3.5} fill="white" textAnchor="middle" fontSize="8.5" fontWeight="700">{row.id}</text>
        </g>;
      })}
      {shownSites.map((site) => {
        const point = points.get(site.node_id);
        if (!point) return null;
        const offset = groupX.get(site.node_id) ?? 0;
        groupX.set(site.node_id, offset + 17);
        const x = point.x + 12 + offset, y = point.y - 14;
        const candidate = site.type === "candidate", active = selected === site.id;
        return <g key={site.id} role="button" tabIndex={0} aria-label={site.label}
          aria-pressed={active} className="map-target" onClick={() => setSelected(site.id)}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(site.id); } }}>
          <path d={candidate ? "M0-9 9 0 0 9-9 0Z" : "M-8-8H8V8H-8Z"} transform={"translate(" + x + " " + y + ")"}
            fill={candidate ? "#c57b21" : "#11534a"} stroke={active ? "#101f24" : "white"} strokeWidth="1.6" />
          <path d={"M" + (x - 3) + " " + y + "h6m-3-3v6"} stroke="white" strokeWidth="1.2" />
        </g>;
      })}
    </svg>
    <div className="map-legend">
      <span><i className="legend-dot" /> Community cluster</span>
      <span><i className="legend-square" /> Existing site</span>
      <span><i className="legend-diamond" /> Candidate zone</span>
    </div>
    <div className="map-selection" aria-live="polite">
      {selectedCommunity ? <><b>{selectedCommunity.label}</b> · {formatNumber(selectedCommunity.demand_visits_per_week)} requested visits/week</>
        : selectedSite ? <><b>{selectedSite.label}</b> · {formatNumber(selectedSite.capacity_per_week)} visits/week capacity</>
          : "Select a cluster or site to see its input values."}
    </div>
  </section>;
}
