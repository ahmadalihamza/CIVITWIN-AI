from pathlib import Path
from time import monotonic

import pytest
from app.domain import optimizer
from app.domain.dataset import create_dataset, dataset_payload, load_dataset
from app.domain.optimizer import solve
from app.domain.travel import scaled_travel, travel_matrix
from app.schemas.dataset import Dataset
from app.schemas.plan import PlanSpec

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(name: str) -> Dataset:
    return load_dataset((FIXTURES / f"{name}.json").read_bytes())


def make_plan(dataset: Dataset, **overrides: object) -> PlanSpec:
    return PlanSpec.model_validate(
        {
            "dataset_version_id": dataset.id,
            "budget_pkr": 100,
            "max_new_units": min(dataset.eligible_candidate_count, 1),
            "threshold_minutes": 30,
            "demand_multiplier_pct": 100,
            "equity_min_pct": 0,
            "policy": "coverage_first",
            "seed": 2026,
            **overrides,
        }
    )


def test_t01_golden_baseline_and_optimized():
    dataset = load_fixture("golden")
    plan = make_plan(dataset)
    for kind, covered, worst, cost, selected, assignments, unmet in (
        ("baseline", 60, 0, 0, (), [("A", "E", 60)], {"A": 0, "B": 40}),
        ("optimized", 100, 100, 100, ("N",), [("A", "E", 60), ("B", "N", 40)], {"A": 0, "B": 0}),
    ):
        outcome = solve(dataset, plan, kind=kind)
        assert outcome.status == "COMPLETED" and outcome.solver_status == "OPTIMAL"
        result = outcome.result
        assert result is not None and result.audit.passed and result.audit.checks
        assert tuple(result.selected_candidate_ids) == selected
        assert [
            (row.community_id, row.site_id, row.visits) for row in result.assignments
        ] == assignments
        assert {row.community_id: row.visits for row in result.unmet_by_community} == unmet
        metrics = result.metrics
        assert metrics.total_demand == 100
        assert metrics.covered_visits == metrics.served_visits == covered
        assert metrics.coverage_pct == metrics.served_rate_pct == covered
        assert metrics.worst_cluster_coverage_pct == worst
        assert metrics.mean_assigned_travel_minutes == 10
        assert metrics.visit_minutes == covered * 10
        assert metrics.unmet_visits == 100 - covered
        assert metrics.cost_pkr == cost
        assert len(result.objective_stages) == 5


@pytest.mark.parametrize("override", [{"budget_pkr": 0}, {"max_new_units": 0}])
def test_t02_zero_budget_or_zero_unit_limit(override):
    dataset = load_fixture("golden")
    outcome = solve(dataset, make_plan(dataset, **override))
    result = outcome.result
    assert result is not None and result.audit.passed
    assert not result.selected_candidate_ids and result.metrics.cost_pkr == 0
    assert result.metrics.covered_visits == 60
    if "budget_pkr" in override:
        assert result.metrics.budget_utilization_pct is None


def test_t03_disconnected_pairs_and_same_node_cost():
    dataset = load_fixture("disconnected")
    matrix = travel_matrix(dataset)
    assert matrix == {("C01", "E01"): 0}
    assert travel_matrix(load_fixture("disconnected")) is matrix
    with pytest.raises(TypeError):
        matrix[("C02", "E01")] = 0
    result = solve(dataset, make_plan(dataset)).result
    assert result is not None and result.audit.passed
    assert [(row.community_id, row.site_id, row.visits) for row in result.assignments] == [
        ("C01", "E01", 60)
    ]
    assert result.metrics.unmet_visits == 40
    assert result.metrics.mean_assigned_travel_minutes == 0


def test_t04_capacity_saturation():
    dataset = load_fixture("saturated")
    result = solve(dataset, make_plan(dataset)).result
    assert result is not None and result.audit.passed
    assert [(row.site_id, row.visits) for row in result.assignments] == [("E", 45), ("N", 20)]
    assert result.metrics.covered_visits == result.metrics.served_visits == 65
    assert result.metrics.unmet_visits == 35
    assert result.metrics.worst_cluster_coverage_pct == 50


def test_t05_impossible_equity_floor_and_alternative_feasibility():
    dataset = load_fixture("golden")
    plan = make_plan(dataset, equity_min_pct=100)
    baseline = solve(dataset, plan, kind="baseline")
    assert baseline.status == "NO_SOLUTION" and baseline.solver_status == "INFEASIBLE"
    assert baseline.result is None
    alternative = solve(dataset, plan, kind="optimized")
    assert alternative.status == "COMPLETED" and alternative.result is not None
    assert (
        alternative.result.audit.passed
        and alternative.result.metrics.worst_cluster_coverage_pct == 100
    )
    disconnected = load_fixture("disconnected")
    impossible = solve(disconnected, make_plan(disconnected, equity_min_pct=1))
    assert impossible.status == "NO_SOLUTION" and impossible.result is None


def test_travel_uses_shortest_directed_paths_and_scales_final_integer_cost_once():
    payload = dataset_payload(load_fixture("golden"))
    del payload["sha256"]
    payload["edges"].append(
        {"from_node": "N", "to_node": "E", "minutes": 5, "direction": "forward"}
    )
    matrix = travel_matrix(create_dataset(payload))
    assert matrix == {("A", "E"): 10, ("A", "N"): 40, ("B", "E"): 15, ("B", "N"): 10}
    assert scaled_travel(matrix, 100) is matrix
    assert scaled_travel(matrix, 110)[("B", "E")] == 17
    assert scaled_travel(matrix, 90)[("B", "E")] == 14


def test_demo_bajaur_default_comparison_is_audited_and_changes_coverage():
    from app.schemas.plan import default_plan

    demo_path = Path(__file__).resolve().parents[4] / "data/demo/bajaur-v1.json"
    dataset = load_dataset(demo_path.read_bytes())
    plan = default_plan()
    baseline = solve(dataset, plan, kind="baseline")
    optimized = solve(dataset, plan, kind="optimized")
    assert baseline.result is not None and optimized.result is not None
    assert baseline.result.audit.passed and optimized.result.audit.passed
    assert optimized.result.metrics.covered_visits > baseline.result.metrics.covered_visits


def test_solver_does_not_publish_on_pre_cancel_or_timeout_before_any_incumbent():
    dataset = load_fixture("golden")
    plan = make_plan(dataset)
    cancelled = solve(dataset, plan, cancelled=lambda: True)
    assert cancelled.status == "CANCELLED" and cancelled.result is None
    timed_out = solve(dataset, plan, timeout_seconds=1e-12)
    assert timed_out.status == "TIMED_OUT" and timed_out.result is None


def test_lexicographic_deadline_retains_audited_incumbent(monkeypatch):
    dataset = load_fixture("golden")
    clock_offset = 0.0

    def clock() -> float:
        return monotonic() + clock_offset

    def on_stage(stage: str) -> None:
        nonlocal clock_offset
        if stage == "served_visits":
            clock_offset = 30.0

    monkeypatch.setattr(optimizer, "monotonic", clock)
    outcome = solve(dataset, make_plan(dataset), on_stage=on_stage)
    assert outcome.status == "COMPLETED" and outcome.solver_status == "FEASIBLE"
    assert outcome.result is not None and outcome.result.audit.passed
    assert outcome.result.metrics.covered_visits == 100
    assert [stage.status for stage in outcome.result.objective_stages] == ["OPTIMAL"] + [
        "NOT_RUN"
    ] * 4
    assert outcome.runtime_ms >= 30_000
