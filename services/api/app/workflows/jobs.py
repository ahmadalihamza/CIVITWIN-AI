"""Bounded local execution and transactional run publication."""

import logging
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Event, Lock
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select, union_all, update
from sqlalchemy.orm import Session

from app.db.models import DatasetVersion, JobState, Run, Scenario, StressRun
from app.db.store import Store, append_event, load_version, utc_now
from app.domain.dataset import canonical_json
from app.domain.greedy import solve_greedy
from app.domain.optimizer import SOLVER_VERSION, SolveOutcome, solve
from app.domain.stress import run_stress
from app.schemas.api import StressRequest
from app.schemas.plan import PlanSpec

RunKind = Literal["baseline", "optimized", "greedy"]
ACTIVE = ("QUEUED", "RUNNING", "AUDITING")
LOGGER = logging.getLogger(__name__)


class JobError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "field_errors": []}


class JobManager:
    def __init__(
        self, store: Store, timeout_seconds: float, stress_timeout_seconds: float = 60
    ) -> None:
        self.store = store
        self.timeout_seconds = timeout_seconds
        self.stress_timeout_seconds = stress_timeout_seconds
        self._lock = Lock()
        self._closing = Event()
        self._cancellations: dict[str, Event] = {}
        self._recover_interrupted_runs()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="civitwin-job")

    def _recover_interrupted_runs(self) -> None:
        with self.store.sessions.begin() as session:

            def recover(entity: str, run: JobState) -> None:
                run.status = "INTERRUPTED"
                run.progress_stage = "INTERRUPTED"
                run.updated_at = run.completed_at = utc_now()
                run.error_json = _error(
                    "INTERRUPTED", "The planner stopped before the run finished."
                )
                append_event(session, entity, run.id, "INTERRUPTED")

            for run in session.scalars(select(Run).where(Run.status.in_(ACTIVE))):
                recover("run", run)
            for stress in session.scalars(select(StressRun).where(StressRun.status.in_(ACTIVE))):
                recover("stress_run", stress)

    @staticmethod
    def _require_available(session: Session) -> None:
        active = union_all(
            select(Run.id).where(Run.status.in_(ACTIVE)),
            select(StressRun.id).where(StressRun.status.in_(ACTIVE)),
        )
        if session.execute(active.limit(1)).first() is not None:
            raise JobError(
                429, "JOB_LIMIT", "The planner is busy. Try again when the active job ends."
            )

    def submit(self, scenario_id: str, kind: RunKind, key: str | None = None) -> str:
        if kind not in ("baseline", "optimized", "greedy"):
            raise JobError(422, "INVALID_RUN_KIND", "Choose baseline, optimized, or greedy.")
        if key is not None and (
            not key or len(key) > 128 or not key.isascii() or not key.isprintable()
        ):
            raise JobError(
                422, "INVALID_JOB_KEY", "Use a printable job key of up to 128 characters."
            )
        request_hash = sha256(
            canonical_json({"scenario_id": scenario_id, "kind": kind})
        ).hexdigest()
        with self._lock:
            if self._closing.is_set():
                raise JobError(503, "PLANNER_UNAVAILABLE", "The planner is shutting down.")
            with self.store.sessions.begin() as session:
                if key is not None:
                    if session.scalar(select(StressRun.id).where(StressRun.job_key == key)):
                        raise JobError(409, "JOB_KEY_CONFLICT", "This job key has another request.")
                    existing = session.scalar(select(Run).where(Run.job_key == key))
                    if existing is not None:
                        if existing.request_hash != request_hash:
                            raise JobError(
                                409, "JOB_KEY_CONFLICT", "This job key has another request."
                            )
                        return existing.id
                scenario = session.get(Scenario, scenario_id)
                if scenario is None:
                    raise JobError(404, "SCENARIO_NOT_FOUND", "Scenario was not found.")
                if scenario.status != "CONFIRMED":
                    raise JobError(
                        409, "PLAN_NOT_CONFIRMED", "Confirm the plan before submitting a run."
                    )
                self._require_available(session)
                run_id = f"run-{uuid4().hex}"
                session.add(
                    Run(
                        id=run_id,
                        scenario_id=scenario_id,
                        kind=kind,
                        status="QUEUED",
                        progress_stage="QUEUED",
                        job_key=key,
                        request_hash=request_hash,
                    )
                )
                append_event(session, "run", run_id, "QUEUED", {"kind": kind})
            cancelled = Event()
            self._cancellations[run_id] = cancelled
            self._executor.submit(self._work, run_id, kind, cancelled)
        return run_id

    def submit_stress(self, request: StressRequest, key: str | None = None) -> str:
        request_hash = sha256(canonical_json(request.model_dump(mode="json"))).hexdigest()
        with self._lock:
            if self._closing.is_set():
                raise JobError(503, "PLANNER_UNAVAILABLE", "The planner is shutting down.")
            with self.store.sessions.begin() as session:
                if key is not None:
                    if session.scalar(select(Run.id).where(Run.job_key == key)):
                        raise JobError(409, "JOB_KEY_CONFLICT", "This job key has another request.")
                    existing = session.scalar(select(StressRun).where(StressRun.job_key == key))
                    if existing is not None:
                        if existing.request_hash != request_hash:
                            raise JobError(
                                409, "JOB_KEY_CONFLICT", "This job key has another request."
                            )
                        return existing.id
                base = session.get(Run, request.baseline_run_id)
                alt = session.get(Run, request.alternative_run_id)
                if base is None or alt is None:
                    raise JobError(404, "RUN_NOT_FOUND", "A referenced run was not found.")
                baseline, alternative = base.result_json, alt.result_json
                if (
                    base.status != "COMPLETED"
                    or alt.status != "COMPLETED"
                    or not baseline
                    or not alternative
                    or not baseline["audit"]["passed"]
                    or not alternative["audit"]["passed"]
                ):
                    raise JobError(
                        409, "RUN_NOT_AUDITED", "Stress testing requires two audited runs."
                    )
                if base.kind != "baseline" or alt.kind == "baseline":
                    raise JobError(
                        422, "INVALID_RUN_KINDS", "Choose one baseline and one alternative."
                    )
                if (
                    baseline["dataset_sha256"] != alternative["dataset_sha256"]
                    or baseline["plan_hash"] != alternative["plan_hash"]
                ):
                    raise JobError(
                        409, "INCOMPATIBLE_COMPARISON", "The runs must share a dataset and plan."
                    )
                self._require_available(session)
                run_id = f"stress-{uuid4().hex}"
                session.add(
                    StressRun(
                        id=run_id,
                        baseline_run_id=base.id,
                        alternative_run_id=alt.id,
                        seed=request.seed,
                        case_count=request.case_count,
                        status="QUEUED",
                        progress_stage="QUEUED",
                        job_key=key,
                        request_hash=request_hash,
                    )
                )
                append_event(session, "stress_run", run_id, "QUEUED")
            self._executor.submit(self._work_stress, run_id)
        return run_id

    def _work_stress(self, run_id: str) -> None:
        try:
            with self.store.sessions.begin() as session:
                row = session.get(StressRun, run_id)
                if row is None or row.status != "QUEUED":
                    return
                row.status = row.progress_stage = "RUNNING"
                row.started_at = row.updated_at = utc_now()
                base = session.get(Run, row.baseline_run_id)
                alt = session.get(Run, row.alternative_run_id)
                assert base and base.result_json and alt and alt.result_json
                scenario = session.get(Scenario, base.scenario_id)
                assert scenario is not None
                version = session.get(DatasetVersion, scenario.dataset_id)
                assert version is not None
                dataset = load_version(version)
                plan = PlanSpec.model_validate(scenario.plan_json)
                if (
                    plan.plan_hash != base.result_json["plan_hash"]
                    or dataset.sha256 != base.result_json["dataset_sha256"]
                ):
                    raise ValueError("The stress inputs did not match the audited run.")
                baseline = tuple(base.result_json["selected_candidate_ids"])
                alternative = tuple(alt.result_json["selected_candidate_ids"])
                append_event(session, "stress_run", run_id, "RUNNING")
            result = run_stress(
                dataset,
                plan,
                baseline_candidates=baseline,
                alternative_candidates=alternative,
                seed=row.seed,
                case_count=row.case_count,
                timeout_seconds=self.stress_timeout_seconds,
                cancelled=self._closing.is_set,
                on_case=lambda current, total: self._stress_progress(run_id, current, total),
            )
            if result.cancelled:
                self._finish_stress(
                    run_id,
                    "INTERRUPTED",
                    error=_error(
                        "INTERRUPTED", "The planner stopped before the stress suite finished."
                    ),
                )
            else:
                self._finish_stress(
                    run_id,
                    "COMPLETED",
                    result=result.model_dump(mode="json")
                    | {
                        "dataset_sha256": dataset.sha256,
                        "plan_hash": plan.plan_hash,
                        "baseline_candidates": baseline,
                        "alternative_candidates": alternative,
                    },
                )
        except Exception as exc:
            LOGGER.error("Stress run failed run_id=%s error_type=%s", run_id, type(exc).__name__)
            self._finish_stress(
                run_id,
                "FAILED",
                error=_error("STRESS_FAILED", "The planner could not complete the stress suite."),
            )

    def _stress_progress(self, run_id: str, current: int, total: int) -> None:
        with self.store.sessions.begin() as session:
            session.execute(
                update(StressRun)
                .where(StressRun.id == run_id, StressRun.status == "RUNNING")
                .values(progress_stage=f"Case {current} of {total}", updated_at=utc_now())
            )

    def _finish_stress(
        self,
        run_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self.store.sessions.begin() as session:
            changed = session.execute(
                update(StressRun)
                .where(StressRun.id == run_id, StressRun.status.in_(ACTIVE))
                .values(
                    status=status,
                    progress_stage=status,
                    results_json=result,
                    error_json=error,
                    runtime_ms=result["runtime_ms"] if result else None,
                    updated_at=utc_now(),
                    completed_at=utc_now(),
                )
                .returning(StressRun.id)
            ).scalar_one_or_none()
            if changed:
                append_event(session, "stress_run", run_id, status)

    def cancel(self, run_id: str) -> None:
        with self._lock:
            with self.store.sessions.begin() as session:
                now = utc_now()
                updated = session.execute(
                    update(Run)
                    .where(Run.id == run_id, Run.status.in_(ACTIVE))
                    .values(
                        status="CANCELLED",
                        progress_stage="CANCELLED",
                        cancel_requested=True,
                        updated_at=now,
                        completed_at=now,
                        error_json=_error("CANCELLED", "The run was cancelled."),
                    )
                    .returning(Run.id)
                ).scalar_one_or_none()
                if updated is None:
                    if session.get(Run, run_id) is None:
                        raise JobError(404, "RUN_NOT_FOUND", "Run was not found.")
                    raise JobError(409, "RUN_TERMINAL", "This run already finished.")
                append_event(session, "run", run_id, "CANCELLED")
            if cancelled := self._cancellations.get(run_id):
                cancelled.set()

    def close(self) -> None:
        with self._lock:
            self._closing.set()
        self._executor.shutdown(wait=True)

    def _work(self, run_id: str, kind: RunKind, cancelled: Event) -> None:
        try:
            with self.store.sessions.begin() as session:
                now = utc_now()
                scenario_id = session.execute(
                    update(Run)
                    .where(Run.id == run_id, Run.status == "QUEUED")
                    .values(
                        status="RUNNING", progress_stage="RUNNING", started_at=now, updated_at=now
                    )
                    .returning(Run.scenario_id)
                ).scalar_one_or_none()
                if scenario_id is None:
                    return
                append_event(session, "run", run_id, "RUNNING")
                scenario = session.get(Scenario, scenario_id)
                if scenario is None or scenario.status != "CONFIRMED":
                    raise ValueError("The confirmed plan could not be loaded.")
                version = session.get(DatasetVersion, scenario.dataset_id)
                if version is None:
                    raise ValueError("The dataset version could not be loaded.")
                plan = PlanSpec.model_validate(scenario.plan_json)
                if plan.plan_hash != scenario.plan_hash:
                    raise ValueError("The stored plan hash does not match.")
                dataset = load_version(version)

            def is_cancelled() -> bool:
                return cancelled.is_set() or self._closing.is_set()

            def on_stage(stage: str) -> None:
                self._progress(run_id, stage)

            if kind == "greedy":
                outcome = solve_greedy(
                    dataset,
                    plan,
                    timeout_seconds=self.timeout_seconds,
                    cancelled=is_cancelled,
                    on_stage=on_stage,
                )
            else:
                outcome = solve(
                    dataset,
                    plan,
                    kind=kind,
                    timeout_seconds=self.timeout_seconds,
                    cancelled=is_cancelled,
                    on_stage=on_stage,
                )
            if self._closing.is_set() and outcome.status == "CANCELLED":
                self._finish(run_id, "INTERRUPTED", outcome.solver_status)
            else:
                self._complete(run_id, scenario_id, outcome)
        except Exception as exc:
            LOGGER.error("Planner run failed run_id=%s error_type=%s", run_id, type(exc).__name__)
            self._finish(run_id, "FAILED", "ERROR")
        finally:
            with self._lock:
                self._cancellations.pop(run_id, None)

    def _progress(self, run_id: str, stage: str) -> None:
        status = "AUDITING" if stage == "AUDITING" else "RUNNING"
        with self.store.sessions.begin() as session:
            updated = session.execute(
                update(Run)
                .where(Run.id == run_id, Run.status == "RUNNING")
                .values(status=status, progress_stage=stage, updated_at=utc_now())
                .returning(Run.id)
            ).scalar_one_or_none()
            if updated is not None:
                append_event(session, "run", run_id, status, {"stage": stage})

    def _complete(self, run_id: str, scenario_id: str, outcome: SolveOutcome) -> None:
        if outcome.status != "COMPLETED":
            self._finish(
                run_id,
                outcome.status,
                outcome.solver_status,
                runtime_ms=outcome.runtime_ms,
                message=outcome.warnings[0]
                if outcome.warnings and outcome.status != "FAILED"
                else None,
            )
            return
        result = outcome.result
        if result is None:
            self._finish(run_id, "FAILED", "AUDIT_FAILED", runtime_ms=outcome.runtime_ms)
            return
        payload = result.model_dump(mode="json")
        audited_fields = {
            key: payload[key]
            for key in ("selected_candidate_ids", "assignments", "unmet_by_community", "metrics")
        }
        if (
            not result.audit.passed
            or not result.audit.checks
            or not all(check.passed for check in result.audit.checks)
            or result.audit.result_hash != sha256(canonical_json(audited_fields)).hexdigest()
        ):
            self._finish(run_id, "FAILED", "AUDIT_FAILED", runtime_ms=outcome.runtime_ms)
            return
        self._finish(
            run_id,
            "COMPLETED",
            result.solver_status,
            runtime_ms=result.runtime_ms,
            solver_version=result.solver_settings.solver_version,
            result_json={
                **payload,
                "run_id": run_id,
                "scenario_id": scenario_id,
                "status": "COMPLETED",
            },
            audit_json=payload["audit"],
        )

    def _finish(
        self,
        run_id: str,
        status: str,
        solver_status: str,
        *,
        message: str | None = None,
        runtime_ms: int | None = None,
        solver_version: str | None = None,
        result_json: dict[str, Any] | None = None,
        audit_json: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        error = None
        if status != "COMPLETED":
            error = _error(solver_status, message or "The planner could not complete this run.")
        expected = ("AUDITING",) if status == "COMPLETED" else ACTIVE
        with self.store.sessions.begin() as session:
            updated = session.execute(
                update(Run)
                .where(Run.id == run_id, Run.status.in_(expected), Run.cancel_requested.is_(False))
                .values(
                    status=status,
                    progress_stage=status,
                    solver_status=solver_status,
                    solver_version=solver_version or SOLVER_VERSION,
                    runtime_ms=runtime_ms,
                    completed_at=now,
                    updated_at=now,
                    error_json=error,
                    result_json=result_json,
                    audit_json=audit_json,
                )
                .returning(Run.id)
            ).scalar_one_or_none()
            if updated is not None:
                append_event(
                    session,
                    "run",
                    run_id,
                    status,
                    {"solver_status": solver_status, "runtime_ms": runtime_ms},
                )
