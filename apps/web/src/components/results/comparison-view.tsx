"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, post } from "@/lib/api";
import type { Comparison, Dataset, Result, RunSnapshot } from "@/lib/types";

import { AuditDetails, dataType, decimal, integer, minutes, money, percent, PlanAssumptions, ResultStatus } from "./result-details";
import styles from "./results.module.css";

function ComparePicker({ baselineId, alternativeId }: {
  baselineId?: string;
  alternativeId?: string;
}) {
  const [runs, setRuns] = useState<RunSnapshot[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api<RunSnapshot[]>("/runs", { signal: controller.signal })
      .then(setRuns)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Run history is unavailable.");
      });
    return () => controller.abort();
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!runs) return <p role="status" className="muted">Loading saved runs…</p>;
  const baselineRuns = runs.filter((run) => run.kind === "baseline" && run.status === "COMPLETED");
  const alternativeRuns = runs.filter((run) => run.kind !== "baseline" && run.status === "COMPLETED");
  if (!baselineRuns.length || !alternativeRuns.length) {
    return (
      <>
        <p className="muted">Complete and audit a baseline and an alternative to compare their allocations.</p>
        <Link className="button primary" href="/scenarios/new">Start a scenario</Link>
      </>
    );
  }
  return (
    <form method="get" action="/compare" className={styles.picker}>
      <label>Baseline
        <select name="baseline" required defaultValue={baselineId ?? ""}>
          <option value="" disabled>Select a baseline</option>
          {baselineRuns.map((run) => (
            <option key={run.run_id} value={run.run_id}>{run.run_id.slice(0, 16)}… · {run.solver_status}</option>
          ))}
        </select>
      </label>
      <label>Alternative
        <select name="alternative" required defaultValue={alternativeId ?? ""}>
          <option value="" disabled>Select an alternative</option>
          {alternativeRuns.map((run) => (
            <option key={run.run_id} value={run.run_id}>{run.run_id.slice(0, 16)}… · {run.solver_status}</option>
          ))}
        </select>
      </label>
      <button type="submit" className="button primary">Compare runs</button>
    </form>
  );
}

function pp(value: number | null) {
  return value === null ? "Unavailable" : (value > 0 ? "+" : "") + decimal(value) + " pp";
}

function siteLoads(result: Result) {
  const loads = new Map<string, number>();
  for (const row of result.assignments) {
    loads.set(row.site_id, (loads.get(row.site_id) ?? 0) + row.visits);
  }
  return loads;
}

function AllocationSummary({ comparison, dataset }: { comparison: Comparison; dataset: Dataset }) {
  const { baseline, alternative } = comparison;
  const base = siteLoads(baseline);
  const alt = siteLoads(alternative);
  const selected = new Set(alternative.selected_candidate_ids);
  const sites = dataset.sites.filter((site) => site.type === "existing" || selected.has(site.id));
  return (
    <section className={"panel " + styles.section}>
      <div>
        <h2>Service-site allocations</h2>
        <p className="muted">Modeled weekly assignments to existing sites and selected candidate zones.</p>
      </div>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="Site allocation comparison">
        <table className={styles.table}>
          <caption className={styles.srOnly}>Modeled weekly visits assigned by service site</caption>
          <thead>
            <tr><th scope="col">Service site</th><th scope="col">Type</th><th scope="col">Capacity</th>
              <th scope="col">Baseline visits</th><th scope="col">Alternative visits</th></tr>
          </thead>
          <tbody>{sites.map((site) => (
            <tr key={site.id}>
              <th scope="row">{site.label}</th>
              <td>{site.type === "existing" ? "Existing" : "Selected candidate"}</td>
              <td>{integer(site.capacity_per_week)}</td>
              <td>{site.type === "candidate" ? "Closed" : integer(base.get(site.id) ?? 0)}</td>
              <td>{integer(alt.get(site.id) ?? 0)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function ComparisonResults({ comparison, dataset }: { comparison: Comparison; dataset: Dataset }) {
  const { baseline, alternative, plan, deltas } = comparison;
  const base = baseline.metrics;
  const alt = alternative.metrics;
  const labels = new Map(dataset.communities.map((row) => [row.id, row.label]));
  const baseClusters = new Map(base.clusters.map((row) => [row.community_id, row]));
  const zoneByCommunity = new Map(dataset.communities.map((row) => [row.id, row.zone_class]));
  const zones = new Map<string, { demand: number; baseline: number; alternative: number }>();
  for (const cluster of alt.clusters) {
    // Audited runs on the same dataset contain exactly one row per community.
    const zone = zoneByCommunity.get(cluster.community_id)!;
    const totals = zones.get(zone) ?? { demand: 0, baseline: 0, alternative: 0 };
    totals.demand += cluster.demand_visits;
    totals.baseline += baseClusters.get(cluster.community_id)!.covered_visits;
    totals.alternative += cluster.covered_visits;
    zones.set(zone, totals);
  }
  const extraCost = deltas.additional_cost_per_added_covered_visit;
  const metrics = [
    {
      label: "Within-threshold coverage",
      baseline: percent(base.coverage_pct),
      alternative: percent(alt.coverage_pct),
      detail: pp(deltas.coverage_pp),
      definition: "Within-threshold visits divided by total demand, including unmet visits.",
    },
    { label: "Weekly visits served", baseline: integer(base.served_visits), alternative: integer(alt.served_visits), detail: percent(alt.served_rate_pct) + " of demand", definition: "Assigned visits at any reachable open site." },
    { label: "Weekly unmet demand", baseline: integer(base.unmet_visits), alternative: integer(alt.unmet_visits), detail: percent(alt.unmet_rate_pct) + " of demand", definition: "Demand visits with no modeled assignment." },
    { label: "Mean assigned travel", baseline: minutes(base.mean_assigned_travel_minutes), alternative: minutes(alt.mean_assigned_travel_minutes), detail: "Served visits only", definition: "Total assigned visit-minutes divided by served visits." },
    { label: "Worst cluster coverage", baseline: percent(base.worst_cluster_coverage_pct), alternative: percent(alt.worst_cluster_coverage_pct), detail: pp(deltas.worst_cluster_coverage_pp), definition: "The minimum coverage among clusters with positive demand." },
    { label: "Additional weekly cost", baseline: money(base.cost_pkr), alternative: money(alt.cost_pkr), detail: extraCost == null ? "Cost per added visit unavailable" : "PKR " + decimal(extraCost) + " per added covered visit", definition: "Fixed planning cost of active candidate sites." },
  ];
  return (
    <>
      <p className={styles.datasetTag}><span className="badge">{dataType(dataset)}</span>
        {" "}{dataset.district_label} · {dataset.version} · One modeled week</p>
      <Link className="button" href={"/stress?baseline=" + encodeURIComponent(baseline.run_id)
        + "&alternative=" + encodeURIComponent(alternative.run_id)}>Test uncertainty</Link>
      <section aria-label="Planning metrics" className={styles.kpis}>
        {metrics.map((metric) => (
          <article key={metric.label} className={"panel " + styles.kpi} title={metric.definition}>
            <h2>{metric.label}</h2>
            <p><strong>{metric.alternative}</strong></p>
            <p className="muted">Baseline {metric.baseline}</p>
            <p className={styles.kpiDetail}>{metric.detail}</p>
          </article>
        ))}
      </section>
      <section className={"panel " + styles.section}>
        <div className={styles.sectionHeader}>
          <div>
            <h2>Coverage by zone</h2>
            <p className="muted">Weekly visits within {plan.threshold_minutes} minutes, grouped by synthetic zone class.</p>
          </div>
        </div>
        <div className={styles.scroll} tabIndex={0} role="region" aria-label="Zone coverage comparison">
          <table className={styles.table}>
            <caption className={styles.srOnly}>Weekly coverage by zone class</caption>
            <thead><tr><th scope="col">Zone</th><th scope="col">Demand</th>
              <th scope="col">Baseline covered</th><th scope="col">Alternative covered</th></tr></thead>
            <tbody>{Array.from(zones, ([zone, totals]) => (
              <tr key={zone}><th scope="row">{zone}</th><td>{integer(totals.demand)}</td>
                <td>{integer(totals.baseline)} ({percent(totals.demand ? 100 * totals.baseline / totals.demand : null)})</td>
                <td>{integer(totals.alternative)} ({percent(totals.demand ? 100 * totals.alternative / totals.demand : null)})</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
      <section className={"panel " + styles.section}>
        <div className={styles.sectionHeader}>
          <div>
            <h2>Coverage by community</h2>
            <p className="muted">Assigned visits within {plan.threshold_minutes} minutes, as a share of weekly demand.</p>
          </div>
          <div className={styles.legend} aria-hidden="true"><span>Baseline</span><span>Alternative</span></div>
        </div>
        <div className={styles.scroll} tabIndex={0} role="region" aria-label="Community coverage comparison">
          <table className={styles.table}>
            <caption className={styles.srOnly}>Baseline and alternative within-threshold coverage by community</caption>
            <thead><tr><th scope="col">Community</th><th scope="col">Demand</th>
              <th scope="col">Baseline coverage</th><th scope="col">Alternative coverage</th>
              <th scope="col">Baseline unmet</th><th scope="col">Alternative unmet</th></tr></thead>
            <tbody>{alt.clusters.map((row) => {
              const previous = baseClusters.get(row.community_id);
              return (
                <tr key={row.community_id}>
                  <th scope="row">{labels.get(row.community_id) ?? row.community_id}</th>
                  <td>{integer(row.demand_visits)}</td>
                  <td><span className={styles.barRow} title={previous && integer(previous.covered_visits) + " covered visits"}>
                    <span>{percent(previous?.coverage_pct ?? null)}</span>
                    <span className={styles.track} aria-hidden="true"><span style={{ width: (previous?.coverage_pct ?? 0) + "%" }} /></span></span></td>
                  <td><span className={styles.barRow} title={integer(row.covered_visits) + " covered visits"}><span>{percent(row.coverage_pct)}</span>
                    <span className={styles.track + " " + styles.alt} aria-hidden="true"><span style={{ width: (row.coverage_pct ?? 0) + "%" }} /></span></span></td>
                  <td>{previous ? integer(previous.unmet_visits) : "Unavailable"}</td>
                  <td>{integer(row.unmet_visits)}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      </section>
      <AllocationSummary comparison={comparison} dataset={dataset} />
      <div className={styles.twoColumns}>
        {[{ title: "Modeled baseline", link: "Baseline report", run: baseline }, { title: "Alternative allocation", link: "Alternative report", run: alternative }]
          .map(({ title, link, run }) => (
            <section className={"panel " + styles.section} key={run.run_id}>
              <h2>{title}</h2>
              <ResultStatus result={run} />
              <p className="muted">Candidate sites {run.selected_candidate_ids.join(", ") || "None"}</p>
              {run.warnings.map((warning) => <p key={warning} className="notice">{warning}</p>)}
              <AuditDetails result={run} />
              <Link className="button" href={"/reports/" + encodeURIComponent(run.run_id)}>{link}</Link>
            </section>
          ))}
      </div>
      <section className={"panel " + styles.section}>
        <h2>Shared assumptions</h2>
        <PlanAssumptions plan={plan} />
        <details>
          <summary>Metric definitions</summary>
          <dl className={styles.checkValues}>
            {metrics.map((metric) => (
              <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.definition}</dd></div>
            ))}
          </dl>
        </details>
        <p className="muted">Equity gap is the difference between the highest and lowest cluster coverage. It is {decimal(base.equity_gap_pp)} pp for baseline and {decimal(alt.equity_gap_pp)} pp for alternative.</p>
        <p className="muted">The cost per added covered visit uses added weekly cost divided by added within-threshold visits when that count is positive.</p>
      </section>
    </>
  );
}

export function ComparisonView({ baselineId, alternativeId }: {
  baselineId?: string;
  alternativeId?: string;
}) {
  const [loaded, setLoaded] = useState<{ key: string; comparison: Comparison; dataset: Dataset } | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([baselineId, alternativeId, attempt]);
  useEffect(() => {
    if (!baselineId || !alternativeId) return;
    let active = true;
    post<Comparison>("/comparisons", { baseline_run_id: baselineId, alternative_run_id: alternativeId })
      .then(async (comparison) => {
        if (!active) return;
        const dataset = await api<Dataset>("/datasets/" + encodeURIComponent(comparison.plan.dataset_version_id));
        if (active) setLoaded({ key, comparison, dataset });
      })
      .catch((err: unknown) => {
        if (active) setFailure({ key, message: err instanceof Error ? err.message : "Comparison is unavailable." });
      });
    return () => { active = false; };
  }, [baselineId, alternativeId, key]);
  const result = loaded?.key === key ? loaded : null;
  const error = failure?.key === key ? failure.message : null;
  return (
    <div className="stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Allocation review</p>
          <h1>Compare allocations</h1>
          <p className="muted">Review modeled service coverage and weekly costs under one confirmed plan.</p>
        </div>
        {result && <Link className="button" href="/compare">Choose different runs</Link>}
      </header>
      {result ? <ComparisonResults comparison={result.comparison} dataset={result.dataset} /> : (
        <section className={"panel " + styles.section}>
          {!baselineId || !alternativeId ? <h2>Choose saved runs</h2> : error ? (
            <div className="notice" role="alert"><h2>Comparison unavailable</h2><p>{error}</p>
              <button className="button" type="button" onClick={() => setAttempt(attempt + 1)}>Retry comparison</button></div>
          ) : <p role="status" className="muted">Checking saved allocations…</p>}
          {(!baselineId || !alternativeId || error) && <ComparePicker baselineId={baselineId} alternativeId={alternativeId} />}
        </section>
      )}
    </div>
  );
}
