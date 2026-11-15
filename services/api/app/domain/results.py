from typing import Annotated

from pydantic import Field

from app.schemas.dataset import Contract, Identifier

Nonnegative = Annotated[int, Field(ge=0)]


class Assignment(Contract):
    community_id: Identifier
    site_id: Identifier
    visits: Nonnegative


class Unmet(Contract):
    community_id: Identifier
    visits: Nonnegative


class Allocation(Contract):
    selected_candidate_ids: tuple[Identifier, ...]
    assignments: tuple[Assignment, ...]
    unmet_by_community: tuple[Unmet, ...]


class ClusterMetrics(Contract):
    community_id: Identifier
    demand_visits: Nonnegative
    served_visits: Nonnegative
    unmet_visits: Nonnegative
    covered_visits: Nonnegative
    coverage_pct: float | None


class Metrics(Contract):
    total_demand: Nonnegative
    served_visits: Nonnegative
    unmet_visits: Nonnegative
    covered_visits: Nonnegative
    visit_minutes: Nonnegative
    served_rate_pct: float
    unmet_rate_pct: float
    coverage_pct: float
    mean_assigned_travel_minutes: float | None
    worst_cluster_id: Identifier
    worst_cluster_coverage_pct: float
    equity_gap_pp: float
    cost_pkr: Nonnegative
    budget_pkr: Nonnegative
    budget_utilization_pct: float | None
    clusters: tuple[ClusterMetrics, ...]
