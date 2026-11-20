import type { PlanSpec } from "@/lib/types";
import styles from "./planning.module.css";

const number = new Intl.NumberFormat("en-PK");

export function PlanAssumptions({ plan }: { plan: PlanSpec }) {
  const properties = [
    ["Budget", `PKR ${number.format(plan.budget_pkr)} / week`],
    ["Maximum new units", number.format(plan.max_new_units)],
    ["Coverage threshold", `${number.format(plan.threshold_minutes)} minutes`],
    ["Demand multiplier", `${plan.demand_multiplier_pct}%`],
    ["Equity floor", `${plan.equity_min_pct}%`],
    ["Policy", "Coverage first"],
    ["Solver seed", number.format(plan.seed)],
    ["Time horizon", "One modeled week"],
  ];

  return (
    <dl className={styles.description}>
      {properties.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
