"use client";

import { useId, useState } from "react";
import type { Dataset, Result } from "@/lib/types";
import { formatNumber } from "@/lib/api";
import { percent } from "@/components/results/result-details";

type CoverageView = "baseline" | "optimized" | "change";
const coverageViews: Record<CoverageView, string> = {
  baseline: "Existing sites",
  optimized: "Optimized plan",
  change: "Change in covered visits",
};

export function Network({ dataset, comparison }: {
  dataset: Dataset;
  comparison?: { baseline: Result; optimized: Result };
}) {
  const patternId = useId();
  const maskId = useId();
  const [layer, setLayer] = useState<"all" | "existing" | "candidate">("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<CoverageView>("change");
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
  const baseline = new Map(comparison?.baseline.metrics.clusters.map((row) => [row.community_id, row]));
  const optimized = new Map(comparison?.optimized.metrics.clusters.map((row) => [row.community_id, row]));
  const activeCandidates = new Set(view === "baseline" ? [] : comparison?.optimized.selected_candidate_ids);
  const selectedBefore = baseline.get(selected ?? "");
  const selectedAfter = optimized.get(selected ?? "");
  const groupX = new Map<string, number>();
  const boundary = "M41 86 83 47 154 29 257 43 339 19 441 32 477 51 604 33 675 72 687 131 663 199 696 253 674 323 631 353 526 349 466 377 373 353 273 375 222 350 114 354 50 312 55 235 24 182Z";

  return <section className="panel map-panel" aria-label="Synthetic service network">
    <div className="section-head"><div><h2>{comparison ? "Coverage on the service network" : "Service network"}</h2><p className="muted">Schematic positions and modeled travel links</p></div>
      {comparison && <label className="layer-control">Coverage view <select value={view}
        onChange={(event) => setView(event.target.value as CoverageView)}>
        {Object.entries(coverageViews).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>}
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
        const before = baseline.get(row.id), after = optimized.get(row.id);
        let fill = "#316b60";
        let marker = row.id;
        let tooltip = row.label;
        if (before && after) {
          const delta = after.covered_visits - before.covered_visits;
          const coverage = (view === "baseline" ? before : after).coverage_pct;
          if (view === "change") {
            fill = delta > 0 ? "#087357" : delta < 0 ? "#9f3f1e" : "#52666a";
            marker = delta > 0 ? "+" : delta < 0 ? "−" : "=";
          } else {
            fill = coverage === 0 ? "#9f3f1e" : coverage !== null && coverage < 50 ? "#805919" : "#316b60";
            marker = coverage === null ? "—" : Math.round(coverage) + "%";
          }
          tooltip += " · Existing sites " + percent(before.coverage_pct) + " · Optimized " + percent(after.coverage_pct);
        }
        return <g key={row.id} role="button" tabIndex={0} aria-label={tooltip}
          aria-pressed={active} className="map-target" onClick={() => setSelected(row.id)}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(row.id); } }}>
          <circle cx={point.x} cy={point.y} r={active ? 17 : 15} fill={fill} stroke="#f4fbf8" strokeWidth={active ? 3 : 2} />
          <title>{tooltip}</title>
          <text x={point.x} y={point.y + 3.5} fill="white" textAnchor="middle" fontSize={view === "change" && comparison ? 14 : 8.5} fontWeight="700">{marker}</text>
        </g>;
      })}
      {shownSites.map((site) => {
        const point = points.get(site.node_id);
        if (!point) return null;
        const offset = groupX.get(site.node_id) ?? 0;
        groupX.set(site.node_id, offset + 17);
        const x = point.x + 12 + offset, y = point.y - 14;
        const candidate = site.type === "candidate", active = selected === site.id;
        const opened = activeCandidates.has(site.id);
        const label = site.label + (opened ? " · Selected site" : "");
        return <g key={site.id} role="button" tabIndex={0} aria-label={label}
          aria-pressed={active} className="map-target" onClick={() => setSelected(site.id)}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(site.id); } }}>
          <path d={candidate ? "M0-9 9 0 0 9-9 0Z" : "M-8-8H8V8H-8Z"} transform={"translate(" + x + " " + y + ")"}
            fill={opened ? "#194595" : candidate ? "#a35f12" : "#11534a"} stroke={active ? "#101f24" : "white"} strokeWidth="1.6" />
          <title>{label}</title>
          <path d={opened ? "M" + (x - 4) + " " + y + "l3 3 5-6" : "M" + (x - 3) + " " + y + "h6m-3-3v6"}
            fill="none" stroke="white" strokeWidth="1.4" />
        </g>;
      })}
    </svg>
    <div className="map-legend">
      {comparison
        ? <span>{view === "change" ? "+ Gain · − Loss · = No change" : "% Within-threshold coverage · Amber below 50% · Red at 0%"}</span>
        : <span><i className="legend-dot" /> Community cluster</span>}
      <span><i className="legend-square" /> Existing site</span>
      <span><i className="legend-diamond" /> Candidate zone</span>
      {comparison && view !== "baseline" && <span>✓ Selected site</span>}
    </div>
    <div className="map-selection" aria-live="polite">
      {selectedCommunity ? <><b>{selectedCommunity.label}</b> · {selectedBefore && selectedAfter
        ? <>Covered visits/week {formatNumber(selectedBefore.covered_visits)} → {formatNumber(selectedAfter.covered_visits)} of {formatNumber(selectedAfter.demand_visits)} requested</>
        : <>{formatNumber(selectedCommunity.demand_visits_per_week)} requested visits/week</>}</>
        : selectedSite ? <><b>{selectedSite.label}</b> · {formatNumber(selectedSite.capacity_per_week)} visits/week capacity{activeCandidates.has(selectedSite.id) && " · Selected site"}</>
          : "Select a community or site to inspect it."}
    </div>
  </section>;
}
