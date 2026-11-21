"use client";

import Link from "next/link";
import { useMemo, useRef, useState, type FormEvent } from "react";
import { Icon } from "@/components/icon";
import { useData } from "@/components/load";
import { Network } from "@/components/network";
import { PlanAssumptions } from "@/components/planning/assumptions";
import { ResultStatus } from "@/components/results/result-details";
import { api, errorMessage, formatNumber, post } from "@/lib/api";
import type { Dataset, PlanSpec, Result, RunSnapshot, Scenario } from "@/lib/types";
import styles from "./studio.module.css";

type Mission = {
  key: string;
  title: string;
  subtitle: string;
  aim: string;
  adjustments: Partial<PlanSpec>;
};

const SEED_ID = "demo-bajaur-v1";
const MISSIONS: Mission[] = [
  {
    key: "reach", title: "Reach the overlooked",
    subtitle: "Which two new sites could cover more visits?",
    aim: "Expand weekly service access with two mobile units.",
    adjustments: { budget_pkr: 300000, max_new_units: 2, threshold_minutes: 45, demand_multiplier_pct: 100 },
  },
  {
    key: "surge", title: "Demand surge",
    subtitle: "Can the network handle 25% more requests?",
    aim: "Test the same budget against higher weekly demand.",
    adjustments: { budget_pkr: 300000, max_new_units: 2, threshold_minutes: 45, demand_multiplier_pct: 125 },
  },
  {
    key: "budget", title: "Tough budget choice",
    subtitle: "What if only one new unit is affordable?",
    aim: "Find an audited option under a tighter spending cap.",
    adjustments: { budget_pkr: 150000, max_new_units: 1, threshold_minutes: 45, demand_multiplier_pct: 100 },
  },
];

const DEFAULT_PLAN: PlanSpec = {
  dataset_version_id: SEED_ID,
  budget_pkr: 300000,
  max_new_units: 2,
  threshold_minutes: 45,
  demand_multiplier_pct: 100,
  equity_min_pct: 0,
  policy: "coverage_first",
  seed: 2026,
};

type Evidence = { baseline: Result; optimized: Result; baselineId: string; optimizedId: string };
const TERMINAL = new Set(["NO_SOLUTION", "FAILED", "CANCELLED", "INTERRUPTED", "TIMED_OUT"]);
const pause = (milliseconds: number) => new Promise<void>((resolve) => setTimeout(resolve, milliseconds));
const round = (value: number) => Math.round(value * 10) / 10;
const signed = (value: number) => (value > 0 ? "+" : "") + round(value).toFixed(1);
const percent = (value: number) => round(value).toFixed(1) + "%";

async function waitForAuditedResult(runId: string): Promise<Result> {
  for (let attempt = 0; attempt < 90; attempt++) {
    const run = await api<RunSnapshot>("/runs/" + encodeURIComponent(runId));
    if (run.status === "COMPLETED") {
      if (!run.result || !run.result.audit.passed) throw new Error("The planner did not publish an audited allocation.");
      return run.result;
    }
    if (TERMINAL.has(run.status)) {
      throw new Error(run.error?.message ?? "The " + run.kind + " run ended with " + run.status.toLowerCase() + ". Adjust your constraints and try again.");
    }
    await pause(900);
  }
  throw new Error("This simulation is taking longer than expected. Open the saved runs to check its status.");
}

function MetricBar({ value, variant = "new" }: { value: number; variant?: "old" | "new" }) {
  return <span className={styles.barTrack} aria-hidden="true">
    <span className={variant === "old" ? styles.barOld : styles.barNew}
      style={{ width: Math.min(100, Math.max(0, value)) + "%" }} />
  </span>;
}

export default function ImpactStudio() {
  const dataset = useData<Dataset>("/datasets/" + SEED_ID);
  const [missionKey, setMissionKey] = useState("reach");
  const [plan, setPlan] = useState<PlanSpec>(DEFAULT_PLAN);
  const [reviewing, setReviewing] = useState(false);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [phase, setPhase] = useState<"idle" | "creating" | "baseline" | "optimized" | "complete" | "error">("idle");
  const [issue, setIssue] = useState("");
  const [question, setQuestion] = useState<"why" | "fairness" | "cost" | "trust">("why");
  const [zone, setZone] = useState("All zones");
  const [savedRuns, setSavedRuns] = useState<{ id: string; label: string }[]>([]);
  const busy = useRef(false);

  const currentMission = MISSIONS.find((row) => row.key === missionKey) ?? MISSIONS[0];
  const working = phase === "creating" || phase === "baseline" || phase === "optimized";
  const isReady = Boolean(dataset.data);
  const update = (field: keyof PlanSpec, value: number) => {
    if (working) return;
    setPlan((existing) => ({ ...existing, [field]: value }));
    setEvidence(null);
    setReviewing(false);
    setPhase("idle");
    setIssue("");
  };
  const selectMission = (mission: Mission) => {
    if (working) return;
    setMissionKey(mission.key);
    setPlan({ ...DEFAULT_PLAN, ...mission.adjustments });
    setEvidence(null);
    setReviewing(false);
    setPhase("idle");
    setIssue("");
    setQuestion("why");
    setZone("All zones");
  };

  async function runSimulation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current || !dataset.data) return;
    if (!reviewing) {
      setReviewing(true);
      return;
    }
    busy.current = true;
    setReviewing(false);
    setEvidence(null);
    setSavedRuns([]);
    setIssue("");
    setPhase("creating");
    try {
      const scenario = await post<Scenario>("/scenarios", plan);
      await post<Scenario>("/scenarios/" + encodeURIComponent(scenario.scenario_id) + "/confirm", {
        plan_hash: scenario.plan_hash,
      });
      setPhase("baseline");
      const first = await post<{ run_id: string }>(
        "/scenarios/" + encodeURIComponent(scenario.scenario_id) + "/runs", { kind: "baseline" },
      );
      setSavedRuns([{ id: first.run_id, label: "Baseline run" }]);
      const baseline = await waitForAuditedResult(first.run_id);
      setPhase("optimized");
      const second = await post<{ run_id: string }>(
        "/scenarios/" + encodeURIComponent(scenario.scenario_id) + "/runs", { kind: "optimized" },
      );
      setSavedRuns((previous) => [...previous, { id: second.run_id, label: "Optimized run" }]);
      const optimized = await waitForAuditedResult(second.run_id);
      if ([baseline, optimized].some((result) =>
        result.dataset_sha256 !== dataset.data?.sha256 || result.plan_hash !== scenario.plan_hash)) {
        throw new Error("The two runs have incompatible source assumptions.");
      }
      setEvidence({ baseline, optimized, baselineId: first.run_id, optimizedId: second.run_id });
      setPhase("complete");
    } catch (failure) {
      setIssue(errorMessage(failure));
      setPhase("error");
    } finally {
      busy.current = false;
    }
  }

  const communities = useMemo(() => {
    if (!dataset.data || !evidence) return [];
    const baseline = new Map(evidence.baseline.metrics.clusters.map((r) => [r.community_id, r]));
    const optimized = new Map(evidence.optimized.metrics.clusters.map((r) => [r.community_id, r]));
    return dataset.data.communities.map((community) => {
      const old = baseline.get(community.id);
      const next = optimized.get(community.id);
      return {
        ...community, old: old?.coverage_pct ?? 0, next: next?.coverage_pct ?? 0,
        difference: (next?.covered_visits ?? 0) - (old?.covered_visits ?? 0),
        covered: next?.covered_visits ?? 0,
        demand: next?.demand_visits ?? community.demand_visits_per_week,
      };
    });
  }, [dataset.data, evidence]);

  const zones = useMemo(() => {
    const names = ["Valley", "Foothill", "Ridge"];
    if (!evidence) return [];
    return names.map((name) => {
      const rows = communities.filter((row) => row.zone_class.toLowerCase() === name.toLowerCase());
      const demand = rows.reduce((sum, row) => sum + row.demand, 0);
      const covered = rows.reduce((sum, row) => sum + row.covered, 0);
      const previous = rows.reduce((sum, row) => {
        const cluster = evidence.baseline.metrics.clusters.find((item) => item.community_id === row.id);
        return sum + (cluster?.covered_visits ?? 0);
      }, 0);
      return { name, demand, covered, previous, rate: demand ? 100 * covered / demand : 0, before: demand ? 100 * previous / demand : 0 };
    });
  }, [communities, evidence]);

  const filteredCommunities = zone === "All zones" ? communities :
    communities.filter((row) => row.zone_class.toLowerCase() === zone.toLowerCase());
  const gaining = filteredCommunities.filter((row) => row.difference > 0).sort((a, b) => b.difference - a.difference);
  const losing = filteredCommunities.filter((row) => row.difference < 0).sort((a, b) => a.difference - b.difference);
  const baseline = evidence?.baseline.metrics;
  const optimized = evidence?.optimized.metrics;
  const extra = baseline && optimized ? optimized.covered_visits - baseline.covered_visits : 0;
  const cost = optimized?.cost_pkr ?? 0;
  const selectedIds = evidence?.optimized.selected_candidate_ids ?? [];
  const selectedSites = selectedIds.join(", ") || "No new sites";
  const gain = gaining[0];
  const loss = losing[0];

  const answers = {
    why: evidence
      ? (selectedIds.length ? "The solver selected " + selectedSites + " together. " : "The solver selected no additional sites. ") +
        "The first objective is to maximize covered visits within " + plan.threshold_minutes +
        " minutes under the budget and unit limits. This run does not quantify which unselected site would perform best in a different combination."
      : "Run a scenario to see which sites the solver selects and how the allocation performs.",
    fairness: evidence
      ? gaining.length + " modeled communities gain covered visits and " + losing.length + " lose covered visits in the selected zone view. " +
        (gain ? gain.label + " gains the most (" + formatNumber(gain.difference) + " visits per week). " : "") +
        (loss ? loss.label + " loses the most (" + formatNumber(-loss.difference) + " visits per week). " : "") +
        "District-wide, the worst community coverage changes from " + percent(baseline!.worst_cluster_coverage_pct) + " to " + percent(optimized!.worst_cluster_coverage_pct) + "."
      : "The Equity Lens will show who gains, who loses, and how the worst-served community fares.",
    cost: evidence
      ? "The plan spends PKR " + formatNumber(cost) + " per modeled week, against a PKR " + formatNumber(plan.budget_pkr) + " cap. " + (extra > 0 ? "The modeled cost is about PKR " + formatNumber(Math.round(cost / extra)) + " per additional within-threshold visit." : "No additional covered visits were achieved.")
      : "The verified run will calculate budget used and the cost per additional covered visit.",
    trust: evidence
      ? "Both runs passed their independent allocation audit and used exactly matching dataset and plan hashes. All coordinates, facilities, visits and costs are synthetic; results are not real Bajaur forecasts."
      : "CIVITWIN uses fictional, labeled inputs. The local API solves each plan with OR-Tools and checks its output independently. A report exposes the assumptions and evidence.",
  };

  return <div className={styles.studio}>
    <section className={styles.hero}>
      <div className={styles.heroCopy}>
        <span className={styles.kicker}>Impact Studio</span>
        <h1>Who gets care <em>next?</em></h1>
        <p>Explore how a limited budget changes access to outpatient services in a synthetic Bajaur network. Compare two audited plans and see which communities gain or lose covered visits.</p>
        <div className={styles.heroActions}>
          <a href="#missions" className={styles.mainAction}>Explore the challenge <span aria-hidden="true">↗</span></a>
          <span className={styles.heroFoot}>No account or AI API required · Synthetic demonstration</span>
        </div>
      </div>
      <div className={styles.heroVisual}>
        <div className={styles.orbitOne} />
        <div className={styles.orbitTwo} />
        <div className={styles.visualCard}>
          <span>SYNTHETIC BAJAUR NETWORK</span>
          {dataset.data && <><strong>{formatNumber(dataset.data.communities.length)} communities</strong>
            <small>{formatNumber(dataset.data.sites.filter((site) => site.type === "existing").length)} existing sites · One modeled week</small></>}
        </div>
      </div>
    </section>

    <section id="missions" className={styles.section}>
      <div className={styles.sectionHeading}>
        <h2>Choose a planning mission</h2>
        <span className={styles.stepCaption}>Select one to load its assumptions</span>
      </div>
      <div className={styles.missions}>
        {MISSIONS.map((mission) => <button type="button" key={mission.key}
          className={styles.mission + (missionKey === mission.key ? " " + styles.missionActive : "")}
          aria-pressed={missionKey === mission.key} onClick={() => selectMission(mission)}
          disabled={working}>
          <strong>{mission.title}</strong>
          <span className={styles.missionSub}>{mission.subtitle}</span>
          <span className={styles.missionFoot}>{mission.aim}</span>
        </button>)}
      </div>
    </section>

    <section className={styles.planner} aria-label="Mission simulation">
      <form className={styles.controls} onSubmit={runSimulation}>
        <div className={styles.sectionHeading}>
          <h2>Set the planning assumptions</h2>
        </div>
        <p className={styles.controlIntro}>Both allocations use the same travel threshold, demand and equity floor.</p>
        <div className={styles.sliders}>
          <label className={styles.slider}>
            <span>Weekly budget <strong>PKR {formatNumber(plan.budget_pkr)}</strong></span>
            <input type="range" min={0} max={450000} step={25000} value={plan.budget_pkr}
              onChange={(e) => update("budget_pkr", Number(e.target.value))} disabled={working} aria-label="Weekly budget"/>
            <small>0 — 450,000 PKR</small>
          </label>
          <label className={styles.slider}>
            <span>New mobile service units <strong>{plan.max_new_units}</strong></span>
            <input type="range" min={0} max={3} step={1} value={plan.max_new_units}
              onChange={(e) => update("max_new_units", Number(e.target.value))} disabled={working} aria-label="New mobile service units"/>
            <small>0 — 3 candidate facilities</small>
          </label>
          <label className={styles.slider}>
            <span>Travel-time threshold <strong>{plan.threshold_minutes} min</strong></span>
            <input type="range" min={15} max={90} step={5} value={plan.threshold_minutes}
              onChange={(e) => update("threshold_minutes", Number(e.target.value))} disabled={working} aria-label="Travel-time threshold"/>
            <small>Maximum time counted as accessible</small>
          </label>
          <label className={styles.slider}>
            <span>Demand level <strong>{plan.demand_multiplier_pct}%</strong></span>
            <input type="range" min={75} max={150} step={5} value={plan.demand_multiplier_pct}
              onChange={(e) => update("demand_multiplier_pct", Number(e.target.value))} disabled={working} aria-label="Demand level"/>
            <small>75% — 150% of the fictional weekly demand</small>
          </label>
        </div>
        <details className={styles.advanced}>
          <summary>Advanced: protect every community</summary>
          <label className={styles.slider}>
            <span>Minimum coverage floor <strong>{plan.equity_min_pct}%</strong></span>
            <input type="range" min={0} max={50} step={5} value={plan.equity_min_pct}
              onChange={(e) => update("equity_min_pct", Number(e.target.value))} disabled={working} aria-label="Minimum coverage floor"/>
            <small>A strict equity floor can make the existing-sites baseline infeasible.</small>
          </label>
        </details>
        {reviewing && <section className={styles.review} aria-labelledby="review-impact">
          <h3 id="review-impact">Review the plan for one modeled week</h3>
          <PlanAssumptions plan={plan} />
          <p>The baseline uses existing sites. The alternative can open eligible candidates within the confirmed budget.</p>
        </section>}
        <div className={styles.runFooter}>
          <button className={styles.runButton} type="submit" disabled={!isReady || working}>
            {working ? "Simulating…" : reviewing ? "Confirm and run both allocations" : "Review simulation plan"}
          </button>
          <span className={styles.runNote}>Uses the real OR-Tools solver and independent audit.</span>
        </div>
        {dataset.error && <div role="alert" className={styles.error}><b>Local API unavailable.</b> {dataset.error} <button type="button" onClick={dataset.retry}>Retry connection</button></div>}
        {phase === "error" && <div role="alert" className={styles.error}>{issue} <span>Review the saved runs or adjust your assumptions.</span></div>}
        {!evidence && savedRuns.length > 0 && <div className={styles.resultsActions}>
          {savedRuns.map((run) => <Link key={run.id} href={"/runs/" + encodeURIComponent(run.id)}>{run.label}</Link>)}
        </div>}
        {working && <div className={styles.progress} role="status" aria-live="polite">
          <span className={styles.spinner} /> {phase === "creating" ? "Confirming the model's assumptions…" : phase === "baseline" ? "Auditing the existing-sites baseline…" : "Solving and auditing the optimized allocation…"}
        </div>}
      </form>
      <aside className={styles.missionBrief}>
        <span className={styles.kicker}>MISSION BRIEFING</span>
        <h3>{currentMission.title}</h3>
        <p>{currentMission.aim}</p>
        <div className={styles.briefStat}><span>District</span><b>Bajaur · fictional network</b></div>
        <div className={styles.briefStat}><span>Modeled week</span><b>1</b></div>
        <div className={styles.briefStat}><span>Source</span><b>Synthetic seed 2026</b></div>
        <div className={styles.briefDivider} />
        <strong className={styles.briefTitle}>What the model considers</strong>
        <ol>
          <li>Weekly demand and service capacity</li>
          <li>Connections and travel minutes</li>
          <li>Budget, eligibility and new-unit limits</li>
          <li>Worst-served community coverage</li>
        </ol>
        <span className={styles.briefCaution}>Decision support, not a real healthcare deployment recommendation.</span>
      </aside>
    </section>

    <section className={styles.section} aria-live="polite">
      <div className={styles.sectionHeading}>
        <h2>{evidence ? "Here is what changed" : "Simulation results"}</h2>
        {evidence && <span className={styles.verified}><Icon name="check" /> Both allocations independently audited</span>}
      </div>
      {!evidence ? <div className={styles.empty}>
        <p>Confirm a plan to compare covered visits, weekly cost and changes by community. Both allocations must pass the independent audit before the comparison appears.</p>
      </div> : <>
        <div className={styles.impactGrid}>
          <article className={styles.impactPrimary}>
            <span>WITHIN-THRESHOLD ACCESS</span>
            <div className={styles.bigNumber}>{percent(optimized!.coverage_pct)}</div>
            <p><b>{signed(optimized!.coverage_pct - baseline!.coverage_pct)} percentage points</b> versus existing sites</p>
            <div className={styles.beforeAfter}><span>Before: {percent(baseline!.coverage_pct)}</span><span>After: {percent(optimized!.coverage_pct)}</span></div>
            <div className={styles.dualBars}><MetricBar value={baseline!.coverage_pct} variant="old"/><MetricBar value={optimized!.coverage_pct} /></div>
          </article>
          <article className={styles.impactSmall}>
            <span>ADDITIONAL ACCESSIBLE VISITS</span>
            <strong>{extra > 0 ? "+" : ""}{formatNumber(extra)}</strong>
            <p>Unmet visits {formatNumber(baseline!.unmet_visits)} → {formatNumber(optimized!.unmet_visits)} per modeled week</p>
          </article>
          <article className={styles.impactSmall}>
            <span>WORST COMMUNITY ACCESS</span>
            <strong>{percent(optimized!.worst_cluster_coverage_pct)}</strong>
            <p>Baseline: {percent(baseline!.worst_cluster_coverage_pct)}</p>
          </article>
          <article className={styles.impactSmall}>
            <span>ADDITIONAL WEEKLY COST</span>
            <strong>PKR {formatNumber(cost)}</strong>
            <p>Budget ceiling: PKR {formatNumber(plan.budget_pkr)}</p>
          </article>
        </div>
        <div className={styles.resultsActions}>
          <span>Selected candidate sites: <b>{selectedSites}</b></span>
          <Link className="button primary" href={"/compare?baseline=" + encodeURIComponent(evidence.baselineId) + "&alternative=" + encodeURIComponent(evidence.optimizedId)}>Open audited comparison <Icon name="arrow" /></Link>
          <Link className="button" href={"/reports/" + encodeURIComponent(evidence.optimizedId)}>Full evidence report</Link>
        </div>
        <div className={styles.stories}>
          <section className={styles.storyCard}><h3>Existing sites</h3><ResultStatus result={evidence.baseline} /></section>
          <section className={styles.storyCard}><h3>Optimized plan</h3><ResultStatus result={evidence.optimized} /></section>
        </div>
        {dataset.data && <Network dataset={dataset.data} comparison={evidence} />}
        {dataset.data && selectedIds.length > 0 && <section className={styles.storyCard}>
          <h3>Selected facilities in the optimized allocation</h3>
          {dataset.data.sites.filter((site) => selectedIds.includes(site.id)).map((site) => {
            const visits = evidence.optimized.assignments
              .filter((row) => row.site_id === site.id)
              .reduce((sum, row) => sum + row.visits, 0);
            return <div className={styles.storyRow} key={site.id}>
              <span>{site.label} ({site.id})<small>PKR {formatNumber(site.fixed_cost_pkr)} per modeled week</small></span>
              <span>{formatNumber(visits)} of {formatNumber(site.capacity_per_week)} weekly slots assigned</span>
            </div>;
          })}
        </section>}

        <div className={styles.sectionHeading}>
          <div><span className={styles.kicker}>Equity Lens</span><h2>Who gains, and who gives up access?</h2></div>
          <label className={styles.zoneSelect}>Zone <select value={zone} onChange={(event) => setZone(event.target.value)}>
            <option>All zones</option><option>Valley</option><option>Foothill</option><option>Ridge</option>
          </select></label>
        </div>
        <div className={styles.zones}>
          {zones.map((row) => <div className={styles.zoneCard} key={row.name}>
            <div><strong>{row.name}</strong><span>{formatNumber(row.covered)} covered visits</span></div>
            <div className={styles.zonePercent}>{percent(row.rate)}</div>
            <div className={styles.zoneCompare}><MetricBar value={row.before} variant="old"/><MetricBar value={row.rate} /></div>
            <small>Before {percent(row.before)} · {row.covered - row.previous >= 0 ? "+" : ""}{formatNumber(row.covered - row.previous)} visits</small>
          </div>)}
        </div>
        <div className={styles.stories}>
          <section className={styles.storyCard}>
            <h3><span className={styles.gainIcon}>↑</span> Communities gaining access</h3>
            {gaining.length ? gaining.slice(0, 5).map((row) => <div className={styles.storyRow} key={row.id}>
              <span>{row.label}<small>{row.zone_class}</small></span>
              <strong className={styles.gain}>+{formatNumber(row.difference)} visits</strong>
            </div>) : <p>No modeled gains in this zone.</p>}
          </section>
          <section className={styles.storyCard}>
            <h3><span className={styles.lossIcon}>↓</span> Communities losing access</h3>
            {losing.length ? losing.slice(0, 5).map((row) => <div className={styles.storyRow} key={row.id}>
              <span>{row.label}<small>{row.zone_class}</small></span>
              <strong className={styles.loss}>{formatNumber(row.difference)} visits</strong>
            </div>) : <p>No modeled reductions in this zone.</p>}
          </section>
        </div>
        <p className={styles.scopeNote}>The lists show the five largest changes in each direction. The comparison includes every community. All counts are modeled weekly visits.</p>
      </>}
    </section>

    <section className={styles.explain}>
      <div><h2>Ask the evidence</h2><p>Answers are formatted from verified metrics and model assumptions. They work offline.</p></div>
      <div className={styles.questionArea}>
        <div className={styles.questionButtons}>
          {([["why", "Why these sites?"], ["fairness", "Is it fair?"], ["cost", "Is it worth the cost?"], ["trust", "Can I trust these numbers?"]] as const).map(([key, label]) =>
            <button type="button" key={key} className={question === key ? styles.questionActive : ""}
              onClick={() => setQuestion(key)} aria-pressed={question === key}>{label}</button>)}
        </div>
        <div className={styles.answer} role="status"><span>MODEL EVIDENCE</span><p>{answers[question]}</p></div>
      </div>
    </section>

    <footer className={styles.footer}>
      <strong>CIVITWIN AI <span>· Decisions you can inspect.</span></strong>
      <span>Built for learning and transparent planning · Fictional Bajaur demonstration · No patient data</span>
    </footer>
  </div>;
}
