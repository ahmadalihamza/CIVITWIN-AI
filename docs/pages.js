"use strict";

const scenario = document.querySelector("#scenario");
const message = document.querySelector("#result-message");
const table = document.querySelector("#results");
const body = document.querySelector("#observations");
const integer = new Intl.NumberFormat("en-PK");
const decimal = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 1 });
const percent = (value) => decimal.format(value) + "%";

function appendRow(label, values) {
  const row = body.insertRow();
  const heading = document.createElement("th");
  heading.scope = "row";
  heading.textContent = label;
  row.append(heading);
  for (const value of values) row.insertCell().textContent = value;
}

function render(record) {
  const { plan, observations } = record;
  const runs = [observations.baseline, observations.greedy, observations.optimized];
  const audited = (run) => run.audit_passed && run.metrics;
  const cells = (format) => runs.map((run) => audited(run) ? format(run.metrics) : "Unavailable");
  body.replaceChildren();
  appendRow("Solver outcome", runs.map((run) =>
    [run.status, run.solver_status].filter(Boolean).join(" · ").replaceAll("_", " ")));
  appendRow("Independent audit", runs.map((run) => run.audit_passed ? "Passed" : "Unavailable"));
  appendRow("Coverage within threshold", cells((metrics) =>
    percent(metrics.coverage_pct) + " (" + integer.format(metrics.covered_visits) + " of " + integer.format(metrics.total_demand) + ")"));
  appendRow("Unmet weekly visits", cells((metrics) => integer.format(metrics.unmet_visits)));
  appendRow("Worst cluster coverage", cells((metrics) => percent(metrics.worst_cluster_coverage_pct)));
  appendRow("Additional weekly cost", cells((metrics) => "PKR " + integer.format(metrics.cost_pkr)));
  table.hidden = false;
  message.textContent = "Travel threshold " + plan.threshold_minutes + " minutes · Equity floor " +
    plan.equity_min_pct + "% · Coverage-first policy";
}

async function load() {
  try {
    const response = await fetch("./release-benchmark.json");
    if (!response.ok) throw new Error("Benchmark unavailable");
    const benchmark = await response.json();
    const cases = benchmark.cases.filter((record) => record.case_id.startsWith("bajaur-"));
    scenario.replaceChildren();
    cases.forEach((record, index) => {
      const { plan } = record;
      const equity = plan.equity_min_pct ? " · " + plan.equity_min_pct + "% equity floor" : "";
      scenario.add(new Option("PKR " + integer.format(plan.budget_pkr) + " · " +
        plan.max_new_units + " max units" + equity, String(index)));
    });
    scenario.value = String(cases.findIndex((record) => record.case_id === "bajaur-default"));
    render(cases[Number(scenario.value)]);
    scenario.addEventListener("change", () => render(cases[Number(scenario.value)]));
    scenario.disabled = false;

    const stress = benchmark.stress.results;
    const range = stress.alternative.coverage_pct;
    document.querySelector("#stress").textContent = stress.paired_success_count + " of " +
      stress.case_count + " pairs completed. Optimized coverage ranged from " +
      percent(range.min) + " to " + percent(range.max) + ", with a median of " + percent(range.median) + ".";
  } catch {
    if (table.hidden) message.textContent = "The benchmark could not be loaded. Try the JSON download below.";
  }
}

load();
