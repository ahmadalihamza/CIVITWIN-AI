from pathlib import Path

import pytest
from app.domain.dataset import create_dataset, dataset_payload, load_dataset
from app.domain.greedy import solve_greedy
from app.domain.stress import run_stress
from app.schemas.plan import default_plan

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def golden():
    dataset = load_dataset((FIXTURES / "golden.json").read_bytes())
    return dataset, default_plan(dataset.id).model_copy(
        update={"budget_pkr": 100, "max_new_units": 1, "threshold_minutes": 30}
    )


def _run(dataset, plan, **overrides):
    return run_stress(
        dataset,
        plan,
        baseline_candidates=(),
        alternative_candidates=("N",),
        **{"seed": 2026, "case_count": 5, **overrides},
    )


def test_t09_reproducible_paired_cases_use_fixed_audited_selections(golden):
    dataset, plan = golden
    steps = []
    first = _run(dataset, plan, on_case=lambda case, count: steps.append((case, count)))
    second = _run(dataset, plan)
    assert first.model_dump(exclude={"runtime_ms"}) == second.model_dump(exclude={"runtime_ms"})
    assert steps == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    assert first.paired_success_count == 5
    assert first.dataset_sha256 == dataset.sha256
    assert first.plan_hash == plan.plan_hash
    for case in first.cases:
        assert 80 <= case.demand_multiplier_pct <= 130
        assert 90 <= case.travel_multiplier_pct <= 140
        assert case.baseline.total_demand == case.alternative.total_demand
        assert case.baseline.selected_candidate_ids == ()
        assert case.alternative.selected_candidate_ids == ("N",)
        assert case.baseline.audit_hash and case.alternative.audit_hash
    sample = sorted(case.alternative.coverage_pct for case in first.cases)
    coverage = first.alternative.coverage_pct
    assert coverage is not None and coverage.sample_count == 5
    assert (coverage.min, coverage.median, coverage.max) == (sample[0], sample[2], sample[-1])
    assert coverage.p10 == pytest.approx(sample[0] * 0.6 + sample[1] * 0.4)
    assert coverage.p90 == pytest.approx(sample[3] * 0.4 + sample[4] * 0.6)


def test_t09_infeasible_sides_have_no_kpis_and_are_excluded(golden):
    dataset, plan = golden
    result = _run(dataset, plan.model_copy(update={"equity_min_pct": 1}))
    assert result.baseline.successful_cases == 0
    assert result.baseline.failed_cases == result.baseline.excluded_cases == result.case_count
    assert result.baseline.failure_rate_pct == 100
    assert result.baseline.coverage_pct is None
    assert result.alternative.successful_cases == result.case_count
    assert result.paired_success_count == 0
    assert all(
        case.baseline.status == "NO_SOLUTION" and case.baseline.covered_visits is None
        for case in result.cases
    )


def test_stress_can_exceed_approved_multiplier_without_changing_plan_hash(golden):
    dataset, original_plan = golden
    plan = original_plan.model_copy(update={"demand_multiplier_pct": 300})
    result = _run(dataset, plan, case_count=20)
    assert result.plan_hash == plan.plan_hash
    assert any(case.baseline.total_demand > 300 for case in result.cases)
    for case in result.cases:
        assert case.baseline.total_demand == (
            (60 * 300 * case.demand_multiplier_pct + 5_000) // 10_000
            + (40 * 300 * case.demand_multiplier_pct + 5_000) // 10_000
        )


@pytest.mark.parametrize(
    "status, overrides",
    [
        ("TIMED_OUT", {"timeout_seconds": 1e-12}),
        ("CANCELLED", {"cancelled": lambda: True}),
    ],
)
def test_stress_shared_deadline_and_cancellation_keep_failure_counts(golden, status, overrides):
    dataset, plan = golden
    result = _run(dataset, plan, **overrides)
    assert result.paired_success_count == 0
    assert result.cancelled == (status == "CANCELLED")
    assert result.baseline.failed_cases == result.alternative.failed_cases == 5
    assert all(case.baseline.status == case.alternative.status == status for case in result.cases)


def test_greedy_scores_marginal_coverage_using_capacity_and_cost(golden):
    dataset, plan = golden
    payload = dataset_payload(dataset)
    del payload["sha256"]
    payload["sites"].append(
        {
            **next(site for site in payload["sites"] if site["id"] == "N"),
            "id": "N2",
            "capacity_per_week": 20,
            "fixed_cost_pkr": 30,
        }
    )
    options = create_dataset(payload)
    stages = []
    outcome = solve_greedy(options, plan, on_stage=stages.append)
    assert outcome.result is not None and outcome.result.audit.passed
    assert outcome.result.selected_candidate_ids == ("N2",)
    assert outcome.result.metrics.covered_visits == 80
    assert outcome.result.metrics.cost_pkr == 30
    assert stages[0] == "GREEDY_SELECTION" and stages.count("AUDITING") == 1
    assert "assignments for those sites" in outcome.warnings[-1]


def test_greedy_budget_and_equity_conflict_has_no_result(golden):
    dataset, plan = golden
    outcome = solve_greedy(dataset, plan.model_copy(update={"budget_pkr": 0, "equity_min_pct": 1}))
    assert outcome.status == "NO_SOLUTION"
    assert outcome.result is None
