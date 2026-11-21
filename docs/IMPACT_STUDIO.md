# CIVITWIN AI: Impact Studio MVP

## What judges can do
Open http://127.0.0.1:3000/studio in the local planner. Select one of three policy missions: access expansion, a 25% increase in synthetic weekly demand, or a tighter weekly unit budget. Adjust the visible budget, number of mobile units, travel-time threshold and demand sliders. Optionally specify an equity coverage floor; explain that this can make a baseline infeasible. Press **Run verified simulation**.

The page creates a normal persistent scenario, confirms its plan hash and solves the **baseline** with existing sites. Only after the audited baseline finishes does it solve the **optimized alternative**. Any failure is shown, not replaced with invented results.

The result dashboard computes the coverage delta, additional served visits, cost, and worst-community metric from audited API results. The Equity Lens groups community allocations into fictional Valley, Foothill and Ridge zone classes and shows which communities gained or lost weekly modeled visits. The Ask the Evidence section answers preset questions from these computed fields and documented model rules, not AI-generated unsupported assertions. The user can open the full comparison and report to inspect hashes and independent audits.

## Demo flow (approximately 90 seconds)
1. Explain that district planning involves hard trade-offs between budget, accessibility and fairness.
2. Show the **Reach the overlooked** mission and its default settings.
3. Press **Run verified simulation** and discuss the real baseline and optimized outcomes.
4. Open **Who gains and who gives up access** to show that total improvement does not mean everyone benefits.
5. Ask **Is it fair?**, then open **Full evidence report** to demonstrate traceability.
6. Select the **Demand surge** mission to show that the same engine handles new assumptions. If time permits, run it.

## Important restrictions
- All values, node positions, service sites and travel links in the Bajaur sandbox are synthetic. They do not represent real facility locations, demand, costs or actual coverage.
- Before a new run, 50.8% → 71.3% is a *previously recorded audited example*. It is not computed from the current sliders.
- The current deterministic policy is "coverage first"; this is not a multi-policy or autonomous agent system.
- The fixed-capacity model is for planned, non-emergency outpatient visits, not clinical triage or individual diagnosis.
- Better overall modeled coverage can reduce allocations for some previously served communities. Show both gains and losses.
- Real geographic data, provider integration, and domain validation are necessary before operational decisions.
- For live simulations, start the API and Next.js app using README instructions. The static GitHub Pages demo is a separate recorded walkthrough.

## Engineering verification
Run npm run lint:web, npm run typecheck:web, npm run build:web, and npm run e2e. The new browser test covers a real baseline/optimized solve and a 375px mobile check. Keep the existing solver and audit tests unchanged.
