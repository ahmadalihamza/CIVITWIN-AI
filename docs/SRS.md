# CIVITWIN AI
## Software Requirements Specification & Implementation Blueprint

**Version:** 1.0 | **Date:** 13 November 2026 | **Status:** Proposed implementation baseline

**Track:** KPITB AI Innovation Challenge — Civics  
**Domain:** Equitable public-service planning; healthcare accessibility first  
**Pilot:** Bajaur; Mohmand and Khyber as future expansion districts  
**Audience:** Developers, Codex, reviewers, competition judges and prospective stakeholders

**Core proposition:** Convert natural-language planning questions into validated mathematical models, compare feasible allocations, and explain the resulting trade-offs using auditable evidence.

This specification is a build contract, not a claim of a completed product. All numerical targets are acceptance goals; all example datasets and outcomes are synthetic unless marked otherwise. The prototype is an advisory planning sandbox, not a clinical, emergency dispatch, or operational deployment system.

### Document map
1. Product scope and success criteria
2. Actors, workflows and requirements
3. Architecture and repository
4. Data contracts and provenance
5. Mathematical optimization
6. Scenario simulation and evaluation
7. AI workflow and multilingual interface
8. REST API and persistence
9. UX specification
10. Security, privacy and reliability
11. Testing and acceptance
12. Build plan, deployment and handoff
13. Demo, risks and references

---
# 1. Product scope and success criteria

## 1.1 Problem and opportunity
District planners must evaluate competing resource allocations under incomplete data, varying demand, travel accessibility, service capacity and budget constraints. CIVITWIN makes those assumptions explicit, evaluates alternatives with a reproducible solver, and explains the trade-offs without pretending to know actual local service performance. The initial service is scheduled, non-emergency outpatient accessibility. No patient-level data, diagnosis or treatment is needed.

## 1.2 Scope and priorities
- **P0 (must ship):** synthetic Bajaur dataset, versioned import, network accessibility calculation, budget/capacity-constrained allocation, scenario editor, baseline vs optimized comparison, independent feasibility verifier, uncertainty stress tests, evidence-linked explanation, dashboard, export, tests, offline demo.
- **P1 (after P0 passes):** structured LLM plan parser, optional Urdu/Pashto interfaces, more detailed stress tests, saved workspaces, approved aggregate district data, multi-objective frontier visualization.
- **P2 (future pilot):** Mohmand and Khyber datasets, authenticated multi-user planning, stakeholder-calibrated demand, licensed mapping layers, expanded education use cases, optional queue simulation and formal validation.
- **Out of scope:** individual health records, clinical advice, emergency triage or dispatch, live tracking, real-time routing of field staff, actual procurement, automated government decisions, autonomous web agents, training a foundation model, real-world claims without validation.

## 1.3 Product objectives and measurable acceptance goals
| ID | Acceptance goal for P0 |
|---|---|
| G1 | Demonstrate 1 district, 24 synthetic community clusters, 5 existing service sites and 8 candidate planning zones. |
| G2 | Produce feasible baseline and alternative allocations with an independent audit; zero constraint violations for every accepted result. |
| G3 | Show demand-weighted access, service coverage, unmet demand, worst-served cluster and budget on identical inputs. |
| G4 | Evaluate 20 fixed-seed stress scenarios (demand and travel-cost changes); report intervals and failures, not certainty. |
| G5 | Complete default solve in <= 10 seconds and 20-scenario stress suite in <= 60 seconds on a documented reference machine, measured rather than assumed. |
| G6 | Entire default workflow works without an API key or external network after dependencies are installed. |
| G7 | Every explanation metric is tied to a result field; every export includes dataset provenance and a synthetic-data warning. |

## 1.4 Design decisions
Use a local-first monorepo. Optimize a small, aggregate planning instance before integrating language models. Treat the digital twin as a scenario-capable representation, not a live synchronized twin. The innovation claim is the integration of language-to-model compilation, verified optimization, uncertainty and fairness analysis in a locally relevant workflow; no claim of being the world's first is justified.

---
# 2. Actors, workflows and functional requirements

## 2.1 Actors
| Actor | Permissions / responsibilities |
|---|---|
| Planner | Open dataset, configure hypothetical scenarios, solve, compare, export. |
| Data steward | Validate and publish aggregate datasets, document sources and assumptions. |
| Reviewer | Read results, solver status, evidence and model limitations. |
| System administrator | Configure deployment and secrets; no clinical privileges. |

P0 is a single local demo session with a mock role label, not production authentication. Remote/public deployment must be read-only demo mode or have real authorization before enabling modifications.

## 2.2 End-to-end journey
1. Start application; load immutable synthetic dataset and visible DEMO banner.
2. Open baseline analysis; calculate demand served using existing capacity only.
3. Specify a budget, maximum new units, coverage threshold, fairness policy and demand assumptions via form or optional AI parser.
4. Review structured plan, assumptions and warnings; explicitly confirm before solve.
5. Run baseline and optimized allocation with the same parameters; audit results independently.
6. Compare KPIs, allocation by aggregate zone, trade-offs and solver status; run fixed-seed stress tests on saved alternatives.
7. Generate a deterministic explanation or optional evidence-grounded language explanation; export reproducible report.

## 2.3 Functional requirements (P0 unless stated)
| ID | System shall |
|---|---|
| FR-01 | Load a validated, immutable dataset version; display source, scope, date and synthetic flag. |
| FR-02 | Import approved CSV/JSON with schema validation, duplicate detection, referential checks and row-level errors; reject entire invalid import. |
| FR-03 | Compute accessible zone-to-site travel costs; exclude unreachable pairs and expose missing data. |
| FR-04 | Create and edit scenarios with typed integer bounds, budget, units, demand multiplier, threshold and equity parameter. |
| FR-05 | Compute a baseline with only existing sites, using the same assignment rules as optimization. |
| FR-06 | Optimize allocations with integer demand, capacity, budget, unit limits and eligible candidate constraints. |
| FR-07 | Audit every returned allocation independently; block publication if any constraint fails. |
| FR-08 | Compare at least two results with matching dataset/assumptions; visibly flag incompatible comparisons. |
| FR-09 | Run reproducible stress scenarios; report failure, coverage, unmet demand and equity distributions. |
| FR-10 | Show metric definitions, evidence IDs, costs, solver status and limitations. |
| FR-11 | Provide deterministic natural-language summary offline; optional LLM paraphrase cannot change values. |
| FR-12 | Export JSON and CSV plus printable report with model version, dataset hash, inputs and metrics. |
| FR-13 | Persist scenario and run history; allow cancellation or timeout without publishing partial invalid results. |
| FR-14 (P1) | Parse English/Urdu/Pashto requests into a restricted PlanSpec and require review. |
| FR-15 (P1) | Offer a three-policy comparison: coverage-first, equity-first and cost-efficient. |
| FR-16 (P2) | Enable approved dataset/role management with authenticated multi-user access. |

---
# 3. System architecture and repository

## 3.1 Logical architecture
```text
Browser (Next.js / TypeScript)
  -> FastAPI REST / Pydantic contracts
     -> scenario service + validation
     -> planning workflow (explicit state machine)
         -> dataset registry -> travel cost matrix
         -> baseline / optimization -> independent audit
         -> stress test -> metrics -> evidence packet
     -> explanation adapter (template or optional LLM)
     -> SQLite repository + immutable result snapshots
  <- typed JSON / job status / report export
```
Keep numerical logic in pure Python services, independent of HTTP, persistence and AI provider. Use a bounded local job executor for P0; a single API process owns the executor. P2 can replace it with a durable queue. No direct model-to-database or model-to-shell access.

## 3.2 Technology choices
| Layer | Choice and rationale |
|---|---|
| Web | Next.js, TypeScript, Tailwind; accessible responsive UI. |
| API | Python 3.11+, FastAPI, Pydantic, SQLAlchemy/Alembic. |
| Engine | OR-Tools CP-SAT, NetworkX, NumPy; explicit algorithms. |
| Storage | SQLite for local demo; PostgreSQL migration later. |
| Visualization | Plotly or Recharts; schematic aggregate zone view first. |
| AI | Provider adapter, structured JSON outputs; template fallback. |
| Test | pytest, Vitest, Playwright; fixture-based reproducibility. |
| Tooling | Docker Compose, lockfiles, CI, ruff, ESLint, type checks. |

Select mutually compatible dependency versions and commit lockfiles after verification. Do not invent a model identifier; configure a supported model through environment variables. A ChatGPT subscription does not itself establish API credits or credentials.

## 3.3 Repository layout
```text
civitwin-ai/
  AGENTS.md               # coding rules and phase gates
  README.md               # setup, demo, limitations
  docs/SRS.md             # authoritative specification
  apps/web/               # pages, components, typed API client
  services/api/
    app/{main,config,schemas,routers,db}/
    app/domain/{dataset,travel,optimizer,audit,metrics,stress}/
    app/workflows/        # planner state machine + jobs
    app/ai/               # provider, parser, evidence, templates
    migrations/           # Alembic
    tests/{unit,integration,fixtures}/
  data/{demo,schemas}/    # immutable synthetic inputs
  scripts/                # seed, smoke, benchmark
  tests/e2e/              # browser acceptance
  infra/                  # Dockerfiles / deployment
  .github/workflows/      # CI
  .env.example            # names only, no credentials
  compose.yaml
```

## 3.4 Processing state machine
DRAFT -> VALIDATED -> CONFIRMED -> QUEUED -> RUNNING -> AUDITING -> COMPLETED. Terminal alternatives: INVALID, FAILED, CANCELLED, TIMED_OUT, NO_SOLUTION. Only audited feasible results reach COMPLETED; FEASIBLE solver results are explicitly marked non-proven-optimal. On restart, unfinished P0 jobs become INTERRUPTED/FAILED, never falsely completed.

---
# 4. Data contracts, provenance and demo dataset

## 4.1 Input schemas
All IDs are strings, unique within dataset version; data are aggregate and non-identifying. Integers are required for model coefficients. Define a JSON schema and CSV adapters with explicit units.

| Entity | Required fields and rules |
|---|---|
| Dataset | id, version, district_label, is_synthetic, source_url (nullable), source_date, license, sha256, assumptions, model_scope. |
| Community | id, label, demand_visits_per_week >= 0, population >= 0 (optional), zone_class, node_id. |
| Site | id, label, type (existing/candidate), node_id, capacity_per_week >= 0, fixed_cost_pkr >= 0, eligible boolean. |
| Edge | from_node, to_node, minutes > 0, direction; no negative costs. |
| Node | id, display_x, display_y (schematic positions only), label. |
| Scenario | dataset_version_id, budget_pkr, max_new_units, threshold_minutes, demand_multiplier_pct, equity_min_pct, seed, policy. |
| Provenance | entity/field, source, method (synthetic/observed/estimated), timestamp, caveat. |

Time horizon is one modeled week. Demand means service visits requested per week, not people. Population is optional descriptive data and must not be used as demand without a documented conversion. Costs represent weekly-equivalent planning costs in PKR, not verified procurement prices. No mixing currencies or periods.

## 4.2 Synthetic seed specification
Generate 24 fictional community clusters (C01-C24), 5 fictional existing service sites (E01-E05), 8 candidate zones (N01-N08) and a connected schematic network. No real facility names, coordinates, staff locations, or patient data. Use seed 2026 and deterministic ordered IDs. Include one separate disconnected fixture, never hide it in the default demo. Default budget PKR 300,000/week; max new units 2; threshold 45 minutes; demand multiplier 100%; equity floor 0%; seed 2026. Illustrative community demand 40-160 visits/week, existing site capacity 150-300, candidate capacity 180-300, candidate cost PKR 90,000-160,000/week; generate values, then verify the default instance yields a feasible, meaningful comparison (not guaranteed improvement). Document all generated values and avoid claiming real district coverage. Default labels: 'Bajaur — synthetic planning sandbox'.

## 4.3 Data ingestion rules
Validate types, uniqueness, nonnegative bounded values, graph references, allowed enums, candidate eligibility and source manifest. Reject unknown required columns or invalid rows with machine-readable errors. Canonical JSON serialization with sorted keys and ordered entities produces SHA-256; store original source metadata and derived transformation notes. Never silently impute. Missing optional fields display unknown. Missing travel connection is unreachable, not zero. Schema version changes require migrations.

## 4.4 Real-data onboarding (future)
Pakistan Bureau of Statistics publishes 2023 district census tables and spreadsheet results [R1, R2]. These support demographic context, not directly measured healthcare visits. Obtain stakeholder-approved aggregate service counts, capacities, travel-time estimates and costs; document date, licensing, coverage and missingness. Public mapping data can support aggregate accessibility after review; avoid publishing sensitive operational details. Treat Mohmand and Khyber as future expansion; do not imply access to datasets or pilot approval. No automatic scraping or live data dependence in P0.

---
# 5. Mathematical optimization specification

## 5.1 Sets, inputs and variables
Let I be community clusters; J = E union N, existing sites E and eligible candidate zones N. D_i is integer demand visits/week; C_j is integer capacity visits/week; t_ij is nonnegative integer travel minutes from I to J; b_j is weekly candidate cost PKR; B is weekly budget; K is maximum new units; T is coverage threshold. Exclude unreachable pairs A; use a deterministic shortest-path method on the schematic network and cache the cost matrix by dataset hash. Round travel time once and document units. Existing sites are fixed open.

Decision variables: x_j in {0,1} for candidate activation (one unit maximum per candidate); y_ij >= 0 integer visits assigned for reachable pairs; u_i >= 0 integer unmet visits. For existing sites define x_j = 1. This is aggregate fractional-by-visit assignment, not patient scheduling. No individual routes are produced.

## 5.2 Hard constraints
- Demand balance: sum_j y_ij + u_i = D_i, for all i.
- Capacity: sum_i y_ij <= C_j * x_j, for all j.
- Budget: sum_(j in N) b_j * x_j <= B.
- Unit count: sum_(j in N) x_j <= K.
- Ineligible candidates must be closed; unreachable pairs must not have assignment variables.
- Optional hard equity floor q in integer percent: 100 * sum_(j: t_ij <= T) y_ij >= q * D_i for each i with D_i > 0. Default q = 0. If infeasible, explain conflict; do not relax automatically.

## 5.3 Objective and policy
Define W = sum_i sum_(j: t_ij <= T) y_ij (within-threshold visits); S = sum_ij y_ij (served); L = sum_ij t_ij*y_ij (visit-minutes); C = sum_N b_j*x_j. Define integer equity score m in [0,10000] basis points using 10000*within_i >= m*D_i for all positive-demand clusters. For zero total demand, reject planning input with a clear validation message.

Default coverage-first lexicographic stages: maximize W; fix its proven optimum; maximize S; fix; maximize m; fix; minimize L; fix; minimize C. Equity-first swaps m to first stage. Cost-efficient policy uses a user-confirmed minimum coverage target, then minimizes C, maximizes W and S, and minimizes L. P0 only requires coverage-first; alternative policies P1. Baseline fixes all candidates closed and uses identical parameters and objective. If equity floor renders baseline infeasible, show 'baseline infeasible under selected policy' rather than fabricated values.

CP-SAT uses integer coefficients [R3]. Validate upper bounds and potential 64-bit overflow before construction. Global wall-clock budget is shared across stages. If a stage returns FEASIBLE but not OPTIMAL, retain audited incumbent, stop lexicographic refinement, mark incomplete objectives and report bound if available. If no incumbent, report status; never display zeros as a solution. Record time limit, seed, worker count (1 for reproducibility), objective stages and solver version. Stable sorted input ordering and fixed seed reduce variability; exact bitwise reproducibility across versions is not promised.

## 5.4 Independent audit and error handling
Recompute all constraints from serialized output without solver internals: integrality, nonnegativity, allowed pairs, demand balance, capacity, budget, activation count, equity floor, and metrics. Check that selected sites match allocations and that no foreign IDs exist. Fail closed on any mismatch. An infeasible input returns diagnostic hints (try lowering equity floor or revising capacity/budget) but never silently changes the approved scenario. Audit record contains check IDs, expected/actual values, pass status, and result hash.

---
# 6. Simulation, metrics and benchmark protocol

## 6.1 Metric definitions
| Metric | Formula / display rule |
|---|---|
| Total demand | D = sum_i D_i, visits/week. |
| Served | S = sum_ij y_ij; served rate = 100*S/D. |
| Unmet demand | U = sum_i u_i; unmet rate = 100*U/D. |
| Within-threshold coverage | 100*W/D; denominator includes unmet visits. |
| Mean assigned travel | L/S minutes; null if S=0; explicitly served visits only. |
| Worst cluster coverage | min_i(100*within_i/D_i) over positive demand clusters. |
| Equity gap | max cluster coverage minus min cluster coverage, percentage points. |
| Cost | C PKR/week; budget utilization 100*C/B, null if B=0. |
| Additional cost per added covered visit | (C_alt-C_base)/(W_alt-W_base); null if denominator <= 0. |
| Comparison | percentage-point difference for rates; absolute minutes/PKR; relative change only with nonzero denominator. |

Compute with unrounded integer totals; round for display only. Show counts and denominators on hover and in exports. Do not present modeled visits as unique residents or causal improvements.

## 6.2 Counterfactual and uncertainty tests
Stress testing is a scenario sensitivity experiment, not a probabilistic forecast. Generate 20 cases using a recorded deterministic seed. For each case draw integer demand multipliers (80-130% of default) and travel multipliers (90-140%) as illustrative ranges, not empirical distributions; round using documented half-up integer rules. Keep chosen candidate activations fixed for baseline and optimized plan; reassign visits under perturbed conditions with the same capacity and policy. This tests robustness of the plan rather than assuming new facilities can be chosen instantly in every case. Run both alternatives on the exact same stress cases.

For each case store input multipliers, status, covered visits, coverage, unmet rate, worst cluster and travel metric. Report median, minimum/maximum and empirical P10/P90 via a documented quantile method; include successful-case count and failure rate. If hard constraints fail, mark case infeasible; exclude from numeric distributions and display exclusion count. Intervals are scenario ranges, not confidence intervals. Do not claim real-world probabilities. Optional P1: display re-optimization as a separately labeled adaptation experiment.

## 6.3 Benchmark and evaluation design
Compare (A) existing-only baseline, (B) deterministic greedy heuristic that adds eligible candidates with the greatest marginal coverage per cost, then solves assignments, and (C) CP-SAT optimization. Enforce same budget, capacity and demand in B/C. If greedy cannot satisfy the equity floor, show infeasibility; no favorable cherry-picking. Test budget 0, 150k, 300k, 450k; max units 0, 1, 2; equity floor 0 and one positive value; record selected representative scenarios in benchmark JSON. Include disconnected and saturated fixtures. Report runtime, solver status, solution quality and constraint pass rate. Baseline may differ from observed real-world practice; label it modeled baseline. Never manufacture a performance gain if the optimized case ties or underperforms.

---
# 7. AI workflow and explainability

## 7.1 Agent design: constrained workflow, not autonomous agents
Implement a deterministic orchestrator with named bounded steps. Planning agent parses optional natural language; data agent performs schema checks; simulation agent invokes domain services; audit agent independently verifies constraints; explanation agent formats evidence. Data, solve and audit stages are ordinary deterministic code, not LLM calls. Only interpretation and optional language generation use a model. A state machine is sufficient; LangGraph is optional P1, not mandatory infrastructure.

## 7.2 PlanSpec contract and confirmation
```json
{
  "dataset_version_id": "demo-bajaur-v1",
  "budget_pkr": 300000,
  "max_new_units": 2,
  "threshold_minutes": 45,
  "demand_multiplier_pct": 100,
  "equity_min_pct": 0,
  "policy": "coverage_first",
  "seed": 2026
}
```
Use strict JSON schema (additionalProperties false), enum policies, bounded numeric fields: budget 0-100000000; max units 0-50 and <= eligible candidates; threshold 1-240; demand multiplier 1-300%; equity 0-100%; seed 0-2147483647. Also enforce dataset size and aggregate integer caps in config. Missing values require explicit defaults shown in preview; ambiguous requests return a clarification or use the manual form. The model must never execute SQL, code, shell, HTTP tools or alter authoritative constraints. User confirms the exact validated plan hash before execution. Any changes invalidate confirmation.

## 7.3 Evidence packet and explanation
Create an immutable packet with result ID, dataset hash, plan hash, model version, solver status, audit status, metric values/units, assumptions, and per-metric evidence paths (e.g. result.metrics.coverage_pct). Template explanation is always available and authoritative for P0. Optional LLM gets only packet and language choice; restrict output to claim objects with evidence IDs and narrative segments. Render numeric values directly from verified packet placeholders, not model prose. Reject unknown references, unsupported claims, out-of-scope requests or schema violations; fall back to template. No model-generated medical advice. Never label an uncertain result optimal unless solver status proves it.

## 7.4 Language and evaluation
P0 English; provide deterministic number/date formatting. P1 Urdu and Pashto with locale dictionary, RTL layout, bilingual review by fluent speakers, and manual form fallback. Translate explanatory text, not IDs, numbers or units. Test 20 manually labeled planning prompts (English, and only validated translations if available), ambiguity, injected instructions and out-of-domain prompts. Report exact field match and rejection rate, with no fabricated accuracy. Model/API disabled by default; provider adapter has short timeout, max retries 1, token cap, schema validation and no sensitive data transmission.

---
# 8. REST API, persistence and integration contracts

## 8.1 REST endpoints (prefix /api/v1)
| Method / path | Request and behavior |
|---|---|
| GET /health | Liveness; no secret or internal stack details. |
| GET /ready | Dataset/database readiness and solver availability. |
| GET /datasets | List published versions and source metadata. |
| GET /datasets/{id} | Aggregate graph, metadata and manifest. |
| POST /datasets/import | Validated JSON/CSV bundle; local steward only. |
| POST /plans/parse | Optional text/language; returns draft, warnings; no solve. |
| POST /scenarios | Valid PlanSpec -> scenario ID and plan hash. |
| POST /scenarios/{id}/confirm | Expected plan hash; 409 on mismatch. |
| POST /scenarios/{id}/runs | Confirmed plan, kind baseline/optimized/greedy; 202 job ID. |
| GET /runs/{id} | Status, progress stage, error or immutable result. |
| POST /runs/{id}/cancel | Cooperative cancellation; 409 if terminal. |
| POST /comparisons | Compatible result IDs -> comparison; reject mismatches. |
| POST /stress-runs | Baseline and alternative IDs, seed/count -> 202 job ID. |
| GET /stress-runs/{id} | Status, results and failures. |
| GET /runs/{id}/explanation | Evidence/template, optional language. |
| GET /runs/{id}/export | JSON/CSV; printable HTML report via UI. |

Use HTTP 400 malformed, 404 missing ID, 409 conflict, 422 invalid schema/semantics, 429 job limit, 503 unavailable. JSON error envelope: {code, message, field_errors, request_id}. No raw exceptions to UI. Idempotency key for job submissions; reject same key with different payload. Poll jobs at 1-second interval with backoff up to 5 seconds. Cap uploads at 2 MB, concurrent solve jobs at 1 in P0; configurable future limits.

### Result envelope (required fields)

```json
{
  "run_id": "run-001",
  "scenario_id": "scenario-001",
  "kind": "optimized",
  "status": "COMPLETED",
  "solver_status": "OPTIMAL",
  "dataset_sha256": "<computed hash>",
  "plan_hash": "<computed hash>",
  "selected_candidate_ids": [],
  "assignments": [],
  "unmet_by_community": [],
  "metrics": {},
  "objective_stages": [],
  "audit": {"passed": true, "checks": []},
  "warnings": [],
  "runtime_ms": 0,
  "model_version": "1.0"
}
```

This is a shape example only, not a valid completed run. An actual assignment record has community_id, site_id and integer visits; unmet records have community_id and integer visits. Populate all metrics in §6, including numerator and denominator, with null for undefined ratios. Completed runs require computed values and nonempty audit checks. Errors and non-solution states omit result fields. A comparison requires identical dataset hash and confirmed plan hash, with only run kind differing. A stress request references those completed audited results and returns paired per-case observations, summary quantiles and failure counts.

## 8.2 Persistence model
| Table | Key fields |
|---|---|
| dataset_versions | id PK, district, version, sha256 UNIQUE, manifest_json, payload_json, created_at. |
| scenarios | id PK, dataset_id FK, plan_json, plan_hash, status, confirmed_at, created_at. |
| runs | id PK, scenario_id FK, kind, status, job_key, solver_version, result_json, audit_json, error_json, timestamps. |
| stress_runs | id PK, baseline_run_id FK, alternative_run_id FK, seed, case_count, status, results_json. |
| event_log | id PK, entity_type/id, event, timestamp, actor_label, safe_metadata_json. |

Use transactions for state changes and completed result/audit persistence. Results immutable after completion; edits create new scenario IDs. JSON columns acceptable for small prototype; no PHI. UTC ISO timestamps. Index run status and scenario_id. SQLite foreign keys enabled; use migrations, not implicit destructive schema resets. Exports include hashes, engine settings, result, audit and data provenance.

---
# 9. User experience and interface requirements

## 9.1 Visual direction
Professional civic analytics interface: deep navy, restrained teal, neutral surfaces, readable typography, consistent spacing, no excessive animation. Clear synthetic-data banner on every dataset-dependent view. Desktop-first responsive layout; mobile stacks panels. Use accessible contrast, keyboard navigation, focus states, labels and non-color status indicators. Provide skeleton/loading, empty, error and no-solution states. Charts include units and accessible data tables.

## 9.2 Screens and interactions
| Screen | Required content and behavior |
|---|---|
| Overview / | District card, model scope, demo banner, Start Scenario, previous run status. |
| Data Explorer /data | Dataset version, provenance, cluster demand, service capacity, schematic graph, validation warnings; no real operational coordinates. |
| Scenario Builder /scenarios/new | Budget, unit count, threshold, demand multiplier, equity floor, policy; optional language prompt; review summary and Confirm & Run. |
| Run /runs/[id] | Job stage, elapsed time, cancel action, solver status, errors and retry/new scenario. |
| Comparison /compare | Baseline vs alternative KPI cards, coverage chart, aggregate zone table, cost/equity trade-off, audit panel. |
| Stress Lab /stress | Seed, case count, assumptions, run status, interval chart, failure count, per-case table. |
| Report /reports/[id] | Printable executive summary, assumptions, metrics, limitations, solver/audit evidence, JSON/CSV downloads. |

## 9.3 Dashboard content hierarchy
Top: district, dataset version, 'SYNTHETIC DEMONSTRATION' badge and scenario controls. Next: coverage, served demand, unmet demand, average assigned travel, worst cluster coverage, additional cost. Center: side-by-side aggregate zone comparison and chart of coverage by cluster. Bottom: stress intervals, constraint audit and evidence references. For infeasible results, replace KPI comparison with a diagnostic panel; never imply a computed allocation. No unsupported impact badges or fake live data.

## 9.4 UX acceptance criteria
Given default dataset, planner can create scenario, confirm, run both modes, view metrics and export in one guided flow. Form invalid values show inline errors. Reload restores scenario/run from API. Browser back does not resubmit jobs. Disabled AI mode is visible but does not block form. Every result displays dataset type, solver status, time horizon, audit state and assumptions. For small screens (375px) controls remain usable without horizontal page scrolling, except intentionally scrollable tables.

---
# 10. Nonfunctional requirements, security and responsible use

| ID | Requirement / verification |
|---|---|
| NFR-01 | Local demo runnable via documented Docker Compose or native setup; no external network at runtime in template mode. |
| NFR-02 | Default solve <=10s and stress suite <=60s target; benchmark on stated hardware, report misses honestly. |
| NFR-03 | API schema strict; user input and uploads validated; bounded workloads; safe error responses. |
| NFR-04 | No patient-level data, exact private locations, staff schedules, or confidential operational records. |
| NFR-05 | Secrets server-side only; no keys in frontend, repo, logs or exports; .env ignored. |
| NFR-06 | Local bind by default; explicit CORS origin; production TLS/auth/RBAC required before non-demo remote access. |
| NFR-07 | Immutable dataset/run provenance, plan/result hashes, solver settings and audit trail. |
| NFR-08 | Accessibility: keyboard navigation, visible focus, labels and text alternatives for charts. |
| NFR-09 | On model/API failure, deterministic fallback; on solver failure, no fabricated result. |
| NFR-10 | Back up SQLite before schema migration; document restore and demo reset procedures. |

## 10.1 Threat model and controls
Prompt injection: treat imported data and user prompts as untrusted; never pass raw file contents as instructions; use schemas, allowlists and evidence validation. Malicious uploads: size cap, file extension/content validation, no executable content or arbitrary file paths. Cross-user exposure: P0 local-only; for P2 use real authentication, role checks on every object and per-tenant storage policies. Resource exhaustion: enforce dataset caps (default 500 nodes, 200 communities, 100 sites, 5,000 edges, 20 stress cases), solver time limits and queue caps; return actionable errors. Export safety: escape CSV cells beginning with formula characters; sanitize HTML; no external script injection. Supply chain: pin dependencies, scan for vulnerabilities and update lockfiles deliberately.

## 10.2 Responsible planning and governance
Results are hypothetical decision support, not medical advice or government-approved allocations. Human stakeholders must validate actual demand, access assumptions and legal/operational feasibility. A fairness metric reflects chosen policy, not a guarantee of fairness; show worst-served clusters, unmet demand and trade-offs. Do not automatically deploy resources, publish sensitive routes or recommend immediate real-world actions. Allow users to inspect, challenge and reproduce results. No surveillance, identification or individual risk scoring.

---
# 11. Verification, test matrix and definition of done

## 11.1 Deterministic golden fixture
Two clusters A/B with demand 60/40. Existing E capacity 60, candidate N capacity 40, candidate cost 100, budget 100, max new units 1, T=30. Travel minutes: A-E=10, B-E=50, A-N=40, B-N=10. Coverage-first baseline: A->E 60, B unmet 40; covered 60%, served 60%, worst cluster 0%, mean assigned travel 10. Optimized: A->E 60 and B->N 40; covered/served 100%, worst cluster 100%, mean assigned travel 10, cost 100. Audit must pass. These are mathematical fixture expectations, not district statistics.

## 11.2 Acceptance test matrix
| Test | Expected result / requirements |
|---|---|
| T01 Golden fixture | Exact totals and constraints; FR-05/06/07. |
| T02 Zero budget / max units 0 | No positive-cost candidates, no overrun; FR-06. |
| T03 Disconnected graph | Unreachable assignments absent, demand unmet; FR-03/06. |
| T04 Capacity saturation | Served <= capacity; demand balance exact; FR-06/07. |
| T05 Impossible equity floor | Infeasible, no fake KPIs; FR-06/07. |
| T06 Duplicate/bad import | Reject transaction; row errors; FR-01/02. |
| T07 Tampered output | Independent audit fails; no publication; FR-07. |
| T08 Mismatched comparison | 409/422 and useful warning; FR-08. |
| T09 Stress reproducibility | Same cases from same seed; fixed selections; failure counts; FR-09. |
| T10 Offline and model failure | Core workflow succeeds; template fallback; FR-11/NFR-01/09. |
| T11 Parser injection / invalid JSON | Reject or manual fallback; no unintended action; FR-14. |
| T12 Export | Valid JSON/CSV, hash/provenance present, formula escaping; FR-12. |
| T13 Job state/cancel/restart | Terminal state correct; no unaudited result; FR-13. |
| T14 End-to-end browser | Seed -> confirm -> baseline/solve -> compare -> export; FR-01–13. |
| T15 Performance | Record machine, versions, time, status, dataset size; NFR-02. |
| T16 UI/accessibility | Keyboard flow, mobile layout, error and empty states; NFR-08. |

Use unit tests for math/validation, integration tests for API and DB, and E2E for the complete demo. Property-based tests may generate bounded small graphs to check conservation and nonnegativity. Run lint, type checks, unit/integration and E2E in CI. Aim >=80% domain test coverage, measure rather than invent. No skipped critical tests or mocked solver in golden/integration tests.

## 11.3 Release gate
P0 complete only when all P0 FRs pass, audit rejects corrupt allocations, demo runs offline, reproducible golden fixture matches, critical tests pass, README setup works on a clean environment, and benchmark report honestly records performance. Record open issues, limitations and actual screenshots. P1/P2 features are not required for P0 sign-off. No fake endpoints, placeholder KPI values, hidden TODOs in core workflow or claims of stakeholder validation.

---
# 12. Build plan, deployment and Codex handoff

## 12.1 Ordered implementation milestones
| Phase | Deliverable and gate |
|---|---|
| M0 Foundation | Repo, dependency locks, contracts, CI, demo generator, README. Seed and schema tests pass. |
| M1 Engine | Graph costs, baseline, CP-SAT, independent audit, metrics. Golden fixture and edge cases pass. |
| M2 Backend | SQLite migrations, scenario confirmation, jobs, API, export. Integration tests pass. |
| M3 Frontend | Scenario, data explorer, run status, comparison, report. E2E core path passes. |
| M4 Robustness | Stress tests, greedy benchmark, evidence templates, error states, accessibility. Benchmark recorded. |
| M5 Optional AI | Provider adapter, parser and review, evidence-controlled output. Offline unchanged; injection tests pass. |
| M6 Release | Clean setup, smoke tests, actual demo results, limitations, screenshots and pitch. |

Each phase must run its tests and record changed files, commands, actual results and blockers before starting the next. Do not start optional features before core engine and UI work. Scope may be reduced to P0; never misrepresent incomplete work.

## 12.2 Configuration and commands (contract to implement)
Create .env.example with API_HOST=127.0.0.1, API_PORT=8000, WEB_PORT=3000, DATABASE_URL=sqlite:///./data/civitwin.db, DEMO_MODE=true, AI_ENABLED=false, LLM_MODEL=, LLM_API_KEY=, SOLVER_TIMEOUT_SECONDS=10, STRESS_TIMEOUT_SECONDS=60. Do not commit real keys. Create Makefile targets setup, seed, dev, test, lint, e2e, benchmark, smoke, reset-demo (explicit confirmation), and compose equivalents. Document native Windows/PowerShell equivalents; don't require Make on Windows. Compose exposes web localhost:3000 and API localhost:8000; ensure frontend API URL works in both browser and container contexts. Persist DB in a named volume; seed idempotently. API health and readiness checked before frontend startup. Build must not require LLM credentials.

## 12.3 Deployment and operations
P0 local demo only by default; allow public read-only demonstration with synthetic data after security review, TLS and rate limiting. No publicly writable anonymous endpoints. CI runs backend + frontend checks, seeded integration tests and browser smoke test. Pin dependencies and reproducible container builds. Backup database and manifest; rollback to prior tagged release and compatible DB snapshot. Structured logs include request IDs, stage, elapsed time, status; no secrets or prompts with private content.

## 12.4 Codex execution contract
Place this SRS at docs/SRS.md and the supplied AGENTS.md at repo root. Instruct Codex to inspect the repository before editing, implement M0 first, run real tests, and proceed in small reviewable commits. It should use repository tools, not assume external API access; if dependencies are unavailable, report exact failure and do not claim success. Require an implementation checklist with FR/NFR/T IDs. Do not deploy, spend money, create accounts, expose secrets or upload data without explicit authorization. Use the model available in the user's environment; the SRS is model-agnostic.

---
# 13. Competition demo, risks and references

## 13.1 Three-to-five-minute demo flow
0:00–0:30: Explain aggregate service-accessibility problem and synthetic-data caveat. 0:30–1:00: Open dataset and show current modeled baseline. 1:00–1:45: Change budget and unit limit, review the structured plan, then run optimization. 1:45–2:30: Compare actual computed coverage, unmet demand, equity and costs; open audit details. 2:30–3:15: Run stress suite or show a precomputed, reproducible run; demonstrate uncertainty and failure cases. 3:15–4:00: Show optional AI parsing or the offline template; emphasize that solver, not LLM, computes outcomes. 4:00–4:30: Explain future data validation and expansion to Mohmand and Khyber. Use actual results from implementation, not sample numbers from application drafts.

## 13.2 Risks and mitigations
| Risk | Mitigation |
|---|---|
| Local data unavailable | Synthetic, clearly labeled inputs; stakeholder validation later. |
| Solver timeout or infeasibility | Bounded model, visible status, audited incumbents only; no invented recommendation. |
| LLM hallucination / injection | Restricted plan schema, confirmation, evidence-linked templates, offline fallback. |
| Scope creep | P0 first; no live maps, clinical features or multi-district production deployment. |
| Misleading fairness claim | Explain chosen metric, show unmet demand and alternative trade-offs. |
| Dependency/API issues | Lock dependencies; local-first runtime; model adapter optional. |
| Public exposure of sensitive data | Aggregate fictional demo only; governance gate before real inputs. |

## 13.3 Future 90-day pilot (conditional, not committed)
Days 1-30: secure stakeholder permission, validate aggregate data, define evaluation and governance. Days 31-60: calibrate model, compare with planner baselines, evaluate fairness and uncertainty, test language accessibility. Days 61-90: supervised planning trials, document feedback and decide whether expansion to Mohmand/Khyber is appropriate. No implementation in the real world without responsible authority approval.

## 13.4 References and implementation resources
- [R1] Pakistan Bureau of Statistics, 7th Population and Housing Census detailed results: https://www.pbs.gov.pk/census/
- [R2] Pakistan Bureau of Statistics, census Excel tables: https://www.pbs.gov.pk/result-excel/
- [R3] Google OR-Tools CP-SAT solver documentation: https://developers.google.com/optimization/cp/cp_solver/
- [R4] OR-Tools Python API reference: https://or-tools.github.io/docs/python/
- [R5] KPITB competition portal (application context supplied by user): https://aichallenge2026.kpitb.online/

The sources above establish data/technology starting points, not verified local healthcare capacity or project endorsement. Real data access, competition status, model/API availability and stakeholder partnerships are unverified. This SRS specifies a proposed system; it does not certify that implementation has started or that a competition result is guaranteed.
