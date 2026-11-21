# CIVITWIN AI implementation status

The workspace initially contained AGENTS.md and the complete SRS, both byte-identical to the supplied copies. It had no Git metadata. The SRS is the source for the gates below. The prototype models one synthetic week in Bajaur. Mohmand and Khyber are future expansion districts.

| Milestone | Status | Acceptance gate |
| --- | --- | --- |
| M0 Foundation | Passed locally | Reproducible dependency locks, schema and demo generation tests, lint and CI wiring |
| M1 Engine | Passed locally | Exact golden fixture and edge cases with independent audit |
| M2 Backend | Passed locally | Migrations, persistent job lifecycle, strict API and export integration tests |
| M3 Frontend | Passed locally | Guided baseline, solve, compare and export through a real browser |
| M4 Robustness | Passed locally | Paired uncertainty, greedy benchmark, evidence and accessibility tests |
| M5 Optional AI | Passed locally with provider fixtures | Reviewed typed drafts, evidence-controlled narration, failure and injection tests |
| M6 Release | Passed on native Windows | Clean setup, smoke, lint, tests, E2E, benchmark, screenshots and demo handoff |

## Requirement checklist

| ID | Milestone | Implementation and verification |
| --- | --- | --- |
| FR-01 | M0, M2, M3 | Immutable dataset contract, hash, registry and explorer. T06, T14. |
| FR-02 | M0, M2 | Strict JSON and CSV bundles, row errors and atomic publish. T06. |
| FR-03 | M1, M3 | Shortest paths, unreachable pairs and explorer visibility. T03. |
| FR-04 | M0, M2, M3 | Strict PlanSpec, dataset limits and reviewed scenario form. T14. |
| FR-05 | M1 | Existing-only assignment with the same policy. T01. |
| FR-06 | M1 | Integer CP-SAT with lexicographic stages and bounded runtime. T01–T05. |
| FR-07 | M1, M2 | Independent audit and fail-closed publication. T01, T04, T07. |
| FR-08 | M2, M3 | Match dataset and plan hashes and compare audited results. T08, T14. |
| FR-09 | M4 | Seeded paired stress cases with fixed selections and recorded failures. T09. |
| FR-10 | M3, M4 | Defined metrics, audit, solver stage, provenance and evidence identifiers. T14, T16. |
| FR-11 | M3, M4, M5 | Offline evidence templates and optional controlled paraphrase. T10. |
| FR-12 | M2, M3 | JSON, escaped CSV and print-friendly report with reproducibility metadata. T12, T14. |
| FR-13 | M2, M3 | Persist immutable run history, cancellation, timeout and restart behavior. T13, T14. |
| FR-14 | M5 | Optional restricted parser with explicit review, language validation and injection checks. T11. |
| FR-15 | P1 | Three-policy comparison. Outside the P0 release gate. |
| FR-16 | P2 | Authenticated multi-user dataset and role management. Future pilot. |
| NFR-01 | M0, M6 | Locked local setup and offline core workflow. T10, T14. |
| NFR-02 | M4, M6 | Measure default solve and 20 paired cases against §1.3. T15. |
| NFR-03 | M0, M2 | Bound input, upload and workload sizes with safe errors. T02, T06, T13. |
| NFR-04 | M0, M6 | Aggregate fictional fixture and synthetic labels throughout. T14. |
| NFR-05 | M0, M5 | Ignore local secrets and configure optional providers server-side. T10, T11. |
| NFR-06 | M2, M6 | Local-only defaults, explicit CORS and local deployment instructions. T13. |
| NFR-07 | M0–M4 | Hashes, immutable results, provenance, solver settings and event history. T06, T07, T12, T13. |
| NFR-08 | M3, M4 | Keyboard, focus, data alternatives and mobile flow. T16. |
| NFR-09 | M1, M2, M5 | Explicit non-solution states and deterministic AI fallback. T05, T10, T11. |
| NFR-10 | M2, M6 | SQLite backup, migration and restore procedures. T13. |

## Acceptance test gates

| Test | Gate | Acceptance check |
| --- | --- | --- |
| T01 | M1 | Golden totals, costs, assignments and audit checks |
| T02 | M1 | Zero budget and unit limits |
| T03 | M1 | Directed/disconnected reachability |
| T04 | M1 | Capacity saturation and exact balance |
| T05 | M1 | Infeasible equity floor and absent metrics |
| T06 | M0, M2 | Duplicate/invalid imports and transactional rejection |
| T07 | M1, M2 | Corrupt serialized result rejected before publication |
| T08 | M2 | Incompatible hashes produce a conflict |
| T09 | M4 | Same seed, paired perturbations and fixed activation |
| T10 | M4, M5 | Core offline flow and model failure fallback |
| T11 | M5 | Invalid JSON, injection and no unintended actions |
| T12 | M2 | Valid hashed provenance exports and safe CSV |
| T13 | M2 | Confirmation, lifecycle, cancellation and interrupted restart |
| T14 | M3, M6 | Guided browser flow through export |
| T15 | M4, M6 | Documented runtime, machine, versions and solver status |
| T16 | M3, M4 | Keyboard, mobile, error and empty states |

## Architecture and gate handoffs

- M0 publishes frozen typed inputs, canonical dataset and plan digests, deterministic seed artifacts and separate malformed/disconnected fixtures. Solver tests consume the same public contracts as the API.
- M1 models a single week using integer assignment and activation decisions. Its public output contains auditable allocation rows, stage statuses, metrics and hashes. The verifier reconstructs accounting from serialized rows and authoritative input.
- M2 owns the confirmation, queuing, cancellation and result publication transactions. An audited result and its event record are written together. A bounded local executor owns jobs in the API process, with interruption recorded on restart.
- M3 consumes persisted identifiers and displays the same dataset and confirmed plan beside each result. Report and comparison views use the typed run snapshot. The schematic graph uses generated positions from the seed contract.
- M4 fixes the selected candidate sets across paired perturbations, then reassigns visits. The greedy comparator uses the same assignment rules. All numeric explanation fields come from audited evidence.
- M5 can suggest typed drafts or select supported evidence statements. Confirmation and mathematical results remain in deterministic services. A provider requires explicit local configuration.

## M0 work log

- Read the repository instructions and SRS in full and verified their SHA-256 matches against the attached copies.
- Inspected the native toolchain. Python 3.11.9, uv 0.13.1, Node 24.19.0 and npm 11.17.0 are available. Docker and Make did not appear in the command inventory.
- Added `pyproject.toml`, `uv.lock`, `.gitignore`, `.env.example`, `Makefile`, `README.md` and this checklist.
- `uv sync --no-progress` in the sandbox failed with Windows socket error 10013 connecting to PyPI. The approved retry resolved 46 packages and installed 43 for Windows/Python 3.11.
- `uv lock --check --offline` passed. `uv run --locked --no-sync python -c 'import ortools, fastapi, networkx, numpy; print(ortools.__version__, fastapi.__version__, networkx.__version__, numpy.__version__)'` confirmed 9.15.6755, 0.162.6, 3.6.1 and 2.4.6.
- Initializing Git under the sandbox prevented subsequent Windows sandbox process creation. Moving the empty metadata aside restored command execution. Lockfiles remain in the workspace for version control.
- Added `services/api/app/schemas/{dataset,plan}.py`, `services/api/app/domain/{dataset,dataset_import}.py`, package markers, `scripts/seed.py`, `data/demo/{README.md,bajaur-v1.json}`, `data/schemas/{README.md,dataset.schema.json,plan.schema.json}`, and `services/api/tests/{unit/test_dataset_contracts.py,fixtures/disconnected.json}`.
- `uv run --locked --no-sync python scripts/seed.py --check` verified the generated synthetic data and schemas. `uv run --locked --no-sync pytest` passed 14 tests in 0.32s, including the input-validation portion of T06. The initial Ruff command included the in-workspace dependency cache. After excluding local caches, `uv run --locked --no-sync ruff check .` passed and `uv run --locked --no-sync ruff format --check .` verified 16 files. `uv run --locked --no-sync mypy` passed for 7 application files.
- Implemented and verified the contract portions of FR-01, FR-02, FR-04, NFR-03, NFR-04 and NFR-07. API persistence and workflow acceptance are assigned to later gates.
- `uv run --locked --no-sync coverage run -m pytest` and `uv run --locked --no-sync coverage report -m` passed. Coverage was 87% for the M0 domain files.
- Added the root npm workspace and lock, Next.js, Tailwind, TypeScript, ESLint, Vitest, Playwright configuration, the fixture consumption test, and `.github/workflows/checks.yml`. CI is configured and local equivalents ran. The hosted workflow has not run.
- Sandbox npm registry access returned EACCES. The approved `npm install --no-audit --no-fund --cache E:\CIVITWIN-AI\.npm-cache --fetch-retries 1` added 441 packages and wrote `package-lock.json`. npm reported ESLint 9 as deprecated. After fixing the PostCSS export and the Pages Router lint setting, `npm run lint:web`, `npm run typecheck:web` and `npm run test:web` passed. Vitest passed 1 test and emitted a config-format migration warning.

## M1 work log

- Added the directed shortest-path matrix and cache, integer CP-SAT model, audit and metric records, independent metric and constraint reconstruction, and golden, saturated and disconnected tests. Main files are `services/api/app/domain/{travel,optimizer,results,metrics,audit}.py`, `scripts/seed.py`, and `services/api/tests/{unit,fixtures}/`.
- `uv run --locked --no-sync pytest` passed the first 24 tests, including exact golden totals, infeasibility, disconnection, capacity saturation, pre-cancellation and shared lexicographic deadline behavior.
- A direct native engine run recorded 1,320/2,598 modeled visits within threshold at PKR 0 for the baseline, and 1,853/2,598 at PKR 267,000 for the alternative (N01 and N06). Both reached OPTIMAL and passed audit. The invocation took 172 ms and 1,657 ms respectively. These are synthetic outputs from a single local invocation. M4 runs the benchmark protocol.
- The final gate used `.venv/Scripts/python.exe -m coverage run -m pytest -q` (37 passed in 4.28s), `-m coverage report` (89% domain coverage), `-m mypy services/api/app` (12 source files), `scripts/seed.py --check`, and the venv Ruff executable with `check services scripts` and `format --check services scripts`. All passed. FR-03 and FR-05–07 engine checks passed, including T01–T05 and T07. M2 verifies transactional publication.

## M2 work log

- Added FastAPI routes and safe error envelopes, SQLite/Alembic storage, immutable synthetic imports, hash confirmation, bounded idempotent jobs, independent-audit publication, restart recovery, comparison, JSON and escaped CSV. Files include `services/api/app/{main,config,errors}.py`, `app/{db,workflows,schemas}/`, `app/domain/comparison.py`, `services/api/migrations/` and `services/api/tests/integration/`.
- `.venv/Scripts/python.exe -m pytest --basetemp .pytest_cache/m2-resume -q --tb=short` passed 49 tests. The alternate test temp path avoids Windows WinError 5 on the shared host temp directory. Starlette emitted a TestClient dependency deprecation warning.
- `.venv/Scripts/ruff.exe check .`, `.venv/Scripts/ruff.exe format --check .` (39 files) and `.venv/Scripts/python.exe -m mypy` (23 application files) passed.
- API acceptance covers FR-01/02/04/07/08/12/13 and T06/T08/T12/T13. HTML reporting and visual provenance are M3. Stress and greedy routes are M4.

## M3 work log

- Added the Next.js workspace, responsive sidebar and overview, interactive schematic, data explorer, scenario form and review, saved run monitoring, comparison and printable report. Changed `apps/web/`, root npm manifests, `playwright.config.ts`, `tests/e2e/`, the README and CI.
- `npm run lint:web`, `npm run typecheck:web` and `npm run test:web` passed. Browser command `npm run e2e` with workspace Chromium passed 3 tests in 3.5 minutes. Verified confirmed runs, back/reload persistence, audited comparison, downloads, infeasible diagnostics, and 375px planner layout. This locally verifies the M3 parts of T14 and T16.
- An optimized build run concurrently with Next dev failed with TS6053 because Next regenerated shared type files during the build. Run production build and browser acceptance sequentially for release. Additional mobile comparison and actual Tab checks are queued for the expanded browser gate.
- The sequential `npm run build:web` passed, including TypeScript and static generation.

## M4 work log

- Added fixed-selection stress trials, a capacity-aware greedy comparator, immutable evidence packets, and persisted stress jobs. Changed `services/api/app/{domain,workflows,ai}/`, API schemas/routes, Stress Lab and report views, acceptance tests, and `scripts/benchmark.py`.
- `.venv/Scripts/python.exe -m coverage run -m pytest --basetemp .pytest_cache/m4-gate -q --tb=short` passed 63 tests in 48.96s. `coverage report` recorded 89% domain coverage. Ruff lint and formatting and mypy (27 application files) passed.
- Real Playwright run passed. Its artifacts include overview, comparison, report, 375px scenario and stress screenshots. The core browser path exercises stress submission, audited paired cases and persisted reload. FR-09/10/11, T09/T10/T14/T16 and the benchmark portion of T15 passed locally.
- `scripts/benchmark.py` recorded 15 scenarios in [benchmark-results.json](benchmark-results.json), including the budget × unit grid, positive equity, disconnected and saturated cases. On the recorded Windows machine, the default optimized solve took 1,547 ms. The 20-pair stress suite took 6,129 ms. All 44 published benchmark allocations and all 20 stress pairs passed audit. One benchmark allocation returned `NO_SOLUTION`.

## M5 work log

- Implemented typed drafts, explicit form review, a server-only provider adapter, constrained claim selection and offline fallback in `services/api/app/ai/`, API configuration/routes, and the web planner and report. Added parser, evidence, integration and browser tests. The data explorer also supports validated local synthetic bundle imports.
- `.venv/Scripts/python.exe -m pytest --basetemp .pytest_cache/m5-ai services/api/tests/unit/test_plan_parser.py services/api/tests/unit/test_evidence.py services/api/tests/integration/test_api.py -q --tb=short` passed 59 tests. Ruff, formatting, mypy, web lint, typecheck and Vitest passed. `npx playwright test tests/e2e/optional-ai.spec.ts` passed with a simulated provider draft and real scenario creation.
- FR-11/14, NFR-05/09 and T10/T11 passed with controlled provider responses. The 20 labeled English parser fixtures cover 14 expected drafts and 6 expected refusals or clarifications. Live model accuracy and native-speaker review of Urdu/Pashto require separate evaluation.

## M6 release verification

- Added `scripts/dev.py`, `scripts/smoke.py`, `scripts/reset_demo.py`, a transactional recovery test, the Makefile targets, `compose.yaml`, `infra/Dockerfile`, `.dockerignore`, request timing logs, CI coverage/smoke checks, native/container setup and the [competition walkthrough](DEMO.md).
- Fresh local clone on Windows, with empty Python and Node dependency directories: `uv sync --locked --offline --python 3.11` installed 43 packages and `npm ci --offline --no-audit --no-fund` installed 436 packages using previously populated local download caches.
- `.venv/Scripts/python.exe -m coverage run -m pytest -q --tb=short` passed 111 tests in 27.79 seconds. `python -m coverage report --fail-under=80` reported 89% branch-inclusive domain coverage. A first attempt using a nested custom temp path failed to create the missing parent directory. The normal pytest invocation passed. The README explains how to create that directory for restricted Windows environments.
- `python scripts/smoke.py` completed a native offline scenario, confirmed plan hashes, independently audited both allocations, checked the comparison and read JSON/CSV after reopening SQLite. The reset recovery test passed with an isolated database. It verified cancellation, republishing the seed and recovering the prior dataset from backup.
- Docker Compose v5.8.0 accepted `--profile qa config --quiet`. Runtime verification on this host is unavailable: the Windows Docker Engine named pipe does not exist. The native workflow is the verified release path.
- Ruff lint and format passed for 56 files, mypy passed for 30 application modules, and `python scripts/seed.py --check` reproduced the tracked seed and schemas. Web lint, TypeScript, Vitest (1 test) and the Next.js production compilation passed locally.
- OSV-Scanner 2.7.1 initially found GHSA-g3hv-75wg-m249 affecting the development dependency minimatch 10.2.6. Updated the typescript-eslint dependency family to 8.73.0 using `npm update typescript-eslint --package-lock-only --ignore-scripts --no-audit --no-fund`. The offline rescan of 45 Python and 527 npm lockfile entries returned zero findings on November 20, 2026. Command: `osv-scanner scan source --offline --lockfile uv.lock --lockfile package-lock.json`. Advisory databases were downloaded locally. [OSV offline scanning](https://google.github.io/osv-scanner/usage/offline-mode/)
- The [release benchmark](release-benchmark.json) records the fresh-checkout run of `python scripts/benchmark.py --output test-results/release-benchmark.json`. The default optimized solve took 765 ms. The 20-pair suite took 7,720 ms and all pairs completed. Across the 15 benchmark scenarios, all 43 published allocations passed independent verification. One zero-budget baseline timed out during this run and the 20% equity-floor baseline was infeasible. Both terminal states are retained in the benchmark.
- The final npm lock installed 437 packages with `npm ci --offline --no-audit --no-fund`. Cold startup on this disk exceeded the original test web-server and native API readiness deadlines. The launcher now waits up to 120 seconds for API readiness and Playwright allows 240 seconds for the frontend to start. The native launcher served the overview and same-origin readiness endpoint at 127.0.0.1 with AI disabled.
- Browser acceptance initially found a test locator that also matched Next.js’s route announcer. The assertion now matches the visible import error. Release review also added demand-weighted zone totals alongside community coverage and a check that the zone counts sum to the audited district counts. The [walkthrough and screenshots](DEMO.md) use the running application.

### Remaining scope

Release sign-off for the native Bajaur demonstration was recorded on November 21, 2026. The final clean-checkout sequence `npm run lint:web`, `npm run typecheck:web`, `npm run test:web`, `npm run e2e`, and `npm run build:web` exited successfully. All five Chromium tests passed in 2.6 minutes. The browser run exercised the offline solver-to-report workflow, zone reconciliation, stress outcomes, download, keyboard/mobile use, an infeasible scenario, reviewed optional AI drafts and synthetic import. The requirements tables and milestone logs above map this evidence to G1–G7, FR-01–14, NFR-01–10 and T01–T16.

The native release covers the P0 workflow (FR-01 through FR-13). FR-14 has controlled provider and browser tests. Live model quality, Urdu/Pashto speaker review, FR-15 alternate objective policies and FR-16 multi-user access remain future work. The single-process job manager and synthetic local data are intended for the competition demonstration. Hosted CI and container execution still require their respective runtimes.

## Impact Studio MVP integration

- Checked out the existing feature branch for [PR #1](https://github.com/ahmadalihamza/CIVITWIN-AI/pull/1) from commit `698848c`. The initial working tree was clean. The planner database and local configuration were preserved.
- Identified and stopped the workspace's Next.js process tree before the Windows reinstall. `npm ci --no-audit --no-fund` installed 437 packages and the Next.js entry-point check returned `True`. `uv sync --locked --python 3.11` checked 43 packages. Verified Python 3.11.9, Node.js 24.19.0, npm 11.17.0 and uv 0.13.1.
- Impact Studio now previews the exact plan before confirmation, retains links to queued runs and displays audit and solver status for both allocations. The shared network renders audited coverage and weekly visit changes, and the Studio summarizes selected facility costs and loads. The explanation identifies the largest gains and losses in the selected zone and links to the full evidence. The three existing missions reuse the same solver and REST API. Fairness trade-offs are shown through the Equity Lens and optional coverage floor.
- Updated the [three-minute presentation](IMPACT_STUDIO.md), README and Playwright scenarios. This work exercises FR-03–08, FR-10–13, NFR-01/08/09 and T05/T07/T10/T12–14/T16.
- `uv run --locked pytest` passed 111 tests. `uv run --locked ruff check .` and `uv run --locked mypy` passed. `uv run --locked python scripts/smoke.py` verified 533 added covered visits for the synthetic default plan, audited results and export after reopening the database.
- `npm run lint:web`, `npm run typecheck:web`, `npm run test:web` (one test), and `npm run build:web` passed. A first browser run detected overflow in completed Studio results at 375 pixels. After the map controls and result grid were fixed, the production build and all eight `npm run e2e` Chromium tests passed. The updated suite checks exact confirmation, both reported audits, site markers, community counts, mobile results, report navigation and an infeasible baseline.
- An isolated API rehearsal using the smoke-test helper completed both audited allocations for the other two presets. Demand surge covered 1,853 of 3,252 visits versus 1,320 with existing facilities. Tough budget choice covered 1,555 of 2,598 versus 1,320 and spent PKR 115,000 per modeled week.
