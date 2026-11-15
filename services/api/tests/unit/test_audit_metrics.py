from copy import deepcopy
from pathlib import Path

import pytest
from app.domain.audit import verify
from app.domain.dataset import load_dataset
from app.domain.metrics import compute_metrics
from app.domain.results import Allocation, Assignment, Unmet
from app.schemas.plan import PlanSpec


@pytest.fixture
def verified_problem():
    path = Path(__file__).resolve().parents[1] / "fixtures/disconnected.json"
    dataset = load_dataset(path.read_bytes())
    plan = PlanSpec(
        dataset_version_id=dataset.id,
        budget_pkr=0,
        max_new_units=0,
        threshold_minutes=30,
        demand_multiplier_pct=100,
        equity_min_pct=0,
        policy="coverage_first",
        seed=2026,
    )
    travel = {("C01", "E01"): 0}
    demand = {"C01": 60, "C02": 40}
    allocation = Allocation(
        selected_candidate_ids=(),
        assignments=(Assignment(community_id="C01", site_id="E01", visits=60),),
        unmet_by_community=(
            Unmet(community_id="C01", visits=0),
            Unmet(community_id="C02", visits=40),
        ),
    )
    metrics = compute_metrics(dataset, plan, travel, demand, allocation)
    serialized = {**allocation.model_dump(mode="json"), "metrics": metrics.model_dump(mode="json")}
    return dataset, plan, travel, demand, serialized


def test_independently_verified_metrics_and_result_hash(verified_problem):
    dataset, plan, travel, demand, serialized = verified_problem
    result = verify(dataset, plan, travel, demand, serialized, fixed_candidates=())
    assert result.passed
    assert result.checks and all(check.passed for check in result.checks)
    assert result.result_hash and len(result.result_hash) == 64
    assert verify(dataset, plan, travel, demand, serialized).result_hash == result.result_hash
    metrics = serialized["metrics"]
    assert metrics["coverage_pct"] == metrics["served_rate_pct"] == 60
    assert metrics["unmet_rate_pct"] == 40
    assert metrics["worst_cluster_id"] == "C02"
    assert metrics["worst_cluster_coverage_pct"] == 0
    assert metrics["equity_gap_pp"] == 100
    assert metrics["mean_assigned_travel_minutes"] == 0
    assert metrics["budget_utilization_pct"] is None


@pytest.mark.parametrize(
    ("target", "key", "value", "failed_check"),
    [
        ("assignments", "visits", True, "ALLOCATION_SCHEMA"),
        ("assignments", "visits", -1, "ALLOCATION_SCHEMA"),
        ("assignments", "visits", 1.0, "ALLOCATION_SCHEMA"),
        ("assignments", "visits", 59, "DEMAND_BALANCE"),
        ("assignments", "visits", 101, "CAPACITY"),
        ("assignments", "community_id", "C02", "ALLOWED_PAIRS"),
        ("assignments", "site_id", "unregistered", "ALLOWED_PAIRS"),
        ("unmet_by_community", "community_id", "C02", "UNMET_ROWS"),
        ("metrics", "coverage_pct", 61.0, "METRICS"),
        ("metrics", "mean_assigned_travel_minutes", None, "METRICS"),
    ],
)
def test_tampered_serialized_output_fails_audit(verified_problem, target, key, value, failed_check):
    dataset, plan, travel, demand, serialized = verified_problem
    tampered = deepcopy(serialized)
    section = tampered[target]
    target_record = section[0] if isinstance(section, list) else section
    target_record[key] = value
    audit = verify(dataset, plan, travel, demand, tampered)
    assert not audit.passed
    assert failed_check in {check.id for check in audit.checks if not check.passed}


def test_independent_selection_equity_and_repeated_assignments(verified_problem):
    dataset, plan, travel, demand, serialized = verified_problem
    serialized["selected_candidate_ids"] = ["E01", "E01"]
    serialized["assignments"].append(serialized["assignments"][0])
    stricter = plan.model_copy(update={"equity_min_pct": 20})
    audit = verify(dataset, stricter, travel, demand, serialized, fixed_candidates=())
    assert not audit.passed
    assert {
        "CANDIDATE_ELIGIBILITY",
        "UNIQUE_SELECTION",
        "FIXED_SELECTION",
        "UNIT_LIMIT",
        "UNIQUE_ASSIGNMENT",
        "EQUITY_FLOOR",
    } <= {check.id for check in audit.checks if not check.passed}


def test_no_assignments_and_zero_demand_cluster_metrics(verified_problem):
    dataset, plan, _, _, _ = verified_problem
    demand = {"C01": 0, "C02": 40}
    allocation = Allocation(
        selected_candidate_ids=(),
        assignments=(),
        unmet_by_community=(
            Unmet(community_id="C01", visits=0),
            Unmet(community_id="C02", visits=40),
        ),
    )
    metrics = compute_metrics(dataset, plan, {}, demand, allocation)
    assert metrics.mean_assigned_travel_minutes is None
    assert metrics.clusters[0].coverage_pct is None
    assert metrics.worst_cluster_id == "C02"
    assert metrics.unmet_visits == metrics.total_demand == 40
    serialized = {**allocation.model_dump(mode="json"), "metrics": metrics.model_dump(mode="json")}
    assert verify(dataset, plan, {}, demand, serialized).passed
