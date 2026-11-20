"""Sensitivity analysis for two already chosen candidate selections."""

from collections.abc import Callable, Iterable
from math import isfinite
from random import Random
from time import monotonic

from app.domain.optimizer import Kind, RunStatus, Stop, solve
from app.schemas.dataset import Contract, Dataset
from app.schemas.plan import PlanSpec

STRESS_ASSUMPTIONS = (
    "Demand draws are 80–130% of approved demand assumptions and travel draws are 90–140%.",
    "Draws use a local seeded integer generator and are shared by both allocations.",
    "Weekly visits are rounded half up once after multiplying raw demand by both percentages.",
    "The shortest-path travel matrix is scaled once, half up. Unreachable pairs stay unreachable.",
    "Selected candidate sites remain fixed. Assignments are solved and audited for each side.",
    "P10 and P90 interpolate linearly between ranks (n−1)×p in each successful sample.",
    "These ranges describe tested scenarios. They are not confidence intervals or forecasts.",
)


class CaseObservation(Contract):
    status: RunStatus
    solver_status: str
    total_demand: int | None = None
    covered_visits: int | None = None
    coverage_pct: float | None = None
    unmet_rate_pct: float | None = None
    worst_cluster_coverage_pct: float | None = None
    mean_assigned_travel_minutes: float | None = None
    audit_passed: bool = False
    audit_hash: str | None = None
    selected_candidate_ids: tuple[str, ...] | None = None


class StressCase(Contract):
    case_number: int
    demand_multiplier_pct: int
    travel_multiplier_pct: int
    baseline: CaseObservation
    alternative: CaseObservation


class Distribution(Contract):
    min: float
    max: float
    median: float
    p10: float
    p90: float
    sample_count: int


class SideSummary(Contract):
    successful_cases: int
    failed_cases: int
    excluded_cases: int
    failure_rate_pct: float
    coverage_pct: Distribution | None
    unmet_rate_pct: Distribution | None
    worst_cluster_coverage_pct: Distribution | None
    mean_assigned_travel_minutes: Distribution | None


class StressResult(Contract):
    seed: int
    case_count: int
    cases: tuple[StressCase, ...]
    baseline: SideSummary
    alternative: SideSummary
    paired_success_count: int
    runtime_ms: int
    cancelled: bool
    assumptions: tuple[str, ...]
    dataset_sha256: str
    plan_hash: str


def _distribution(values: Iterable[float | None]) -> Distribution | None:
    sample = sorted(value for value in values if value is not None)
    if not sample:
        return None

    def quantile(percentile: int) -> float:
        lower, remainder = divmod((len(sample) - 1) * percentile, 100)
        upper = min(lower + 1, len(sample) - 1)
        return sample[lower] + (sample[upper] - sample[lower]) * remainder / 100

    return Distribution(
        min=sample[0],
        max=sample[-1],
        median=quantile(50),
        p10=quantile(10),
        p90=quantile(90),
        sample_count=len(sample),
    )


def _summary(observations: list[CaseObservation]) -> SideSummary:
    successes = [row for row in observations if row.audit_passed]
    failures = len(observations) - len(successes)
    return SideSummary(
        successful_cases=len(successes),
        failed_cases=failures,
        excluded_cases=failures,
        failure_rate_pct=100 * failures / len(observations),
        coverage_pct=_distribution(row.coverage_pct for row in successes),
        unmet_rate_pct=_distribution(row.unmet_rate_pct for row in successes),
        worst_cluster_coverage_pct=_distribution(
            row.worst_cluster_coverage_pct for row in successes
        ),
        mean_assigned_travel_minutes=_distribution(
            row.mean_assigned_travel_minutes for row in successes
        ),
    )


def run_stress(
    dataset: Dataset,
    plan: PlanSpec,
    *,
    baseline_candidates: tuple[str, ...],
    alternative_candidates: tuple[str, ...],
    seed: int,
    case_count: int = 20,
    timeout_seconds: float = 60,
    cancelled: Stop | None = None,
    on_case: Callable[[int, int], None] | None = None,
) -> StressResult:
    """Run the two fixed selections on identical perturbations under one deadline."""
    started = monotonic()
    plan.validate_for(dataset)
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise ValueError("Seed must be an integer from 0 to 2147483647.")
    if type(case_count) is not int or not 1 <= case_count <= 20:
        raise ValueError("Case count must be an integer from 1 to 20.")
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The stress time limit must be positive and finite.")
    if baseline_candidates:
        raise ValueError("The baseline selection must be empty.")
    eligible = {
        site.id: site.fixed_cost_pkr
        for site in dataset.sites
        if site.type == "candidate" and site.eligible
    }
    selected = set(alternative_candidates)
    if (
        len(selected) != len(alternative_candidates)
        or not selected <= eligible.keys()
        or len(selected) > plan.max_new_units
        or sum(eligible[site] for site in selected) > plan.budget_pkr
    ):
        raise ValueError("The alternative selection is incompatible with the approved plan.")
    deadline = started + timeout_seconds
    random = Random(seed)
    settings = [(random.randint(80, 130), random.randint(90, 140)) for _ in range(case_count)]

    def observe(
        kind: Kind, candidates: tuple[str, ...], demand_pct: int, travel_pct: int
    ) -> CaseObservation:
        if cancelled and cancelled():
            return CaseObservation(status="CANCELLED", solver_status="NOT_RUN")
        remaining = deadline - monotonic()
        if remaining <= 0:
            return CaseObservation(status="TIMED_OUT", solver_status="NOT_RUN")
        outcome = solve(
            dataset,
            plan,
            kind=kind,
            fixed_candidates=candidates,
            stress_demand_multiplier_pct=demand_pct,
            travel_multiplier_pct=travel_pct,
            timeout_seconds=remaining,
            cancelled=cancelled,
        )
        result = outcome.result
        if result is None:
            return CaseObservation(status=outcome.status, solver_status=outcome.solver_status)
        if not result.audit.passed:
            return CaseObservation(status="FAILED", solver_status="AUDIT_FAILED")
        return CaseObservation(
            status=outcome.status,
            solver_status=outcome.solver_status,
            total_demand=result.metrics.total_demand,
            covered_visits=result.metrics.covered_visits,
            coverage_pct=result.metrics.coverage_pct,
            unmet_rate_pct=result.metrics.unmet_rate_pct,
            worst_cluster_coverage_pct=result.metrics.worst_cluster_coverage_pct,
            mean_assigned_travel_minutes=result.metrics.mean_assigned_travel_minutes,
            audit_passed=True,
            audit_hash=result.audit.result_hash,
            selected_candidate_ids=result.selected_candidate_ids,
        )

    cases: list[StressCase] = []
    for case, (demand_pct, travel_pct) in enumerate(settings, start=1):
        cases.append(
            StressCase(
                case_number=case,
                demand_multiplier_pct=demand_pct,
                travel_multiplier_pct=travel_pct,
                baseline=observe("baseline", baseline_candidates, demand_pct, travel_pct),
                alternative=observe("optimized", alternative_candidates, demand_pct, travel_pct),
            )
        )
        if on_case:
            on_case(case, case_count)
    return StressResult(
        seed=seed,
        case_count=case_count,
        cases=tuple(cases),
        baseline=_summary([case.baseline for case in cases]),
        alternative=_summary([case.alternative for case in cases]),
        paired_success_count=sum(
            case.baseline.audit_passed and case.alternative.audit_passed for case in cases
        ),
        runtime_ms=round((monotonic() - started) * 1_000),
        cancelled=any(
            "CANCELLED" in (case.baseline.status, case.alternative.status) for case in cases
        ),
        assumptions=STRESS_ASSUMPTIONS,
        dataset_sha256=dataset.sha256,
        plan_hash=plan.plan_hash,
    )
