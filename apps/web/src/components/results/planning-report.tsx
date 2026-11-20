"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, post } from "@/lib/api";
import type { Dataset, PlanSpec, Result, RunSnapshot } from "@/lib/types";

import { AuditDetails, dataType, decimal, integer, minutes, money, percent, PlanAssumptions, ResultStatus, runKind, SolverDetails } from "./result-details";
import styles from "./results.module.css";

type Report = {
  data_warning: string;
  time_horizon: string;
  dataset: Omit<Dataset, "reachable_pair_count" | "unreachable_pair_count">;
  plan: PlanSpec;
  result: Result;
};

type Explanation = {
  mode: string;
  claims: { text: string; evidence_ids: string[] }[];
  packet: { metrics: { id: string; label: string; path: string; value: number | string | null; unit: string }[] };
};

function Evidence({ runId }: { runId: string }) {
  const [evidence, setEvidence] = useState<Explanation>();
  const [failed, setFailed] = useState(false);
  const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const explanationPath = "/runs/" + encodeURIComponent(runId) + "/explanation";
  useEffect(() => {
    const controller = new AbortController();
    api<Explanation>(explanationPath, { signal: controller.signal })
      .then(setEvidence)
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    api<{ ai_enabled: boolean }>("/ready", { signal: controller.signal })
      .then((ready) => setAvailable(ready.ai_enabled)).catch(() => {});
    return () => controller.abort();
  }, [explanationPath]);

  async function requestNarration() {
    setBusy(true);
    setMessage("");
    try {
      const updated = await post<Explanation>(explanationPath);
      setEvidence(updated);
      setMessage(updated.mode === "provider" ? "AI-assisted wording applied." : "Showing the verified offline explanation.");
    } catch {
      setMessage("AI wording is unavailable. Showing the verified offline explanation.");
    } finally {
      setBusy(false);
    }
  }
  return <section className={"panel " + styles.section}>
    <h2>Evidence-linked explanation</h2>
    {evidence ? <>
      <ul className={styles.bullets}>
        {evidence.claims.map((claim) => <li key={claim.text}>{claim.text}
          {" "}<small className="muted">{claim.evidence_ids.join(" · ")}</small></li>)}
      </ul>
      <details><summary>Metric evidence paths</summary>
        <dl className={styles.facts}>
          {evidence.packet.metrics.map((row) => <div key={row.id}><dt>{row.id} · {row.label}</dt>
            <dd><code>{row.path}</code></dd></div>)}
        </dl>
      </details>
      {available && <div className={styles.reportActions}>
        <button className="button" type="button" disabled={busy} onClick={requestNarration}>
          {busy ? "Preparing wording…" : "Request AI wording"}
        </button>
        <span className="muted" role="status">{message}</span>
      </div>}
    </> : <p className="muted" role="status">{failed ? "Evidence packet unavailable. The report shows the saved audited metrics." : "Loading evidence…"}</p>}
  </section>;
}

function PrintReport({ report, exportPath }: { report: Report; exportPath: string }) {
  const { result, plan, dataset } = report;
  const m = result.metrics;
  const selected = result.selected_candidate_ids.map((id) => dataset.sites.find((site) => site.id === id)?.label ?? id);
  return (
    <>
      <div className={styles.reportActions}>
        <a className="button primary" href={exportPath + "?format=json"} download>Download JSON</a>
        <a className="button" href={exportPath + "?format=csv"} download>Download CSV</a>
        <button className="button" type="button" onClick={() => window.print()}>Print report</button>
      </div>
      <div className="notice" role="note">{report.data_warning}</div>
      <section className={"panel " + styles.section}>
        <h2>Executive summary</h2>
        <p className={styles.datasetTag}><span className="badge">{dataType(dataset)}</span>
          {" "}{dataset.district_label} · {dataset.version} · {runKind(result.kind)}</p>
        <ResultStatus result={result} />
        <p>
          In one modeled week, this allocation serves {integer(m.served_visits)} of {integer(m.total_demand)} requested
          visits. {integer(m.covered_visits)} visits are assigned within {plan.threshold_minutes} minutes
          ({percent(m.coverage_pct)} of demand). {integer(m.unmet_visits)} visits remain unmet.
          Additional weekly planning cost is {money(m.cost_pkr)}.
        </p>
        <p className="muted">Selected candidate sites {selected.join(", ") || "None"}.</p>
        {result.warnings.map((warning) => <p key={warning} role="note" className="notice">{warning}</p>)}
      </section>
      <Evidence key={result.run_id} runId={result.run_id} />
      <div className={styles.twoColumns}>
        <section className={"panel " + styles.section}>
          <h2>Verified metrics</h2>
          <dl className={styles.facts}>
            <div><dt>Within-threshold coverage</dt><dd>{percent(m.coverage_pct)}</dd></div>
            <div><dt>Weekly visits served</dt><dd>{integer(m.served_visits)} ({percent(m.served_rate_pct)})</dd></div>
            <div><dt>Weekly unmet demand</dt><dd>{integer(m.unmet_visits)} ({percent(m.unmet_rate_pct)})</dd></div>
            <div><dt>Mean assigned travel, served visits</dt><dd>{minutes(m.mean_assigned_travel_minutes)}</dd></div>
            <div><dt>Worst cluster</dt><dd>{m.worst_cluster_id} · {percent(m.worst_cluster_coverage_pct)}</dd></div>
            <div><dt>Equity gap</dt><dd>{decimal(m.equity_gap_pp)} pp</dd></div>
            <div><dt>Additional weekly cost</dt><dd>{money(m.cost_pkr)}</dd></div>
            <div><dt>Budget utilization</dt><dd>{percent(m.budget_utilization_pct)}</dd></div>
          </dl>
        </section>
        <section className={"panel " + styles.section}>
          <h2>Confirmed assumptions</h2>
          <PlanAssumptions plan={plan} />
        </section>
      </div>
      <section className={"panel " + styles.section}>
        <h2>Independent constraints and solver evidence</h2>
        <AuditDetails result={result} defaultOpen />
        <SolverDetails result={result} />
      </section>
      <section className={"panel " + styles.section}>
        <h2>Provenance and limitations</h2>
        <p>{dataset.model_scope}</p>
        <ul className={styles.bullets}>{dataset.assumptions.map((assumption, i) => <li key={i}>{assumption}</li>)}</ul>
        <p>Rates use weekly visits. Coverage includes unmet demand in its denominator. The equity gap represents the range of coverage across positive-demand clusters.</p>
        <dl className={styles.hashes}>
          <div><dt>Run ID</dt><dd><code>{result.run_id}</code></dd></div>
          <div><dt>Model version</dt><dd>{result.model_version}</dd></div>
          <div><dt>Source date</dt><dd>{dataset.source_date}</dd></div>
          <div><dt>Dataset license</dt><dd>{dataset.license}</dd></div>
          <div><dt>Dataset SHA-256</dt><dd><code>{result.dataset_sha256}</code></dd></div>
          <div><dt>Plan SHA-256</dt><dd><code>{result.plan_hash}</code></dd></div>
          <div><dt>Audit SHA-256</dt><dd><code>{result.audit.result_hash}</code></dd></div>
        </dl>
        <details>
          <summary>Source manifest</summary>
          <div className={styles.scroll} tabIndex={0} role="region" aria-label="Dataset provenance">
            <table className={styles.table}>
              <caption className={styles.srOnly}>Provenance for modeled inputs</caption>
              <thead><tr><th scope="col">Field</th><th scope="col">Source</th><th scope="col">Caveat</th></tr></thead>
              <tbody>{dataset.provenance.map((row, i) => (
                <tr key={i}><th scope="row">{row.entity}.{row.field}</th>
                  <td>{row.source} ({row.method})</td><td>{row.caveat}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      </section>
    </>
  );
}

export function PlanningReport({ runId }: { runId: string }) {
  const [loaded, setLoaded] = useState<{ key: string; report: Report } | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const runPath = "/runs/" + encodeURIComponent(runId);
  const exportPath = runPath + "/export";
  const key = JSON.stringify([runId, attempt]);
  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    api<RunSnapshot>(runPath, options)
      .then((snapshot) => {
        if (snapshot.status !== "COMPLETED") {
          throw new Error(snapshot.error?.message ?? "A printable report requires a completed audited run.");
        }
        return api<Report>(exportPath + "?format=json", options);
      })
      .then((report) => {
        if (!controller.signal.aborted) setLoaded({ key, report });
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setFailure({ key, message: err instanceof Error ? err.message : "The report is unavailable." });
      });
    return () => controller.abort();
  }, [exportPath, key, runPath]);
  const report = loaded?.key === key ? loaded.report : null;
  const error = failure?.key === key ? failure.message : null;
  return (
    <article className={"stack " + styles.report}>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Verified evidence</p>
          <h1>Planning report</h1>
          <p className="muted">Allocation, constraints, and provenance for a saved planning run.</p>
        </div>
      </header>
      {report ? <PrintReport report={report} exportPath={"/api/v1" + exportPath} /> : error ? (
        <div className={"panel " + styles.section} role="alert">
          <h2>Report unavailable</h2><p>{error}</p>
          <button className="button" type="button" onClick={() => setAttempt(attempt + 1)}>Retry report</button>
          {" "}<Link className="button" href={runPath}>View run</Link>
        </div>
      ) : <p className="muted" role="status">Loading report…</p>}
    </article>
  );
}
