from collections import Counter
from collections.abc import Mapping
from fractions import Fraction

from app.domain.results import Allocation, ClusterMetrics, Metrics
from app.schemas.dataset import Dataset
from app.schemas.plan import PlanSpec


def compute_metrics(
    dataset: Dataset,
    plan: PlanSpec,
    travel: Mapping[tuple[str, str], int],
    demand: Mapping[str, int],
    allocation: Allocation,
) -> Metrics:
    served: Counter[str] = Counter()
    covered: Counter[str] = Counter()
    visit_minutes = 0
    for row in allocation.assignments:
        minutes = travel[row.community_id, row.site_id]
        served[row.community_id] += row.visits
        visit_minutes += minutes * row.visits
        if minutes <= plan.threshold_minutes:
            covered[row.community_id] += row.visits

    unmet = {row.community_id: row.visits for row in allocation.unmet_by_community}
    coverage = {
        community_id: Fraction(covered[community_id], visits)
        for community_id, visits in sorted(demand.items())
        if visits > 0
    }
    if not coverage:
        raise ValueError("Metrics require positive total weekly demand.")
    worst_cluster_id, worst_coverage = min(coverage.items(), key=lambda item: item[1])
    best_coverage = max(coverage.values())
    clusters = tuple(
        ClusterMetrics(
            community_id=community_id,
            demand_visits=visits,
            served_visits=served[community_id],
            unmet_visits=unmet[community_id],
            covered_visits=covered[community_id],
            coverage_pct=float(100 * coverage[community_id]) if visits else None,
        )
        for community_id, visits in sorted(demand.items())
    )
    total_demand = sum(demand.values())
    total_served = served.total()
    total_unmet = sum(unmet.values())
    total_covered = covered.total()
    candidate_ids = set(allocation.selected_candidate_ids)
    cost = sum(site.fixed_cost_pkr for site in dataset.sites if site.id in candidate_ids)
    return Metrics(
        total_demand=total_demand,
        served_visits=total_served,
        unmet_visits=total_unmet,
        covered_visits=total_covered,
        visit_minutes=visit_minutes,
        served_rate_pct=100 * total_served / total_demand,
        unmet_rate_pct=100 * total_unmet / total_demand,
        coverage_pct=100 * total_covered / total_demand,
        mean_assigned_travel_minutes=visit_minutes / total_served if total_served else None,
        worst_cluster_id=worst_cluster_id,
        worst_cluster_coverage_pct=float(100 * worst_coverage),
        equity_gap_pp=float(100 * (best_coverage - worst_coverage)),
        cost_pkr=cost,
        budget_pkr=plan.budget_pkr,
        budget_utilization_pct=100 * cost / plan.budget_pkr if plan.budget_pkr else None,
        clusters=clusters,
    )
