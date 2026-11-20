export interface DatasetManifest {
  id: string;
  version: string;
  district_label: string;
  is_synthetic: boolean;
  source_url: string | null;
  source_date: string;
  license: string;
  sha256: string;
  assumptions: string[];
  model_scope: string;
  schema_version: number;
  provenance: {
    entity: string; field: string; source: string; method: string; timestamp: string; caveat: string;
  }[];
}

export interface Dataset extends DatasetManifest {
  nodes: { id: string; label: string; display_x: number; display_y: number }[];
  edges: { from_node: string; to_node: string; minutes: number; direction: string }[];
  communities: {
    id: string; label: string; node_id: string; zone_class: string;
    demand_visits_per_week: number; population: number | null;
  }[];
  sites: {
    id: string; label: string; node_id: string; type: "existing" | "candidate";
    capacity_per_week: number; fixed_cost_pkr: number; eligible: boolean;
  }[];
  reachable_pair_count: number;
  unreachable_pair_count: number;
}

export interface PlanSpec {
  dataset_version_id: string;
  budget_pkr: number;
  max_new_units: number;
  threshold_minutes: number;
  demand_multiplier_pct: number;
  equity_min_pct: number;
  policy: "coverage_first";
  seed: number;
}

export interface Scenario {
  scenario_id: string;
  plan: PlanSpec;
  plan_hash: string;
  status: "VALIDATED" | "CONFIRMED";
  created_at: string;
  confirmed_at: string | null;
}

export interface ClusterMetrics {
  community_id: string;
  demand_visits: number;
  served_visits: number;
  unmet_visits: number;
  covered_visits: number;
  coverage_pct: number | null;
}

export interface Metrics {
  total_demand: number;
  served_visits: number;
  unmet_visits: number;
  covered_visits: number;
  visit_minutes: number;
  served_rate_pct: number;
  unmet_rate_pct: number;
  coverage_pct: number;
  mean_assigned_travel_minutes: number | null;
  worst_cluster_id: string;
  worst_cluster_coverage_pct: number;
  equity_gap_pp: number;
  cost_pkr: number;
  budget_pkr: number;
  budget_utilization_pct: number | null;
  clusters: ClusterMetrics[];
}

export interface Result {
  run_id: string;
  scenario_id: string;
  kind: "baseline" | "optimized" | "greedy";
  status: "COMPLETED";
  solver_status: "OPTIMAL" | "FEASIBLE";
  dataset_sha256: string;
  plan_hash: string;
  selected_candidate_ids: string[];
  assignments: { community_id: string; site_id: string; visits: number }[];
  unmet_by_community: { community_id: string; visits: number }[];
  metrics: Metrics;
  objective_stages: {
    objective: string; direction: string; status: string; value: number | null; best_bound: number | null;
  }[];
  audit: {
    passed: boolean; result_hash: string;
    checks: { id: string; passed: boolean; expected: unknown; actual: unknown }[];
  };
  warnings: string[];
  runtime_ms: number;
  model_version: string;
  solver_settings: { solver_version: string; seed: number; worker_count: number; time_limit_seconds: number };
}

export interface FieldError {
  field: (string | number)[];
  code: string;
  message: string;
}

export interface RunSnapshot {
  run_id: string;
  scenario_id: string;
  kind: Result["kind"];
  status: "QUEUED" | "RUNNING" | "AUDITING" | "COMPLETED" | "NO_SOLUTION" |
    "FAILED" | "TIMED_OUT" | "CANCELLED" | "INTERRUPTED";
  progress_stage: string;
  solver_status: string | null;
  runtime_ms: number | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  result?: Result;
  error?: { code: string; message: string; field_errors: FieldError[] };
}

export interface Comparison {
  baseline: Result;
  alternative: Result;
  plan: PlanSpec;
  deltas: Record<string, number | null>;
}
