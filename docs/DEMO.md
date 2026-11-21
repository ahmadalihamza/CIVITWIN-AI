# CIVITWIN AI competition demo

**How much weekly demand can a fixed budget cover, and which communities still receive less service?** This demo answers that question for a fictional Bajaur dataset. Every demand value, travel time, site, and cost is synthetic. The schematic shows modeled connections. Real district use requires permission and validated aggregate inputs.

Start the native planner using the [setup instructions](../README.md). Keep AI disabled. Open the overview, then use the following sequence for a four-and-a-half-minute presentation.

| Time | Action | What to show |
| --- | --- | --- |
| 0:00–0:30 | Open Overview, then Data Explorer. | The seed has 24 community clusters, five existing sites, eight candidate zones and 2,598 requested visits per modeled week. Select a cluster on the schematic and inspect its demand. |
| 0:30–1:15 | Open Scenario Builder. Set PKR 300,000/week, at most two new units, 45 minutes, 100% demand and 0% minimum coverage. Review the plan and confirm. | The saved plan fixes the assumptions for both runs. The modeled baseline allocates visits using existing capacity. |
| 1:15–2:15 | Run the optimized alternative and open Comparison. | The recorded default solve selected N01 and N06 for PKR 267,000/week. Within-threshold coverage rose from 1,320 to 1,853 visits. Show unmet demand and the average travel trade-off alongside coverage. |
| 2:15–2:45 | Open the audit and inspect the zone or cluster table. | Existing and selected sites have finite capacity. The verifier independently checks assignments, demand balance, travel eligibility, policy and budget before publishing metrics. |
| 2:45–3:30 | Open Stress Lab. Use seed 2026 and 20 paired cases. | The selected sites stay fixed while weekly demand and travel vary. Read the number of successful pairs and failures before describing the interval. |
| 3:30–4:00 | Open the report, expand the evidence and download JSON or CSV. | Follow a claim back to an audited field. The report works offline. The JSON carries dataset, plan and result provenance. |
| 4:00–4:30 | Explain the next validation step. | Stakeholders would need to validate demand, road costs, capacity and the equity policy. Mohmand and Khyber are candidate expansion districts. |

## Recorded example

| Weekly metric | Modeled baseline | Optimized |
| --- | ---: | ---: |
| Visits within 45 minutes | 1,320 (50.81%) | 1,853 (71.32%) |
| Unmet visits | 1,278 | 745 |
| Worst cluster coverage | 0.00% | 70.89% |
| Mean assigned travel | 10.24 min | 17.36 min |
| Additional cost | PKR 0 | PKR 267,000 |

The alternative covered 533 additional visits per week and mean assigned travel increased by 7.12 minutes. The zone table shows who gained and who lost coverage in this modeled allocation. Ridge rose from 0 to 634 covered visits out of 891, while Valley fell from 741 to 568 out of 794. [Audited run comparison](screenshots/comparison.png)

In the recorded 20-case sensitivity analysis, alternative coverage ranged from 55.28% to 89.34%. The median was 65.84%. All 20 pairs completed. These figures describe sensitivity to the specified synthetic perturbations. [Benchmark inputs, objective stages and results](benchmark-results.json)

For an infeasibility demonstration, create a separate scenario with a one-minute threshold and a 100% equity floor. Inspect the baseline diagnostic. The run history retains its solver status.

## Screenshots from the running demo

| View | Evidence |
| --- | --- |
| [Planning overview](screenshots/overview.png) | Seed counts, schematic network and dataset manifest |
| [Mobile scenario builder](screenshots/scenario-mobile.png) | Planning controls at 375 pixels wide |
| [Allocation comparison](screenshots/comparison.png) | Modeled baseline and alternative on the same weekly demand |
| [Stress Lab](screenshots/stress.png) | A three-pair browser run with per-case audit states |
| [Printable report](screenshots/report.png) | Solver outcome, assumptions, audit and export controls |
