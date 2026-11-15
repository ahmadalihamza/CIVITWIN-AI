from app.domain.results import Metrics


def compare_metrics(base: Metrics, alt: Metrics) -> dict[str, float | int | None]:
    covered_delta = alt.covered_visits - base.covered_visits
    cost_delta = alt.cost_pkr - base.cost_pkr
    base_travel, alt_travel = base.mean_assigned_travel_minutes, alt.mean_assigned_travel_minutes
    return {
        "covered_visits": covered_delta,
        "served_visits": alt.served_visits - base.served_visits,
        "unmet_visits": alt.unmet_visits - base.unmet_visits,
        "coverage_pp": alt.coverage_pct - base.coverage_pct,
        "served_rate_pp": alt.served_rate_pct - base.served_rate_pct,
        "unmet_rate_pp": alt.unmet_rate_pct - base.unmet_rate_pct,
        "worst_cluster_coverage_pp": alt.worst_cluster_coverage_pct
        - base.worst_cluster_coverage_pct,
        "equity_gap_pp": alt.equity_gap_pp - base.equity_gap_pp,
        "mean_assigned_travel_minutes": (
            alt_travel - base_travel if base_travel is not None and alt_travel is not None else None
        ),
        "cost_pkr": cost_delta,
        "additional_cost_per_added_covered_visit": (
            cost_delta / covered_delta if covered_delta > 0 else None
        ),
    }
