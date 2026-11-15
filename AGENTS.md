# CIVITWIN AI — Codex implementation instructions

Read `docs/SRS.md` completely before writing code. It is the source of truth. This is a local-first synthetic civic planning prototype, not a medical or operational system.

## Operating rules
- Inspect the repository first. Preserve existing work. If empty, scaffold according to SRS §3.3.
- Implement milestones M0 through M4 in order, then optional M5 and release M6. Keep a living `docs/IMPLEMENTATION_STATUS.md` with requirement IDs, milestone status, files changed, real test commands/results and blockers.
- Never invent data, screenshots, evaluation results, test passes, partner commitments or model IDs. Clearly mark synthetic demo data. Do not add actual patient records or precise operational locations.
- Core numerical results must come from the optimizer and independent verifier, not an LLM. Follow the equations, units and lexicographic semantics in SRS §5. Check the golden fixture before building UI.
- Make AI optional, disabled by default. Use typed PlanSpec, explicit user confirmation, evidence packet and deterministic fallback. Never give a model arbitrary tools or DB access.
- Do not deploy, upload data, incur charges, provision accounts or use credentials without explicit authorization. Do not expose local services beyond localhost by default.
- Install compatible dependencies and commit lockfiles when environment permits. If commands fail or network is unavailable, report actual errors. No placeholder implementations in P0.
- Keep user interface truthful: every result shows dataset type, assumptions, solver status and audit. Infeasible or timed-out results must not become fabricated successes.

## Work sequence
1. M0: scaffold, data contract, deterministic fixture generator, lint/test CI, docs.
2. M1: pure domain engine, exact golden fixture, audit and metric tests. No frontend until this gate passes.
3. M2: database migrations, API contracts, jobs and export. Test persistence and invalid cases.
4. M3: real end-to-end frontend, responsive states and API integration. No fake dashboard data.
5. M4: uncertainty stress suite, greedy benchmark, evidence report and acceptance tests.
6. M5: optional AI parser and constrained explanation; test failure and injection paths.
7. M6: run clean setup, test, lint, E2E, smoke and benchmark; deliver actual results, known limitations and demo instructions.

## End-of-phase response
Summarize implemented features, FR/NFR/T IDs satisfied, changed files, exact commands run, real results, remaining issues and next phase. Do not claim completion if tests were not run. Ask for user input only when a genuine blocking decision or permission is needed.
