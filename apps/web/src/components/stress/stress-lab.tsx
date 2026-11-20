"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Loading, useData } from "@/components/load";
import { PlanAssumptions, integer, minutes, percent, runKind } from "@/components/results/result-details";
import { api, ApiError, errorMessage, formatDate, post } from "@/lib/api";
import type { RunSnapshot, Scenario } from "@/lib/types";

import styles from "./stress.module.css";

type Observation = {
  status: string;
  solver_status: string | null;
  audit_passed: boolean | null;
  covered_visits: number | null;
  coverage_pct: number | null;
  unmet_rate_pct: number | null;
  worst_cluster_coverage_pct: number | null;
  mean_assigned_travel_minutes: number | null;
};

type Interval = Record<"min" | "max" | "median" | "p10" | "p90", number>;
type Metric = "coverage_pct" | "unmet_rate_pct" | "worst_cluster_coverage_pct" |
  "mean_assigned_travel_minutes";
type Summary = Record<Metric, Interval | null> & {
  successful_cases: number;
  failed_cases: number;
  excluded_cases: number;
  failure_rate_pct: number;
};
type StressResults = {
  seed: number;
  case_count: number;
  cases: {
    case_number: number;
    demand_multiplier_pct: number;
    travel_multiplier_pct: number;
    baseline: Observation;
    alternative: Observation;
  }[];
  baseline: Summary;
  alternative: Summary;
  paired_success_count: number;
  runtime_ms: number;
};
type StressSnapshot = {
  stress_run_id: string;
  status: string;
  progress_stage: string;
  seed: number;
  case_count: number;
  baseline_run_id: string;
  alternative_run_id: string;
  results?: StressResults;
  error?: { code: string; message: string };
};

const activeStatuses = new Set(["QUEUED", "RUNNING", "AUDITING"]);
const metrics: { key: Metric; label: string; format: (value: number | null) => string }[] = [
  { key: "coverage_pct", label: "Within-threshold coverage", format: percent },
  { key: "unmet_rate_pct", label: "Unmet demand rate", format: percent },
  { key: "worst_cluster_coverage_pct", label: "Worst cluster coverage", format: percent },
  { key: "mean_assigned_travel_minutes", label: "Mean assigned travel", format: minutes },
];

function statusLabel(status: string) {
  return status.replaceAll("_", " ").toLowerCase();
}

function stressURL(baselineId: string, alternativeId: string, stressId?: string) {
  const query = new URLSearchParams({ baseline: baselineId, alternative: alternativeId });
  if (stressId) query.set("run", stressId);
  return "/stress?" + query.toString();
}

function StressForm({ initialBaseline, initialAlternative }: {
  initialBaseline?: string;
  initialAlternative?: string;
}) {
  const router = useRouter();
  const history = useData<RunSnapshot[]>("/runs");
  const [baseline, setBaseline] = useState(initialBaseline ?? "");
  const [alternative, setAlternative] = useState(initialAlternative ?? "");
  const [seed, setSeed] = useState("2026");
  const [cases, setCases] = useState("20");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const submission = useRef<{ key: string; fingerprint: string } | null>(null);
  const inFlight = useRef(false);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    const body = {
      baseline_run_id: baseline,
      alternative_run_id: alternative,
      seed: Number(seed),
      case_count: Number(cases),
    };
    const fingerprint = JSON.stringify(body);
    if (submission.current?.fingerprint !== fingerprint) {
      submission.current = { key: "stress-" + crypto.randomUUID(), fingerprint };
    }
    inFlight.current = true;
    setSubmitting(true);
    setError("");
    try {
      const result = await post<{ stress_run_id: string }>("/stress-runs", body, submission.current.key);
      router.push(stressURL(baseline, alternative, result.stress_run_id));
    } catch (problem) {
      inFlight.current = false;
      setSubmitting(false);
      setError(errorMessage(problem));
    }
  }

  if (!history.data) return <Loading error={history.error} retry={history.retry} />;
  const complete = history.data.filter((run) => run.status === "COMPLETED");
  const baselineRuns = complete.filter((run) => run.kind === "baseline");
  const alternativeRuns = complete.filter((run) => run.kind !== "baseline");
  if (!(baselineRuns.length || initialBaseline) || !(alternativeRuns.length || initialAlternative)) {
    return <section className={"panel " + styles.section}>
      <h2>Choose a saved allocation pair</h2>
      <p className="muted">Complete a baseline and an alternative under the same confirmed plan to test their sensitivity.</p>
      <Link className="button primary" href="/scenarios/new">Start a scenario</Link>
    </section>;
  }

  return <section className={"panel " + styles.section}>
    <h2>Stress assumptions</h2>
    <p className="muted">
      Each case changes demand by a multiplier of 80% to 130% and travel cost by 90% to 140%.
      Both allocations use the same cases and keep their selected sites fixed.
    </p>
    <form className={styles.form} onSubmit={start}>
      <label>Modeled baseline
        <select required value={baseline} onChange={(event) => setBaseline(event.target.value)}>
          <option value="" disabled>Select a baseline</option>
          {initialBaseline && !baselineRuns.some((row) => row.run_id === initialBaseline)
            && <option value={initialBaseline}>Linked baseline · {initialBaseline.slice(4, 12)}</option>}
          {baselineRuns.map((run) => <RunOption key={run.run_id} run={run} />)}
        </select>
      </label>
      <label>Alternative allocation
        <select required value={alternative} onChange={(event) => setAlternative(event.target.value)}>
          <option value="" disabled>Select an alternative</option>
          {initialAlternative && !alternativeRuns.some((row) => row.run_id === initialAlternative)
            && <option value={initialAlternative}>Linked alternative · {initialAlternative.slice(4, 12)}</option>}
          {alternativeRuns.map((run) => <RunOption key={run.run_id} run={run} />)}
        </select>
      </label>
      <label>Stress seed<input type="number" required min={0} max={2_147_483_647} step={1}
        value={seed} onChange={(event) => setSeed(event.target.value)} /></label>
      <label>Case count<input type="number" required min={1} max={20} step={1}
        value={cases} onChange={(event) => setCases(event.target.value)} /></label>
      <div className={styles.formFull}>
        <button className="button primary" disabled={submitting} type="submit">
          {submitting ? "Queueing stress test…" : "Run stress test"}
        </button>
      </div>
    </form>
    {error && <p className="notice" role="alert">{error}</p>}
  </section>;
}

function RunOption({ run }: { run: RunSnapshot }) {
  return <option value={run.run_id}>{runKind(run.kind)} · {formatDate(run.created_at)} · {run.run_id.slice(4, 12)}</option>;
}

function StressContext({ baselineId, alternativeId }: { baselineId: string; alternativeId: string }) {
  const baseline = useData<RunSnapshot>("/runs/" + encodeURIComponent(baselineId));
  const alternative = useData<RunSnapshot>("/runs/" + encodeURIComponent(alternativeId));
  return <section className={"panel " + styles.section}>
    <h2>Fixed allocations and confirmed assumptions</h2>
    <dl className={styles.sources}>
      {[{ state: baseline, id: baselineId, title: "Modeled baseline" },
        { state: alternative, id: alternativeId, title: "Alternative allocation" }].map(({ state, id, title }) =>
        <div key={title}><dt>{title}</dt><dd>
          <Link href={"/runs/" + encodeURIComponent(id)}>View saved run</Link>
          {state.data?.result && <span> · Candidate sites {state.data.result.selected_candidate_ids.join(", ") || "None"}</span>}
        </dd></div>,
      )}
    </dl>
    {baseline.data && <StressPlan scenarioId={baseline.data.scenario_id} />}
  </section>;
}

function StressPlan({ scenarioId }: { scenarioId: string }) {
  const { data, error, retry } = useData<Scenario>("/scenarios/" + encodeURIComponent(scenarioId));
  return data ? <PlanAssumptions plan={data.plan} /> : <Loading error={error} retry={retry} />;
}

function CoverageInterval({ label, interval }: { label: string; interval: Interval | null }) {
  return <div className={styles.coverageRow}>
    <strong>{label}</strong>
    {interval ? <>
      <div className={styles.track} aria-hidden="true">
        <div className={styles.range} style={{ left: interval.p10 + "%", width: Math.max(0.6, interval.p90 - interval.p10) + "%" }} />
        <div className={styles.median} style={{ left: interval.median + "%" }} />
      </div>
      <p className="muted">P10 {percent(interval.p10)} · Median {percent(interval.median)} · P90 {percent(interval.p90)}</p>
    </> : <p className="muted">No audited cases available.</p>}
  </div>;
}

function CaseOutcome({ observation }: { observation: Observation }) {
  return <>
    <strong>{observation.coverage_pct === null ? statusLabel(observation.status) : percent(observation.coverage_pct)}</strong>
    <span className={styles.caseDetail}>
      {observation.covered_visits === null ? "" : integer(observation.covered_visits) + " covered visits · "}
      {observation.solver_status ?? "Solver status unavailable"} · {observation.audit_passed ? "Audit passed" : "No passed audit"}
    </span>
    {observation.unmet_rate_pct !== null && <span className={styles.caseDetail}>
      Unmet {percent(observation.unmet_rate_pct)} · Worst cluster {percent(observation.worst_cluster_coverage_pct)} · Travel {minutes(observation.mean_assigned_travel_minutes)}
    </span>}
  </>;
}

function StressSummary({ results }: { results: StressResults }) {
  const sides = [
    { name: "Modeled baseline", key: "baseline", metrics: results.baseline },
    { name: "Alternative allocation", key: "alternative", metrics: results.alternative },
  ];
  return <>
    <section className={"panel " + styles.section}>
      <h2>Coverage across scenarios</h2>
      <p className="muted">
        P10 to P90 across audited cases, with the median marked. These ranges describe the tested assumptions.
      </p>
      <div className={styles.intervals}>
        {sides.map((side) => <CoverageInterval key={side.key} label={side.name} interval={side.metrics.coverage_pct} />)}
      </div>
      <p><strong>{results.paired_success_count} of {results.case_count}</strong> cases succeeded for both allocations.</p>
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Stress summary metrics">
        <table><caption className="sr-only">Distribution across successful audited cases</caption>
          <thead><tr><th scope="col">Allocation and metric</th><th scope="col">Min</th><th scope="col">P10</th>
            <th scope="col">Median</th><th scope="col">P90</th><th scope="col">Max</th></tr></thead>
          {sides.map((side) => <tbody key={side.key}>
            <tr><th scope="rowgroup" colSpan={6}>{side.name} · {side.metrics.failed_cases} failed · {side.metrics.excluded_cases} excluded · {percent(side.metrics.failure_rate_pct)} failure rate</th></tr>
            {metrics.map((metric) => <tr key={metric.key}>
              <th scope="row">{metric.label}</th>
              {(["min", "p10", "median", "p90", "max"] as const).map((point) =>
                <td key={point}>{metric.format(side.metrics[metric.key]?.[point] ?? null)}</td>,
              )}
            </tr>)}
          </tbody>)}
        </table>
      </div>
    </section>
    <section className={"panel " + styles.section}>
      <h2>Paired case results</h2>
      <p className="muted">Case multipliers apply to modeled demand and shortest-path travel costs. Failed cases are excluded from the distributions.</p>
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Paired stress case results">
        <table className={styles.cases}><caption className="sr-only">Stress outcomes by scenario and allocation</caption>
          <thead><tr><th scope="col">Case</th><th scope="col">Demand</th><th scope="col">Travel</th>
            <th scope="col">Modeled baseline</th><th scope="col">Alternative allocation</th></tr></thead>
          <tbody>{results.cases.map((row) => <tr key={row.case_number}>
            <th scope="row">{row.case_number}</th><td>{row.demand_multiplier_pct}%</td><td>{row.travel_multiplier_pct}%</td>
            <td><CaseOutcome observation={row.baseline} /></td><td><CaseOutcome observation={row.alternative} /></td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  </>;
}

function StressRun({ id }: { id: string }) {
  const [snapshot, setSnapshot] = useState<StressSnapshot>();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let next: ReturnType<typeof setTimeout>;
    let delay = 1000;
    const controller = new AbortController();
    async function poll() {
      try {
        const result = await api<StressSnapshot>("/stress-runs/" + encodeURIComponent(id),
          { signal: controller.signal });
        if (controller.signal.aborted) return;
        setSnapshot(result);
        setError("");
        delay = 1000;
        if (activeStatuses.has(result.status)) next = setTimeout(poll, delay);
      } catch (problem) {
        if (controller.signal.aborted) return;
        setError(errorMessage(problem));
        if (!(problem instanceof ApiError) || problem.status !== 404) {
          delay = Math.min(delay * 2, 5000);
          next = setTimeout(poll, delay);
        }
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(next);
    };
  }, [id, attempt]);

  const retry = () => { setError(""); setAttempt((value) => value + 1); };
  if (!snapshot) return <Loading error={error} retry={retry} />;
  return <>
    <section className={"panel " + styles.section}>
      <div className={styles.heading}>
        <h2>Stress run status</h2><span className="badge">{statusLabel(snapshot.status)}</span>
      </div>
      <p role="status">
        {activeStatuses.has(snapshot.status) ? (snapshot.status === "QUEUED" ? "Waiting for the planner."
          : "Reassigning visits in paired stress cases.") : <>Stress run {statusLabel(snapshot.status)}.</>}
      </p>
      <p className="muted">Seed {integer(snapshot.seed)} · {snapshot.case_count} cases
        {snapshot.results && <> · {integer(snapshot.results.runtime_ms)} ms</>}</p>
      {snapshot.error && <p role="alert" className="notice">{snapshot.error.message}</p>}
      {error && <Loading error={error} retry={retry} />}
      <div className={styles.actions}>
        <Link className="button" href={stressURL(snapshot.baseline_run_id, snapshot.alternative_run_id)}>New stress test</Link>
        <Link className="button" href={"/compare?" + new URLSearchParams({
          baseline: snapshot.baseline_run_id, alternative: snapshot.alternative_run_id,
        }).toString()}>Back to comparison</Link>
      </div>
    </section>
    {snapshot.results && <StressSummary results={snapshot.results} />}
    <StressContext baselineId={snapshot.baseline_run_id} alternativeId={snapshot.alternative_run_id} />
  </>;
}

export function StressLab({ baselineId, alternativeId, stressId }: {
  baselineId?: string;
  alternativeId?: string;
  stressId?: string;
}) {
  return <div className="stack">
    <header className="page-heading"><div>
      <p className="eyebrow">Sensitivity analysis</p>
      <h1>Stress Lab</h1>
      <p className="muted">Test whether audited allocations hold up under changes in modeled demand and travel times.</p>
    </div></header>
    {stressId ? <StressRun id={stressId} /> :
      <StressForm initialBaseline={baselineId} initialAlternative={alternativeId} />}
  </div>;
}
