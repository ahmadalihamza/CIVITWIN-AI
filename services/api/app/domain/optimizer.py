"""Integer allocation with a shared lexicographic deadline."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.metadata import version
from math import isfinite
from threading import Event, Thread
from time import monotonic
from typing import Literal

from ortools.sat.python import cp_model

from app.domain.audit import Audit, verify
from app.domain.metrics import compute_metrics
from app.domain.results import Allocation, Assignment, Metrics, Unmet
from app.domain.travel import scaled_travel, travel_matrix
from app.schemas.dataset import Contract, Dataset
from app.schemas.plan import PlanSpec, scaled_visits

MODEL_VERSION = "1.0"
WORKERS = 1
Kind = Literal["baseline", "optimized", "greedy"]
RunStatus = Literal["COMPLETED", "NO_SOLUTION", "TIMED_OUT", "CANCELLED", "FAILED"]
Stop = Callable[[], bool]
Progress = Callable[[str], None]
Pair = tuple[str, str]
Objective = tuple[str, Literal["maximize", "minimize"], cp_model.LinearExpr]
SOLVER_VERSION = version("ortools")


class ObjectiveStage(Contract):
    objective: str
    direction: Literal["maximize", "minimize"]
    status: str
    value: int | None
    best_bound: float | None


class SolverSettings(Contract):
    solver_version: str
    seed: int
    worker_count: int
    time_limit_seconds: float


class Result(Allocation):
    kind: Kind
    solver_status: Literal["OPTIMAL", "FEASIBLE"]
    dataset_sha256: str
    plan_hash: str
    metrics: Metrics
    objective_stages: tuple[ObjectiveStage, ...]
    audit: Audit
    warnings: tuple[str, ...]
    runtime_ms: int
    model_version: str
    solver_settings: SolverSettings


@dataclass(frozen=True)
class SolveOutcome:
    status: RunStatus
    solver_status: str
    result: Result | None
    warnings: tuple[str, ...]
    runtime_ms: int


@dataclass
class Model:
    program: cp_model.CpModel
    opened: dict[str, cp_model.IntVar]
    visits: dict[Pair, cp_model.IntVar]
    unmet: dict[str, cp_model.IntVar]
    worst: cp_model.IntVar
    objectives: tuple[Objective, ...]

    def snapshot(self, solver: cp_model.CpSolver) -> Allocation:
        return Allocation(
            selected_candidate_ids=tuple(
                site for site, var in self.opened.items() if solver.value(var)
            ),
            assignments=tuple(
                Assignment(community_id=community, site_id=site, visits=visits)
                for (community, site), var in self.visits.items()
                if (visits := solver.value(var)) > 0
            ),
            unmet_by_community=tuple(
                Unmet(community_id=community, visits=solver.value(var))
                for community, var in self.unmet.items()
            ),
        )

    def hint(self, solver: cp_model.CpSolver) -> None:
        self.program.clear_hints()
        for var in (*self.opened.values(), *self.visits.values(), *self.unmet.values(), self.worst):
            self.program.add_hint(var, solver.value(var))


def _build(
    dataset: Dataset,
    plan: PlanSpec,
    travel: Mapping[Pair, int],
    demand: Mapping[str, int],
    fixed: tuple[str, ...] | None,
) -> Model:
    program = cp_model.CpModel()
    sites = {site.id: site for site in sorted(dataset.sites, key=lambda row: row.id)}
    opened = {
        site.id: program.new_bool_var(f"activate_{site.id}")
        for site in sites.values()
        if site.type == "candidate" and site.eligible
    }
    if fixed is not None:
        for site_id, var in opened.items():
            program.add(var == int(site_id in fixed))

    limits = {
        pair: min(demand[pair[0]], sites[pair[1]].capacity_per_week)
        for pair in sorted(travel)
        if sites[pair[1]].type == "existing"
        or (pair[1] in opened and (fixed is None or pair[1] in fixed))
    }
    # CP-SAT checks activity bounds based on individual variable domains.
    upper_bounds = (
        sum(limits.values()) * 10_000,
        sum(travel[pair] * bound for pair, bound in limits.items()),
        sum(sites[site_id].fixed_cost_pkr for site_id in opened),
        max(demand.values()) * 20_000,
    )
    if max(upper_bounds) >= 2**62:
        raise ValueError("Planning coefficients exceed the supported integer activity bounds.")

    visits = {
        pair: program.new_int_var(0, bound, f"visit_{pair[0]}_{pair[1]}")
        for pair, bound in limits.items()
        if bound
    }
    unmet = {
        community: program.new_int_var(0, amount, f"unmet_{community}")
        for community, amount in demand.items()
    }
    by_community: dict[str, list[cp_model.IntVar]] = {key: [] for key in demand}
    by_site: dict[str, list[cp_model.IntVar]] = {key: [] for key in sites}
    within: dict[str, list[cp_model.IntVar]] = {key: [] for key in demand}
    for pair, var in visits.items():
        community, site_id = pair
        by_community[community].append(var)
        by_site[site_id].append(var)
        if travel[pair] <= plan.threshold_minutes:
            within[community].append(var)

    worst = program.new_int_var(0, 10_000, "worst_cluster_basis_points")
    for community, amount in demand.items():
        program.add(sum(by_community[community]) + unmet[community] == amount)
        if amount > 0:
            covered = sum(within[community])
            program.add(100 * covered >= plan.equity_min_pct * amount)
            program.add(10_000 * covered >= worst * amount)
    for site_id, site in sites.items():
        activation = 1 if site.type == "existing" else opened.get(site_id, 0)
        program.add(sum(by_site[site_id]) <= site.capacity_per_week * activation)

    cost = cp_model.LinearExpr.weighted_sum(
        list(opened.values()), [sites[site_id].fixed_cost_pkr for site_id in opened]
    )
    program.add(cost <= plan.budget_pkr)
    program.add(sum(opened.values()) <= plan.max_new_units)
    objectives: tuple[Objective, ...] = (
        (
            "covered_visits",
            "maximize",
            cp_model.LinearExpr.sum([v for a in within.values() for v in a]),
        ),
        ("served_visits", "maximize", cp_model.LinearExpr.sum(list(visits.values()))),
        ("equity_basis_points", "maximize", worst),
        (
            "assigned_travel_visit_minutes",
            "minimize",
            cp_model.LinearExpr.weighted_sum(list(visits.values()), [travel[p] for p in visits]),
        ),
        ("cost_pkr", "minimize", cost),
    )
    return Model(program, opened, visits, unmet, worst, objectives)


def _run_stage(
    model: cp_model.CpModel, solver: cp_model.CpSolver, cancelled: Stop | None
) -> cp_model.CpSolverStatus:
    if cancelled is None:
        return solver.solve(model)

    done = Event()

    def interrupt() -> None:
        while not done.wait(0.025):
            if cancelled():
                solver.stop_search()

    watcher = Thread(target=interrupt, daemon=True)
    watcher.start()
    try:
        return solver.solve(model)
    finally:
        done.set()
        watcher.join()


def solve(
    dataset: Dataset,
    plan: PlanSpec,
    *,
    kind: Kind = "optimized",
    timeout_seconds: float = 10,
    fixed_candidates: tuple[str, ...] | None = None,
    travel_multiplier_pct: int = 100,
    cancelled: Stop | None = None,
    on_stage: Progress | None = None,
) -> SolveOutcome:
    """Solve an audited baseline, optimized allocation, or fixed selection."""
    start = monotonic()
    plan.validate_for(dataset)
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The solve time limit must be positive and finite.")
    if type(travel_multiplier_pct) is not int or not 1 <= travel_multiplier_pct <= 300:
        raise ValueError("The travel multiplier must be an integer percentage between 1 and 300.")
    if kind == "baseline":
        if fixed_candidates:
            raise ValueError("A baseline cannot activate candidate sites.")
        fixed_candidates = ()
    if kind == "greedy" and fixed_candidates is None:
        raise ValueError("Greedy assignment requires a fixed candidate selection.")
    if fixed_candidates is not None:
        eligible = {site.id for site in dataset.sites if site.type == "candidate" and site.eligible}
        if len(set(fixed_candidates)) != len(fixed_candidates) or not eligible.issuperset(
            fixed_candidates
        ):
            raise ValueError("Fixed candidate selection contains a duplicate or ineligible ID.")

    def elapsed() -> int:
        return round((monotonic() - start) * 1000)

    def stop(status: RunStatus, solver_status: str, message: str) -> SolveOutcome:
        return SolveOutcome(status, solver_status, None, (message,), elapsed())

    if cancelled and cancelled():
        return stop("CANCELLED", "NOT_RUN", "The run was cancelled.")

    deadline = start + timeout_seconds
    demand = {
        row.id: scaled_visits(row.demand_visits_per_week, plan.demand_multiplier_pct)
        for row in sorted(dataset.communities, key=lambda item: item.id)
    }
    travel = scaled_travel(travel_matrix(dataset), travel_multiplier_pct)
    model = _build(dataset, plan, travel, demand, fixed_candidates)
    if diagnostic := model.program.validate():
        return stop("FAILED", "MODEL_INVALID", f"CP-SAT rejected the planning model: {diagnostic}")

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = WORKERS
    solver.parameters.random_seed = plan.seed
    stages: list[ObjectiveStage] = []
    incumbent: Allocation | None = None
    for name, direction, objective in model.objectives:
        if cancelled and cancelled():
            return stop("CANCELLED", "CANCELLED", "The run was cancelled.")
        if on_stage:
            on_stage(name)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        if direction == "maximize":
            model.program.maximize(objective)
        else:
            model.program.minimize(objective)
        solver.parameters.max_time_in_seconds = remaining
        status = _run_stage(model.program, solver, cancelled)
        if cancelled and cancelled():
            return stop("CANCELLED", "CANCELLED", "The run was cancelled.")
        status_name = solver.status_name(status)
        feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        stages.append(
            ObjectiveStage(
                objective=name,
                direction=direction,
                status=status_name,
                value=solver.value(objective) if feasible else None,
                best_bound=(
                    float(solver.best_objective_bound)
                    if feasible or status == cp_model.UNKNOWN
                    else None
                ),
            )
        )
        if feasible:
            incumbent = model.snapshot(solver)
        if status == cp_model.OPTIMAL:
            model.program.add(objective == solver.value(objective))
            model.hint(solver)
            continue
        if status == cp_model.INFEASIBLE and incumbent is None:
            subject = "The baseline" if kind == "baseline" else "This selection"
            return stop(
                "NO_SOLUTION",
                status_name,
                f"{subject} is infeasible under the selected policy. Review the equity floor, "
                "threshold, capacity and budget assumptions.",
            )
        if status not in (cp_model.FEASIBLE, cp_model.UNKNOWN):
            return stop("FAILED", status_name, "The solver could not complete the approved model.")
        break

    if incumbent is None:
        return stop("TIMED_OUT", "UNKNOWN", "The time limit elapsed before a feasible allocation.")
    optimal = len(stages) == len(model.objectives) and all(
        stage.status == "OPTIMAL" for stage in stages
    )
    warnings = (
        ()
        if optimal
        else ("A feasible incumbent was found. The full lexicographic optimum was not proven.",)
    )
    for name, direction, _ in model.objectives[len(stages) :]:
        stages.append(
            ObjectiveStage(
                objective=name,
                direction=direction,
                status="NOT_RUN",
                value=None,
                best_bound=None,
            )
        )
    if on_stage:
        on_stage("AUDITING")
    metrics = compute_metrics(dataset, plan, travel, demand, incumbent)
    serialized = {**incumbent.model_dump(mode="json"), "metrics": metrics.model_dump(mode="json")}
    audit = verify(dataset, plan, travel, demand, serialized, fixed_candidates=fixed_candidates)
    if cancelled and cancelled():
        return stop("CANCELLED", "CANCELLED", "The run was cancelled.")
    if not audit.passed:
        return stop("FAILED", "AUDIT_FAILED", "The independent audit rejected the allocation.")
    runtime_ms = elapsed()
    result = Result(
        selected_candidate_ids=incumbent.selected_candidate_ids,
        assignments=incumbent.assignments,
        unmet_by_community=incumbent.unmet_by_community,
        kind=kind,
        solver_status="OPTIMAL" if optimal else "FEASIBLE",
        dataset_sha256=dataset.sha256,
        plan_hash=plan.plan_hash,
        metrics=metrics,
        objective_stages=tuple(stages),
        audit=audit,
        warnings=warnings,
        runtime_ms=runtime_ms,
        model_version=MODEL_VERSION,
        solver_settings=SolverSettings(
            solver_version=SOLVER_VERSION,
            seed=plan.seed,
            worker_count=WORKERS,
            time_limit_seconds=float(timeout_seconds),
        ),
    )
    return SolveOutcome("COMPLETED", result.solver_status, result, warnings, runtime_ms)
