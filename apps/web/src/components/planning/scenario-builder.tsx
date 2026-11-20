"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useData } from "@/components/load";
import { api, ApiError, errorMessage, post } from "@/lib/api";
import type { Dataset, DatasetManifest, PlanSpec, Scenario } from "@/lib/types";
import { PlanAssumptions } from "./assumptions";
import { PlanAssistant } from "./plan-assistant";
import styles from "./planning.module.css";

const defaultDataset = "demo-bajaur-v1";
const defaults: Pick<
  PlanSpec,
  "budget_pkr" | "max_new_units" | "threshold_minutes" | "demand_multiplier_pct" | "equity_min_pct" | "seed"
> = {
  budget_pkr: 300_000,
  max_new_units: 2,
  threshold_minutes: 45,
  demand_multiplier_pct: 100,
  equity_min_pct: 0,
  seed: 2026,
};

type NumberField = keyof typeof defaults;

const fields: {
  key: NumberField;
  label: string;
  help: string;
  min: number;
  max: number;
}[] = [
  {
    key: "budget_pkr",
    label: "Budget (PKR/week)",
    help: "Weekly-equivalent cost limit for new units.",
    min: 0,
    max: 100_000_000,
  },
  {
    key: "max_new_units",
    label: "Maximum new units",
    help: "One unit per eligible candidate zone.",
    min: 0,
    max: 50,
  },
  {
    key: "threshold_minutes",
    label: "Coverage threshold (minutes)",
    help: "Assigned visits at or below this travel time count as covered.",
    min: 1,
    max: 240,
  },
  {
    key: "demand_multiplier_pct",
    label: "Demand multiplier (%)",
    help: "Scales each cluster’s modeled weekly demand.",
    min: 1,
    max: 300,
  },
  {
    key: "equity_min_pct",
    label: "Equity floor (%)",
    help: "Minimum coverage required in each positive-demand cluster. Zero leaves it optional.",
    min: 0,
    max: 100,
  },
  {
    key: "seed",
    label: "Solver seed",
    help: "Preserves the seed with the scenario for reproduction.",
    min: 0,
    max: 2_147_483_647,
  },
];

function formValues(plan: Pick<PlanSpec, NumberField>): Record<NumberField, string> {
  return Object.fromEntries(fields.map(({ key }) => [key, String(plan[key])])) as Record<NumberField, string>;
}

export function ScenarioBuilder({
  datasetId,
  draftId,
}: {
  datasetId?: string;
  draftId?: string;
}) {
  const router = useRouter();
  const readiness = useData<{ ai_enabled: boolean }>("/ready");
  const [datasets, setDatasets] = useState<DatasetManifest[]>();
  const [dataset, setDataset] = useState<Dataset>();
  const [selected, setSelected] = useState("");
  const [values, setValues] = useState(() => formValues(defaults));
  const [scenario, setScenario] = useState<Scenario>();
  const [editing, setEditing] = useState(!draftId);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [datasetError, setDatasetError] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [datasetAttempt, setDatasetAttempt] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const sending = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    Promise.all([
      api<DatasetManifest[]>("/datasets", options),
      draftId
        ? api<Scenario>(`/scenarios/${encodeURIComponent(draftId)}`, options)
        : Promise.resolve(undefined),
    ])
      .then(([items, saved]) => {
        if (controller.signal.aborted) return;
        const preferred = items.find((item) => item.id === datasetId)
          ?? items.find((item) => item.id === defaultDataset)
          ?? items[0];
        setDatasets(items);
        setSelected(saved?.plan.dataset_version_id ?? preferred?.id ?? "");
        if (saved) {
          setScenario(saved);
          setValues(formValues(saved.plan));
        }
      })
      .catch((problem: unknown) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(problem));
      });
    return () => controller.abort();
  }, [datasetId, draftId, loadAttempt]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    api<Dataset>(`/datasets/${encodeURIComponent(selected)}`, { signal: controller.signal })
      .then((item) => {
        if (!controller.signal.aborted) setDataset(item);
      })
      .catch((problem: unknown) => {
        if (!controller.signal.aborted) setDatasetError(errorMessage(problem));
      });
    return () => controller.abort();
  }, [selected, datasetAttempt]);

  const selectedManifest = datasets?.find((item) => item.id === selected);
  const datasetReady = dataset?.id === selected;
  const eligibleCount = datasetReady && dataset
    ? dataset.sites.filter((site) => site.type === "candidate" && site.eligible).length
    : undefined;
  const unitLimit = Math.min(50, eligibleCount ?? 50);

  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending.current || !datasetReady) return;
    setError("");
    const invalid: Record<string, string> = {};
    const payload = { dataset_version_id: selected, policy: "coverage_first" } as PlanSpec;
    for (const { key, min, max: bound } of fields) {
      const max = key === "max_new_units" ? unitLimit : bound;
      const value = Number(values[key]);
      if (!values[key].trim() || !Number.isInteger(value) || value < min || value > max) {
        invalid[key] = `Enter a whole number from ${min.toLocaleString("en-PK")} to ${max.toLocaleString("en-PK")}.`;
      } else {
        payload[key] = value;
      }
    }
    setErrors(invalid);
    const firstInvalid = Object.keys(invalid)[0];
    if (firstInvalid) {
      document.getElementById(firstInvalid)?.focus();
      return;
    }

    sending.current = true;
    setSaving(true);
    try {
      const saved = await post<Scenario>("/scenarios", payload);
      setScenario(saved);
      setEditing(false);
      router.replace(`/scenarios/new?draft=${encodeURIComponent(saved.scenario_id)}`, { scroll: false });
    } catch (problem) {
      if (problem instanceof ApiError) {
        const messages: Record<string, string> = {};
        for (const field of problem.fields) {
          const key = String(field.field.at(-1) ?? "");
          if (key in defaults || key === "dataset_version_id") messages[key] = field.message;
        }
        setErrors(messages);
      }
      setError(errorMessage(problem));
    } finally {
      sending.current = false;
      setSaving(false);
    }
  }

  async function confirmAndRun() {
    if (sending.current || !scenario) return;
    sending.current = true;
    setSaving(true);
    setError("");
    const path = `/scenarios/${encodeURIComponent(scenario.scenario_id)}`;
    try {
      const confirmed = await post<Scenario>(`${path}/confirm`, { plan_hash: scenario.plan_hash });
      setScenario(confirmed);
      const { run_id } = await post<{ run_id: string }>(
        `${path}/runs`, { kind: "baseline" }, `${scenario.scenario_id}:baseline`,
      );
      router.push(`/runs/${encodeURIComponent(run_id)}`);
    } catch (problem) {
      setError(errorMessage(problem));
      sending.current = false;
      setSaving(false);
    }
  }

  const reviewing = scenario && !editing;

  useEffect(() => {
    if (reviewing) heading.current?.focus();
  }, [reviewing]);

  return (
    <div className="stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Scenario planning</p>
          <h1 ref={heading} tabIndex={-1}>{reviewing ? "Review scenario" : "Scenario builder"}</h1>
          <p className="muted">
            {reviewing
              ? "Check the saved assumptions before running the existing-site baseline."
              : "Set the limits and assumptions for a weekly outpatient service scenario."}
          </p>
        </div>
      </header>

      {loadError ? (
        <section className="notice" role="alert">
          <p>{loadError}</p>
          <div className={styles.actions}>
            <button className="button" onClick={() => { setLoadError(""); setLoadAttempt((count) => count + 1); }}>Retry</button>
            {draftId && <Link className="button" href="/scenarios/new">Start a new scenario</Link>}
          </div>
        </section>
      ) : !datasets ? (
        <p className="notice" role="status">Loading published datasets…</p>
      ) : !datasets.length ? (
        <p className="notice">No published datasets. Open the <Link href="/data">data explorer</Link> to import a synthetic dataset.</p>
      ) : (
        <div className={styles.columns}>
          {reviewing ? (
            <section className={`panel ${styles.content}`} aria-label="Reviewed assumptions">
              <h2>Planning assumptions</h2>
              <PlanAssumptions plan={scenario.plan} />
              <div className="notice">
                <p><strong>{scenario.status === "CONFIRMED" ? "Plan confirmed" : "Plan hash"}</strong></p>
                <p className={styles.hash}>{scenario.plan_hash}</p>
              </div>
              {scenario.plan.equity_min_pct > 0 && (
                <p className="notice">The baseline or alternative may be infeasible if a cluster cannot meet the equity floor.</p>
              )}
              {error && <p className="notice" role="alert">{error}</p>}
              <div className={styles.actions}>
                <button className="button primary" type="button" disabled={saving} onClick={confirmAndRun}>
                  {saving ? "Starting baseline…" : "Confirm & Run"}
                </button>
                <button className="button" type="button" disabled={saving} onClick={() => {
                  setError("");
                  setEditing(true);
                }}>Edit assumptions</button>
              </div>
            </section>
          ) : (
            <form className={`panel ${styles.content}`} noValidate onSubmit={review}>
              <h2>Plan parameters</h2>
              <div className={styles.field}>
                <label htmlFor="dataset_version_id">Dataset version</label>
                <select id="dataset_version_id" value={selected} aria-invalid={Boolean(errors.dataset_version_id)} aria-describedby={errors.dataset_version_id ? "dataset-version-error" : undefined} onChange={(event) => {
                  setSelected(event.target.value);
                  setDatasetError("");
                  setErrors((current) => ({ ...current, dataset_version_id: "", max_new_units: "" }));
                }}>
                  {datasets.map((item) => (
                    <option value={item.id} key={item.id}>{item.district_label} · {item.version}</option>
                  ))}
                </select>
                {errors.dataset_version_id && <small id="dataset-version-error" className={styles.error}>{errors.dataset_version_id}</small>}
              </div>
              <div className={styles.fieldGrid}>
                {fields.map(({ key, label, min, max, help }) => (
                  <div className={styles.field} key={key}>
                    <label htmlFor={key}>{label}</label>
                    <input
                      id={key}
                      name={key}
                      type="number"
                      value={values[key]}
                      min={min}
                      max={key === "max_new_units" ? unitLimit : max}
                      step={1}
                      required
                      aria-invalid={Boolean(errors[key])}
                      aria-describedby={errors[key] ? `${key}-error ${key}-help` : `${key}-help`}
                      onChange={(event) => {
                        const value = event.target.value;
                        setValues((current) => ({ ...current, [key]: value }));
                        setErrors((current) => ({ ...current, [key]: "" }));
                      }}
                    />
                    {errors[key] && <small id={`${key}-error`} className={styles.error}>{errors[key]}</small>}
                    <small id={`${key}-help`} className="muted">{help}</small>
                  </div>
                ))}
              </div>
              <div className={styles.field}>
                <label htmlFor="policy">Allocation policy</label>
                <select id="policy" defaultValue="coverage_first">
                  <option value="coverage_first">Coverage first</option>
                </select>
              </div>
              {datasetError && (
                <div className="notice" role="alert">
                  <p>{datasetError}</p>
                  <button type="button" className="button" onClick={() => {
                    setDatasetError("");
                    setDatasetAttempt((count) => count + 1);
                  }}>Retry dataset load</button>
                </div>
              )}
              {!datasetReady && !datasetError && <p className="muted" role="status">Loading the selected dataset…</p>}
              {error && <p className="notice" role="alert">{error}</p>}
              <div className={styles.actions}>
                <button className="button primary" disabled={saving || !datasetReady} type="submit">
                  {saving ? "Saving plan…" : "Review plan"}
                </button>
                {scenario && <button className="button" type="button" disabled={saving} onClick={() => {
                  setValues(formValues(scenario.plan));
                  setSelected(scenario.plan.dataset_version_id);
                  setErrors({});
                  setError("");
                  setEditing(false);
                }}>Return to saved review</button>}
              </div>
            </form>
          )}
          <aside className={`panel ${styles.content}`} aria-label="Planning context">
            <p className="eyebrow">Dataset</p>
            <h2>{selectedManifest?.district_label ?? "Synthetic planning sandbox"}</h2>
            {selectedManifest && (
              <>
                <span className="badge">{selectedManifest.is_synthetic ? "Synthetic demonstration" : "Aggregate dataset"}</span>
                <p className="muted">Version {selectedManifest.version} · One modeled week</p>
              </>
            )}
            {eligibleCount !== undefined && <p>{eligibleCount} eligible candidate zones.</p>}
            <Link className="button" href="/data">Explore dataset</Link>
            <h2>Planning method</h2>
            <p className="muted">The solver prioritizes covered visits, served visits, the worst-served cluster, travel time, then cost.</p>
            {!readiness.data?.ai_enabled ? (
              <p className="muted">Manual planning · AI assistance {readiness.error ? "unavailable" : readiness.data ? "off" : "loading"}</p>
            ) : !selectedManifest?.is_synthetic ? (
              <p className="muted">Manual planning · AI assistance is available for synthetic datasets.</p>
            ) : !reviewing && (
              <PlanAssistant key={selected} datasetId={selected} disabled={saving || !datasetReady}
                onApply={(plan) => {
                  setValues(formValues(plan));
                  setErrors({});
                  setError("");
                  document.getElementById("budget_pkr")?.focus();
                }} />
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
