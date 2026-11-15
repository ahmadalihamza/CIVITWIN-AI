from collections import Counter
from collections.abc import Mapping
from fractions import Fraction
from hashlib import sha256
from typing import Any, cast

from pydantic import JsonValue, ValidationError

from app.domain.dataset import canonical_json
from app.domain.results import Allocation, Metrics
from app.schemas.dataset import Contract, Dataset, Digest
from app.schemas.plan import PlanSpec


class AuditCheck(Contract):
    id: str
    passed: bool
    expected: JsonValue
    actual: JsonValue


class Audit(Contract):
    passed: bool
    checks: tuple[AuditCheck, ...]
    result_hash: Digest | None


class _PublishedAllocation(Allocation):
    metrics: Metrics


def verify(
    dataset: Dataset,
    plan: PlanSpec,
    travel: Mapping[tuple[str, str], int],
    demand: Mapping[str, int],
    serialized: dict[str, Any],
    *,
    fixed_candidates: tuple[str, ...] | None = None,
) -> Audit:
    """Verify a serialized result against trusted problem inputs without solver internals."""
    checks: list[AuditCheck] = []

    def record(check_id: str, passed: bool, expected: object, actual: object) -> None:
        checks.append(
            AuditCheck(
                id=check_id,
                passed=passed,
                expected=cast(JsonValue, expected),
                actual=cast(JsonValue, actual),
            )
        )

    try:
        encoded = canonical_json(serialized)
    except (TypeError, ValueError, RecursionError):
        record("ALLOCATION_SCHEMA", False, "Finite JSON", "Serialization failed")
        return Audit(passed=False, checks=tuple(checks), result_hash=None)
    digest = sha256(encoded).hexdigest()
    try:
        published = _PublishedAllocation.model_validate_json(encoded)
    except ValidationError as exc:
        failures = [
            {"field": ".".join(map(str, error["loc"])), "code": error["type"]}
            for error in exc.errors(include_input=False, include_url=False)
        ]
        record("ALLOCATION_SCHEMA", False, "Strict nonnegative integer counts", failures)
        return Audit(passed=False, checks=tuple(checks), result_hash=digest)
    record("ALLOCATION_SCHEMA", True, "Strict nonnegative integer counts", "Valid")

    community_ids = {community.id for community in dataset.communities}
    inputs_valid = (
        plan.dataset_version_id == dataset.id
        and demand.keys() == community_ids
        and all(type(visits) is int and visits >= 0 for visits in demand.values())
        and sum(demand.values()) > 0
    )
    record(
        "PROBLEM_INPUT", inputs_valid, "Matching dataset and positive total demand", inputs_valid
    )
    if not inputs_valid:
        return Audit(passed=False, checks=tuple(checks), result_hash=digest)

    sites = {site.id: site for site in dataset.sites}
    existing = {site.id for site in dataset.sites if site.type == "existing"}
    eligible = {site.id for site in dataset.sites if site.type == "candidate" and site.eligible}
    selected = set(published.selected_candidate_ids)
    duplicate_count = len(published.selected_candidate_ids) - len(selected)
    record("UNIQUE_SELECTION", duplicate_count == 0, 0, duplicate_count)
    invalid_candidates = sorted(selected - eligible)
    record("CANDIDATE_ELIGIBILITY", not invalid_candidates, [], invalid_candidates)
    if fixed_candidates is not None:
        fixed = sorted(fixed_candidates)
        record("FIXED_SELECTION", sorted(selected) == fixed, fixed, sorted(selected))
    record("UNIT_LIMIT", len(selected) <= plan.max_new_units, plan.max_new_units, len(selected))
    cost = sum(sites[site_id].fixed_cost_pkr for site_id in selected & eligible)
    record("BUDGET", cost <= plan.budget_pkr, plan.budget_pkr, cost)

    assignments_seen: set[tuple[str, str]] = set()
    invalid_pairs: list[JsonValue] = []
    duplicate_pairs: list[JsonValue] = []
    community_served: Counter[str] = Counter()
    community_covered: Counter[str] = Counter()
    site_load: Counter[str] = Counter()
    total_minutes = 0
    open_sites = existing | (selected & eligible)
    for row in published.assignments:
        pair = (row.community_id, row.site_id)
        if pair in assignments_seen:
            duplicate_pairs.append(list(pair))
        assignments_seen.add(pair)
        minutes = travel.get(pair)
        if (
            row.community_id not in community_ids
            or row.site_id not in open_sites
            or minutes is None
        ):
            invalid_pairs.append(list(pair))
            continue
        community_served[row.community_id] += row.visits
        site_load[row.site_id] += row.visits
        total_minutes += row.visits * minutes
        if minutes <= plan.threshold_minutes:
            community_covered[row.community_id] += row.visits
    record("UNIQUE_ASSIGNMENT", not duplicate_pairs, [], duplicate_pairs)
    record("ALLOWED_PAIRS", not invalid_pairs, [], invalid_pairs)

    unmet_keys = [row.community_id for row in published.unmet_by_community]
    unmet = {row.community_id: row.visits for row in published.unmet_by_community}
    record(
        "UNMET_ROWS", sorted(unmet_keys) == sorted(community_ids), sorted(community_ids), unmet_keys
    )
    accounted = {cid: community_served[cid] + unmet.get(cid, 0) for cid in sorted(community_ids)}
    record("DEMAND_BALANCE", accounted == demand, dict(demand), accounted)
    capacity = {
        sid: site.capacity_per_week if sid in open_sites else 0 for sid, site in sites.items()
    }
    loads = {sid: site_load[sid] for sid in sites}
    record("CAPACITY", all(loads[sid] <= capacity[sid] for sid in sites), capacity, loads)

    equity_required = {
        cid: (plan.equity_min_pct * visits + 99) // 100
        for cid, visits in demand.items()
        if visits > 0
    }
    within = {cid: community_covered[cid] for cid in equity_required}
    record(
        "EQUITY_FLOOR",
        all(within[cid] >= visits for cid, visits in equity_required.items()),
        equity_required,
        within,
    )

    # Recompute reporting directly from the audited rows, without the solver's metric function.
    exact_coverage = {
        cid: Fraction(100 * within[cid], demand[cid]) for cid in sorted(equity_required)
    }
    worst = min(exact_coverage, key=lambda cid: exact_coverage[cid])
    total_demand = sum(demand.values())
    served = sum(community_served.values())
    covered = sum(community_covered.values())
    unserved = sum(unmet.values())
    metrics = {
        "total_demand": total_demand,
        "served_visits": served,
        "unmet_visits": unserved,
        "covered_visits": covered,
        "visit_minutes": total_minutes,
        "served_rate_pct": 100 * served / total_demand,
        "unmet_rate_pct": 100 * unserved / total_demand,
        "coverage_pct": 100 * covered / total_demand,
        "mean_assigned_travel_minutes": total_minutes / served if served else None,
        "worst_cluster_id": worst,
        "worst_cluster_coverage_pct": float(exact_coverage[worst]),
        "equity_gap_pp": float(max(exact_coverage.values()) - exact_coverage[worst]),
        "cost_pkr": cost,
        "budget_pkr": plan.budget_pkr,
        "budget_utilization_pct": 100 * cost / plan.budget_pkr if plan.budget_pkr else None,
        "clusters": [
            {
                "community_id": cid,
                "demand_visits": demand[cid],
                "served_visits": community_served[cid],
                "unmet_visits": unmet.get(cid, 0),
                "covered_visits": community_covered[cid],
                "coverage_pct": float(exact_coverage[cid]) if cid in exact_coverage else None,
            }
            for cid in sorted(community_ids)
        ],
    }
    reported = published.metrics.model_dump(mode="json")
    mismatches = sorted(key for key in metrics if metrics[key] != reported[key])
    record("METRICS", not mismatches, [], mismatches)
    return Audit(
        passed=all(check.passed for check in checks), checks=tuple(checks), result_hash=digest
    )
