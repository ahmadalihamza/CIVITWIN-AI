"""Measure the synthetic Bajaur allocation and stress benchmarks."""

import argparse
import json
import os
import platform
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import datetime, timezone
from importlib.metadata import version
from itertools import product
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.domain.comparison import compare_metrics  # noqa: E402
from app.domain.dataset import load_dataset  # noqa: E402
from app.domain.greedy import solve_greedy  # noqa: E402
from app.domain.optimizer import MODEL_VERSION, WORKERS, SolveOutcome, solve  # noqa: E402
from app.domain.stress import run_stress  # noqa: E402
from app.schemas.dataset import Dataset  # noqa: E402
from app.schemas.plan import PlanSpec, default_plan  # noqa: E402

SOLVE_LIMIT_SECONDS = 10
STRESS_LIMIT_SECONDS = 60
OUTPUT_PATH = ROOT / "docs" / "benchmark-results.json"


def _sweep(demo: Dataset) -> Iterator[tuple[str, Dataset, PlanSpec]]:
    plan = default_plan(demo.id)
    for budget, units in product((0, 150_000, 300_000, 450_000), (0, 1, 2)):
        case_id = (
            "bajaur-default" if (budget, units) == (300_000, 2) else f"bajaur-{budget}-{units}"
        )
        yield case_id, demo, plan.model_copy(update={"budget_pkr": budget, "max_new_units": units})
    yield "bajaur-equity-20", demo, plan.model_copy(update={"equity_min_pct": 20})

    for name in ("disconnected", "saturated"):
        fixture_path = ROOT / "services" / "api" / "tests" / "fixtures" / f"{name}.json"
        dataset = load_dataset(fixture_path.read_bytes())
        yield (
            name,
            dataset,
            default_plan(dataset.id).model_copy(
                update={
                    "budget_pkr": 100,
                    "max_new_units": min(1, dataset.eligible_candidate_count),
                    "threshold_minutes": 30,
                }
            ),
        )


def _dataset_shape(dataset: Dataset) -> dict[str, Any]:
    return {
        "id": dataset.id,
        "sha256": dataset.sha256,
        "is_synthetic": dataset.is_synthetic,
        "communities": len(dataset.communities),
        "existing_sites": sum(site.type == "existing" for site in dataset.sites),
        "candidate_sites": sum(site.type == "candidate" for site in dataset.sites),
        "nodes": len(dataset.nodes),
        "edges": len(dataset.edges),
    }


def _observation(outcome: SolveOutcome) -> dict[str, Any]:
    record: dict[str, Any] = {
        "status": outcome.status,
        "solver_status": outcome.solver_status,
        "runtime_ms": outcome.runtime_ms,
        "warnings": list(outcome.warnings),
    }
    result = outcome.result
    if result is not None:
        record.update(
            {
                "selected_candidate_ids": list(result.selected_candidate_ids),
                "metrics": result.metrics.model_dump(mode="json", exclude={"clusters"}),
                "audit_passed": result.audit.passed,
                "audit_result_hash": result.audit.result_hash,
                "objective_stages": [
                    stage.model_dump(mode="json") for stage in result.objective_stages
                ],
            }
        )
    return record


def run() -> dict[str, Any]:
    started = perf_counter()
    measured_at = datetime.now(timezone.utc).isoformat()
    demo = load_dataset((ROOT / "data" / "demo" / "bajaur-v1.json").read_bytes())
    cases: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    published = passed = 0
    stress_report: dict[str, Any] | None = None
    stress_status = "Not run because the default pair had no audited results."
    default_times: dict[str, int] = {}
    for case_id, dataset, plan in _sweep(demo):
        baseline = solve(dataset, plan, kind="baseline", timeout_seconds=SOLVE_LIMIT_SECONDS)
        greedy = solve_greedy(dataset, plan, timeout_seconds=SOLVE_LIMIT_SECONDS)
        optimized = solve(dataset, plan, timeout_seconds=SOLVE_LIMIT_SECONDS)
        outcomes = {"baseline": baseline, "greedy": greedy, "optimized": optimized}
        for outcome in outcomes.values():
            statuses[outcome.status] += 1
            if outcome.result is not None:
                published += 1
                passed += int(outcome.result.audit.passed)
        deltas = {}
        if baseline.result is not None:
            for kind, outcome in (("greedy", greedy), ("optimized", optimized)):
                if outcome.result is not None:
                    deltas[kind] = compare_metrics(baseline.result.metrics, outcome.result.metrics)
        cases.append(
            {
                "case_id": case_id,
                "dataset": _dataset_shape(dataset),
                "plan": plan.model_dump(mode="json"),
                "plan_hash": plan.plan_hash,
                "observations": {kind: _observation(value) for kind, value in outcomes.items()},
                "deltas_from_baseline": deltas,
            }
        )
        if case_id == "bajaur-default":
            default_times = {kind: value.runtime_ms for kind, value in outcomes.items()}
            if baseline.result is not None and optimized.result is not None:
                stress_start = perf_counter()
                stress = run_stress(
                    dataset,
                    plan,
                    baseline_candidates=baseline.result.selected_candidate_ids,
                    alternative_candidates=optimized.result.selected_candidate_ids,
                    seed=plan.seed,
                    case_count=20,
                    timeout_seconds=STRESS_LIMIT_SECONDS,
                )
                stress_report = {
                    "elapsed_ms": round((perf_counter() - stress_start) * 1000),
                    "results": stress.model_dump(mode="json"),
                }
                stress_status = "Measured"
        print(
            f"{case_id}  " + "  ".join(f"{key}={value.status}" for key, value in outcomes.items())
        )

    optimized_ms = default_times["optimized"]
    default_outcome = next(case for case in cases if case["case_id"] == "bajaur-default")[
        "observations"
    ]["optimized"]
    stress_ms = stress_report["elapsed_ms"] if stress_report is not None else None
    return {
        "schema_version": 1,
        "measured_at_utc": measured_at,
        "data_warning": "Synthetic planning fixtures and illustrative scenario sensitivity only.",
        "machine": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "logical_processors": os.cpu_count(),
        },
        "software": {
            "model": MODEL_VERSION,
            "python": platform.python_version(),
            "ortools": version("ortools"),
            "networkx": version("networkx"),
            "numpy": version("numpy"),
        },
        "settings": {
            "worker_count": WORKERS,
            "solve_timeout_seconds": SOLVE_LIMIT_SECONDS,
            "stress_timeout_seconds": STRESS_LIMIT_SECONDS,
        },
        "performance_targets": {
            "default_solve": {
                "target_ms": 10_000,
                "elapsed_ms": optimized_ms,
                "passed": default_outcome["status"] == "COMPLETED" and optimized_ms <= 10_000,
            },
            "default_20_case_stress": {
                "target_ms": 60_000,
                "elapsed_ms": stress_ms,
                "passed": stress_ms is not None and stress_ms <= 60_000,
            },
        },
        "default_solver_runtime_ms": default_times,
        "constraint_audit": {
            "published_results": published,
            "passed": passed,
            "pass_rate_pct": 100 * passed / published if published else None,
            "status_counts": dict(statuses),
        },
        "stress_status": stress_status,
        "stress": stress_report,
        "cases": cases,
        "overall_elapsed_ms": round((perf_counter() - started) * 1000),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Recorded {len(report['cases'])} benchmark cases in {args.output}")


if __name__ == "__main__":
    main()
