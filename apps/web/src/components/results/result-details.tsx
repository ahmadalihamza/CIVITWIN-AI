import type { Dataset, PlanSpec, Result } from "@/lib/types";

import styles from "./results.module.css";

const wholeNumber = new Intl.NumberFormat("en-PK");
const decimalNumber = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 1 });

export function integer(value: number): string {
  return wholeNumber.format(value);
}

export function decimal(value: number): string {
  return decimalNumber.format(value);
}

export function percent(value: number | null): string {
  return value === null ? "Unavailable" : decimal(value) + "%";
}

export function minutes(value: number | null): string {
  return value === null ? "Unavailable" : decimal(value) + " min";
}

export function money(value: number): string {
  return "PKR " + integer(value);
}

export function dataType(dataset: Pick<Dataset, "is_synthetic">): string {
  return dataset.is_synthetic ? "Synthetic demonstration" : "Aggregate planning dataset";
}

export function runKind(kind: Result["kind"]): string {
  if (kind === "baseline") return "Modeled baseline";
  if (kind === "greedy") return "Greedy alternative";
  return "Optimized alternative";
}

function auditValue(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function ResultStatus({ result }: { result: Result }) {
  return (
    <ul className={styles.statusList} aria-label="Solver and audit status">
      <li><span>Solver</span> <strong>{result.solver_status}</strong></li>
      <li><span>Independent audit</span> <strong>{result.audit.passed ? "Passed" : "Failed"}</strong></li>
      <li><span>Runtime</span> <strong>{integer(result.runtime_ms)} ms</strong></li>
    </ul>
  );
}

export function PlanAssumptions({ plan }: { plan: PlanSpec }) {
  return (
    <dl className={styles.facts}>
      <div><dt>Time horizon</dt><dd>One modeled week</dd></div>
      <div><dt>Coverage threshold</dt><dd>{plan.threshold_minutes} min</dd></div>
      <div><dt>Budget</dt><dd>{money(plan.budget_pkr)}/week</dd></div>
      <div><dt>Maximum new units</dt><dd>{plan.max_new_units}</dd></div>
      <div><dt>Demand multiplier</dt><dd>{plan.demand_multiplier_pct}%</dd></div>
      <div><dt>Equity floor</dt><dd>{plan.equity_min_pct}% per cluster</dd></div>
      <div><dt>Planning policy</dt><dd>{plan.policy.replaceAll("_", " ")}</dd></div>
      <div><dt>Solver seed</dt><dd>{integer(plan.seed)}</dd></div>
    </dl>
  );
}

export function AuditDetails({ result, defaultOpen = false }: { result: Result; defaultOpen?: boolean }) {
  return (
    <details className={styles.audit} open={defaultOpen || undefined}>
      <summary>
        <strong>{result.audit.passed ? "Audit passed" : "Audit failed"}</strong>
        {" · "}{result.audit.checks.length} checks
      </summary>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="Constraint audit">
        <table className={styles.table}>
          <caption className={styles.srOnly}>Independent constraint checks</caption>
          <thead><tr><th scope="col">Check</th><th scope="col">Status</th><th scope="col">Details</th></tr></thead>
          <tbody>{result.audit.checks.map((check) => (
            <tr key={check.id}>
              <th scope="row">{check.id.replaceAll("_", " ").toLowerCase()}</th>
              <td>{check.passed ? "Pass" : "Fail"}</td>
              <td>
                <details>
                  <summary>Expected and actual</summary>
                  <dl className={styles.checkValues}>
                    <dt>Expected</dt><dd><code>{auditValue(check.expected)}</code></dd>
                    <dt>Actual</dt><dd><code>{auditValue(check.actual)}</code></dd>
                  </dl>
                </details>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </details>
  );
}

export function SolverDetails({ result }: { result: Result }) {
  const solver = result.solver_settings;
  return (
    <>
      <p className="muted">
        OR-Tools CP-SAT {solver.solver_version} · {solver.worker_count} worker{solver.worker_count === 1 ? "" : "s"} ·{" "}
        {solver.time_limit_seconds}s solve limit
      </p>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="Solver objective stages">
        <table className={styles.table}>
          <caption className={styles.srOnly}>Lexicographic objective stages</caption>
          <thead>
            <tr><th scope="col">Objective</th><th scope="col">Direction</th><th scope="col">Status</th>
              <th scope="col">Value</th><th scope="col">Bound</th></tr>
          </thead>
          <tbody>{result.objective_stages.map((stage) => (
            <tr key={stage.objective}>
              <th scope="row">{stage.objective.replaceAll("_", " ")}</th>
              <td>{stage.direction}</td><td>{stage.status}</td>
              <td>{stage.value === null ? "—" : integer(stage.value)}</td>
              <td>{stage.best_bound === null ? "—" : decimal(stage.best_bound)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
