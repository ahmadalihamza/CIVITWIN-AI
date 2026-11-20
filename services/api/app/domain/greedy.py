"""A deliberately simple, capacity-aware heuristic for comparison."""

from dataclasses import replace
from fractions import Fraction
from math import isfinite
from time import monotonic

import networkx as nx

from app.domain.optimizer import Progress, RunStatus, SolveOutcome, Stop, solve
from app.domain.travel import travel_matrix
from app.schemas.dataset import Dataset
from app.schemas.plan import PlanSpec, scaled_visits


def solve_greedy(
    dataset: Dataset,
    plan: PlanSpec,
    *,
    timeout_seconds: float = 10,
    cancelled: Stop | None = None,
    on_stage: Progress | None = None,
) -> SolveOutcome:
    """Choose sites by marginal covered visits per PKR, then solve fixed-site assignments."""
    started = monotonic()
    plan.validate_for(dataset)
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The greedy time limit must be positive and finite.")
    deadline = started + timeout_seconds

    def runtime_ms() -> int:
        return round((monotonic() - started) * 1_000)

    def interruption() -> SolveOutcome | None:
        if cancelled and cancelled():
            status: RunStatus = "CANCELLED"
            message = "The run was cancelled."
        elif monotonic() >= deadline:
            status = "TIMED_OUT"
            message = "The time limit elapsed before greedy assignment."
        else:
            return None
        return SolveOutcome(status, "NOT_RUN", None, (message,), runtime_ms())

    if stopped := interruption():
        return stopped

    candidates = [
        site
        for site in sorted(dataset.sites, key=lambda row: row.id)
        if site.type == "candidate"
        and site.eligible
        and site.fixed_cost_pkr <= plan.budget_pkr
        and site.capacity_per_week
    ]
    selected: list[str] = []
    if candidates and plan.max_new_units:
        if on_stage:
            on_stage("GREEDY_SELECTION")
        graph = nx.DiGraph()
        source, sink = ("flow", "source"), ("flow", "sink")
        graph.add_nodes_from((source, sink))
        demand = {
            row.id: scaled_visits(row.demand_visits_per_week, plan.demand_multiplier_pct)
            for row in sorted(dataset.communities, key=lambda item: item.id)
        }
        for community_id, visits in demand.items():
            graph.add_edge(source, ("community", community_id), capacity=visits)
        available = {
            site.id: site for site in dataset.sites if site.type == "existing" or site in candidates
        }
        for site in sorted(available.values(), key=lambda row: row.id):
            graph.add_edge(
                ("site", site.id),
                sink,
                capacity=site.capacity_per_week if site.type == "existing" else 0,
            )
        for (community_id, site_id), minutes in sorted(travel_matrix(dataset).items()):
            if minutes <= plan.threshold_minutes and site_id in available:
                capacity = min(demand[community_id], available[site_id].capacity_per_week)
                if capacity:
                    graph.add_edge(
                        ("community", community_id), ("site", site_id), capacity=capacity
                    )

        def coverage() -> int:
            return int(
                nx.maximum_flow_value(
                    graph, source, sink, flow_func=nx.algorithms.flow.preflow_push
                )
            )

        if stopped := interruption():
            return stopped
        current = coverage()
        remaining_budget = plan.budget_pkr
        while candidates and len(selected) < plan.max_new_units:
            best_rank: tuple[bool, Fraction, int, int] | None = None
            best_site = None
            for site in candidates:
                if stopped := interruption():
                    return stopped
                if site.fixed_cost_pkr > remaining_budget:
                    continue
                edge = graph[("site", site.id)][sink]
                edge["capacity"] = site.capacity_per_week
                gain = coverage() - current
                edge["capacity"] = 0
                if gain <= 0:
                    continue
                cost = site.fixed_cost_pkr
                rank = (cost == 0, Fraction(gain, max(1, cost)), gain, -cost)
                if best_rank is None or rank > best_rank:
                    best_rank, best_site = rank, site
            if best_rank is None or best_site is None:
                break
            selected.append(best_site.id)
            candidates.remove(best_site)
            current += best_rank[2]
            remaining_budget -= best_site.fixed_cost_pkr
            graph[("site", best_site.id)][sink]["capacity"] = best_site.capacity_per_week

    remaining = deadline - monotonic()
    if stopped := interruption():
        return stopped
    outcome = solve(
        dataset,
        plan,
        kind="greedy",
        timeout_seconds=remaining,
        fixed_candidates=tuple(sorted(selected)),
        cancelled=cancelled,
        on_stage=on_stage,
    )
    elapsed = runtime_ms()
    if outcome.result is None:
        return replace(outcome, runtime_ms=elapsed)
    warnings = (
        *outcome.warnings,
        "Greedy site selection is a heuristic. Solver status refers to assignments for those sites.",
    )
    return replace(
        outcome,
        warnings=warnings,
        runtime_ms=elapsed,
        result=outcome.result.model_copy(update={"runtime_ms": elapsed, "warnings": warnings}),
    )
