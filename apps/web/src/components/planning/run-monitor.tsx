"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage, formatNumber, post } from "@/lib/api";
import type { DatasetManifest, RunSnapshot, Scenario } from "@/lib/types";
import { PlanAssumptions } from "./assumptions";
import styles from "./planning.module.css";

const activeStatuses = new Set<RunSnapshot["status"]>(["QUEUED", "RUNNING", "AUDITING"]);
const stages: Record<string, string> = {
  QUEUED: "Waiting for the planner",
  RUNNING: "Preparing the problem",
  covered_visits: "Maximizing visits covered",
  served_visits: "Maximizing visits served",
  equity_basis_points: "Improving worst-cluster coverage",
  assigned_travel_visit_minutes: "Minimizing assigned travel",
  cost_pkr: "Minimizing activation cost",
  AUDITING: "Verifying the allocation independently",
  COMPLETED: "Completed",
  NO_SOLUTION: "No feasible allocation",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
  TIMED_OUT: "Timed out",
  INTERRUPTED: "Interrupted",
};

function isActive(run: RunSnapshot) {
  return activeStatuses.has(run.status);
}

function elapsed(run: RunSnapshot, now: number) {
  if (run.runtime_ms !== null) return run.runtime_ms;
  const start = new Date(run.started_at ?? run.created_at).getTime();
  const end = run.completed_at ? new Date(run.completed_at).getTime() : now;
  return Math.max(0, end - start);
}

export function RunMonitor({ runId, baselineId }: { runId: string; baselineId?: string }) {
  const router = useRouter();
  const [run, setRun] = useState<RunSnapshot>();
  const [scenario, setScenario] = useState<Scenario>();
  const [dataset, setDataset] = useState<DatasetManifest>();
  const [sibling, setSibling] = useState<RunSnapshot>();
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [contextError, setContextError] = useState("");
  const [action, setAction] = useState<"cancel" | "start">();
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(0);
  const acting = useRef(false);
  const path = `/runs/${encodeURIComponent(runId)}`;

  useEffect(() => {
    let next: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;
    const controller = new AbortController();

    async function poll() {
      try {
        const latest = await api<RunSnapshot>(path, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setRun(latest);
        setNow(Date.now());
        setError("");
        retryDelay = 1000;
        if (isActive(latest)) next = setTimeout(poll, 1000);
      } catch (problem) {
        if (controller.signal.aborted) return;
        setError(errorMessage(problem));
        if (!(problem instanceof ApiError) || problem.status !== 404) {
          retryDelay = Math.min(retryDelay * 2, 5000);
          next = setTimeout(poll, retryDelay);
        }
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(next);
    };
  }, [path, refresh]);

  const scenarioId = run?.scenario_id;
  const shouldFindSibling = Boolean(run && !isActive(run));
  const kind = run?.kind;
  useEffect(() => {
    if (!scenarioId) return;
    const controller = new AbortController();
    const request = { signal: controller.signal };

    async function loadContext(id: string) {
      try {
        const [loadedScenario, datasets] = await Promise.all([
          api<Scenario>(`/scenarios/${encodeURIComponent(id)}`, request),
          api<DatasetManifest[]>("/datasets", request),
        ]);
        if (controller.signal.aborted) return;
        setScenario(loadedScenario);
        setDataset(datasets.find((item) => item.id === loadedScenario.plan.dataset_version_id));
        setContextError("");
      } catch (problem) {
        if (!controller.signal.aborted) setContextError(errorMessage(problem));
      }
    }

    void loadContext(scenarioId);
    return () => controller.abort();
  }, [scenarioId, refresh]);

  useEffect(() => {
    if (!shouldFindSibling || !scenarioId) return;
    const controller = new AbortController();
    const options = { signal: controller.signal };

    async function findSibling() {
      try {
        const preferred = kind !== "baseline" && baselineId
          ? await api<RunSnapshot>(`/runs/${encodeURIComponent(baselineId)}`, options)
            .catch(() => undefined)
          : undefined;
        if (controller.signal.aborted) return;
        if (preferred && preferred.scenario_id === scenarioId && preferred.kind === "baseline") {
          setSibling(preferred);
          return;
        }
        const history = await api<RunSnapshot[]>("/runs", options);
        if (controller.signal.aborted) return;
        const others = history.filter((item) => item.scenario_id === scenarioId &&
          item.run_id !== runId && item.kind === (kind === "baseline" ? "optimized" : "baseline"));
        setSibling(others.find((item) => item.status === "COMPLETED") ?? others[0]);
      } catch (problem) {
        if (!controller.signal.aborted) setContextError(errorMessage(problem));
      }
    }
    void findSibling();
    return () => controller.abort();
  }, [baselineId, kind, runId, scenarioId, shouldFindSibling, refresh]);

  async function cancel() {
    if (acting.current) return;
    acting.current = true;
    setAction("cancel");
    setActionError("");
    try {
      const cancelled = await post<RunSnapshot>(`${path}/cancel`);
      setRun(cancelled);
      setNow(Date.now());
      setRefresh((count) => count + 1);
    } catch (problem) {
      setActionError(errorMessage(problem));
      setRefresh((count) => count + 1);
    } finally {
      acting.current = false;
      setAction(undefined);
    }
  }

  async function start(kindToStart: RunSnapshot["kind"], retry: boolean) {
    if (!run || acting.current) return;
    acting.current = true;
    setAction("start");
    setActionError("");
    try {
      const key = retry ? `${run.run_id}:retry` : `${run.scenario_id}:${kindToStart}`;
      const { run_id } = await post<{ run_id: string }>(
        `/scenarios/${encodeURIComponent(run.scenario_id)}/runs`, { kind: kindToStart }, key,
      );
      const baseline = kindToStart === "baseline" ? undefined
        : run.kind === "baseline" ? run.run_id : sibling?.run_id ?? baselineId;
      const params = baseline ? `?baseline=${encodeURIComponent(baseline)}` : "";
      router.push(`/runs/${encodeURIComponent(run_id)}${params}`);
    } catch (problem) {
      setActionError(errorMessage(problem));
      acting.current = false;
      setAction(undefined);
    }
  }

  const title = run?.kind === "baseline" ? "Baseline run"
    : run?.kind === "greedy" ? "Greedy run" : run ? "Optimized run" : "Run status";
  const baseline = run?.kind === "baseline" ? run : sibling;
  const alternative = run?.kind === "baseline" ? sibling : run;
  const comparison = baseline?.status === "COMPLETED" && alternative?.status === "COMPLETED"
    ? `/compare?baseline=${encodeURIComponent(baseline.run_id)}&alternative=${encodeURIComponent(alternative.run_id)}`
    : undefined;

  return (
    <div className="stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Scenario planning</p>
          <h1>{title}</h1>
          <p className="muted">
            {run?.kind === "baseline" ? "Evaluate existing sites under the confirmed plan."
              : "Follow the persisted solve and independent audit."}
          </p>
        </div>
      </header>

      {error && (
        <div className="notice" role="alert">
          <p>{error}</p>
          <div className={styles.actions}>
            <button className="button" type="button" onClick={() => {
              setError("");
              setRefresh((count) => count + 1);
            }}>Refresh status</button>
            <Link className="button" href="/scenarios/new">Start a new scenario</Link>
          </div>
        </div>
      )}
      {!run && !error && <p className="notice" role="status">Loading saved run…</p>}
      {run && (
        <div className={styles.columns}>
          <section className={`panel ${styles.content}`} aria-label="Run progress">
            <div className={styles.status}>
              <h2>Run progress</h2>
              <span className="badge">{run.status.replaceAll("_", " ")}</span>
            </div>
            <p className={styles.stage} aria-live="polite">{stages[run.progress_stage] ?? run.progress_stage}</p>
            <p className="muted">Elapsed {(elapsed(run, now) / 1000).toFixed(1)} seconds</p>
            <ol className={styles.steps}>
              <li>
                <span>Plan confirmed</span>
                <span className={styles.completed}>Complete</span>
              </li>
              <li aria-current={run.status === "QUEUED" || run.status === "RUNNING" ? "step" : undefined}>
                <span>Allocate modeled visits</span>
                <span>{run.status === "COMPLETED" || run.status === "AUDITING" ? "Complete"
                  : isActive(run) ? "In progress" : "Ended"}</span>
              </li>
              <li aria-current={run.status === "AUDITING" ? "step" : undefined}>
                <span>Verify constraints and metrics</span>
                <span className={run.result?.audit.passed ? styles.completed : undefined}>
                  {run.result?.audit.passed ? "Audit passed" : run.status === "AUDITING" ? "In progress"
                    : isActive(run) ? "Pending" : "No published allocation"}
                </span>
              </li>
            </ol>
            {run.solver_status && <p>Solver status <strong>{run.solver_status}</strong></p>}
            {run.result && (
              <p>
                <strong>{formatNumber(run.result.metrics.covered_visits)}</strong> of{" "}
                {formatNumber(run.result.metrics.total_demand)} modeled visits fall within the coverage threshold.
              </p>
            )}
            {run.result?.warnings.map((warning) => <p key={warning} className="notice">{warning}</p>)}
            {run.kind !== "baseline" && run.result && sibling && !isActive(sibling) && sibling.status !== "COMPLETED" && (
              <p className="notice">Comparison requires an audited baseline.{" "}
                <Link href={`/runs/${encodeURIComponent(sibling.run_id)}`}>View baseline status</Link>.
              </p>
            )}
            {run.error && <p className="notice" role="alert">{run.error.message}</p>}
            {actionError && <p className="notice" role="alert">{actionError}</p>}
            <div className={styles.actions}>
              {isActive(run) ? (
                <button className="button" type="button" onClick={cancel} disabled={Boolean(action)}>
                  {action === "cancel" ? "Cancelling…" : "Cancel run"}
                </button>
              ) : (
                <>
                  {comparison && <Link className="button primary" href={comparison}>Compare results</Link>}
                  {run.kind === "baseline" && !comparison && (sibling?.kind === "optimized" ? (
                    <Link className="button primary" href={`/runs/${encodeURIComponent(sibling.run_id)}?baseline=${encodeURIComponent(runId)}`}>
                      Open optimized run
                    </Link>
                  ) : (
                    <button className="button primary" type="button" onClick={() => start("optimized", false)} disabled={Boolean(action)}>
                      {action === "start" ? "Starting run…" : "Run optimized plan"}
                    </button>
                  ))}
                  {run.kind === "baseline" && run.result && <button className="button" type="button"
                    onClick={() => start("greedy", false)} disabled={Boolean(action)}>Run greedy benchmark</button>}
                  {run.result && <Link className="button" href={`/reports/${encodeURIComponent(runId)}`}>Open report</Link>}
                  {!run.result && (
                    <button className="button" type="button" onClick={() => start(run.kind, true)} disabled={Boolean(action)}>
                      Retry run
                    </button>
                  )}
                  <Link className="button" href={`/scenarios/new?draft=${encodeURIComponent(run.scenario_id)}`}>Review scenario</Link>
                  <Link className="button" href="/scenarios/new">New scenario</Link>
                </>
              )}
            </div>
          </section>
          <aside className={`panel ${styles.content}`} aria-label="Confirmed scenario">
            <p className="eyebrow">Confirmed scenario</p>
            <h2>{dataset?.district_label ?? "Planning assumptions"}</h2>
            {dataset && (
              <>
                <span className="badge">{dataset.is_synthetic ? "Synthetic demonstration" : "Aggregate dataset"}</span>
                <p className="muted">Version {dataset.version} · One modeled week</p>
              </>
            )}
            {scenario ? (
              <>
                <PlanAssumptions plan={scenario.plan} />
                <p className="muted">Confirmed plan hash</p>
                <p className={styles.hash}>{scenario.plan_hash}</p>
              </>
            ) : !contextError && <p className="muted" role="status">Loading confirmed assumptions…</p>}
            {contextError && (
              <div className="notice" role="alert">
                <p>{contextError}</p>
                <button className="button" type="button" onClick={() => {
                  setContextError("");
                  setRefresh((count) => count + 1);
                }}>Reload context</button>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
