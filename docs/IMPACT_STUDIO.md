# Impact Studio competition demo

Start the project using the [local setup](../README.md#quick-start) and open [Impact Studio](http://127.0.0.1:3000/studio). The page evaluates one synthetic Bajaur week with fictional communities, sites, demand, capacity, cost and travel times.

## Three-minute presentation

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:30 | Open Impact Studio from the dashboard. | “A planner with a limited budget has to decide where extra capacity will cover the most visits. CIVITWIN shows who gains and who loses under the same assumptions. We use a synthetic Bajaur network to demonstrate the method.” |
| 0:30–1:05 | Choose **Reach the overlooked**. Review the PKR 300,000 weekly cap, two-unit limit and 45-minute threshold. Select **Review simulation plan**, then **Confirm and run both allocations**. | “The baseline uses the existing facilities. The alternative can open eligible candidates. Both runs use the same travel, demand and equity assumptions.” |
| 1:05–1:55 | Compare covered and unmet visits. Switch the schematic between existing sites, optimized plan and change. Select a community and inspect its counts. | “The solver chooses the sites and assigns weekly visits within the available capacity. The Equity Lens ranks gains and losses. A higher district total can still come with a loss for a community.” |
| 1:55–2:30 | Open **Why these sites?** and the **Full evidence report**. Show solver status, audit and downloads. | “The independent verifier checks eligible sites, travel, budget, capacity, equity and demand balance. The evidence shows what this allocation achieved. Testing an unselected combination would require another solve.” |
| 2:30–3:00 | Return to Impact Studio and select **Demand surge**, then **Tough budget choice**. | “The surge preset raises weekly demand by 25%. The tighter budget preset allows one new unit and caps spending at PKR 150,000 per week. The same solver evaluates each confirmed plan.” |

## What powers the results

- **Optimization.** OR-Tools CP-SAT chooses and assigns eligible sites. The independent verifier checks the published allocation. `FEASIBLE` indicates an audited allocation for which the solver has yet to prove optimality.
- **Evidence.** Impact Studio formats metrics, site assignments and community changes from both audited results. A failed baseline keeps its saved run available for inspection.
- **Optional AI.** The Scenario Builder can draft inputs with a configured provider. The planner reviews that draft before confirmation. Impact Studio, the solver and the default explanations work offline.
- **Public demo.** GitHub Pages shows recorded benchmark scenarios. Use the local app for live simulation, saved plans and exports. [Open the recorded walkthrough](https://ahmadalihamza.github.io/CIVITWIN-AI/)

## Verified rehearsal results

| Mission | Weekly demand | Covered visits with existing sites | Covered visits after optimization | Additional weekly cost |
| --- | ---: | ---: | ---: | ---: |
| Reach the overlooked | 2,598 | 1,320 | 1,853 | PKR 267,000 |
| Demand surge | 3,252 | 1,320 | 1,853 | PKR 267,000 |
| Tough budget choice | 2,598 | 1,320 | 1,555 | PKR 115,000 |

These are audited runs with the default mission settings. Demand surge increases requests while site capacity stays fixed, so the same 1,853 covered visits meet a smaller share of weekly demand.

## Local verification

Run `npm run e2e` with installed Playwright Chromium. The Studio tests check mission presets and slider inputs, explicit confirmation, the audited baseline and optimized runs, map states, report navigation, mobile layout and the infeasible baseline diagnostic. The broader suite exercises the existing planner, comparison, Stress Lab, imports, optional AI and exports.
