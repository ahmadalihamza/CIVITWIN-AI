from dataclasses import replace
from threading import Event
from time import monotonic, sleep

import pytest
from app.config import Settings
from app.db.models import DatasetVersion, EventLog, Run, Scenario
from app.db.store import Store
from app.domain.optimizer import solve
from app.schemas.plan import default_plan
from app.workflows import jobs
from app.workflows.jobs import ACTIVE, JobError, JobManager
from sqlalchemy import select


@pytest.fixture
def job_store(tmp_path):
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'job-tests.db').as_posix()}")
    store = Store(settings)
    store.prepare()
    plan = default_plan()
    with store.sessions.begin() as session:
        assert session.get(DatasetVersion, plan.dataset_version_id) is not None
        for scenario_id, status in (("confirmed", "CONFIRMED"), ("draft", "VALIDATED")):
            session.add(
                Scenario(
                    id=scenario_id,
                    dataset_id=plan.dataset_version_id,
                    plan_json=plan.model_dump(mode="json"),
                    plan_hash=plan.plan_hash,
                    status=status,
                )
            )
    yield store
    store.engine.dispose()


def wait_for_terminal(store: Store, run_id: str) -> Run:
    deadline = monotonic() + 10
    while monotonic() < deadline:
        with store.sessions() as session:
            run = session.get(Run, run_id)
            assert run is not None
            if run.status not in ACTIVE:
                return run
        sleep(0.01)
    pytest.fail(f"Run {run_id} did not reach a terminal state")


def test_real_job_persists_audited_result_and_idempotent_retry(job_store):
    manager = JobManager(job_store, 10)
    try:
        with pytest.raises(JobError, match="Confirm the plan") as raised:
            manager.submit("draft", "baseline")
        assert raised.value.status_code == 409
        run_id = manager.submit("confirmed", "baseline", "example-key")
        assert manager.submit("confirmed", "baseline", "example-key") == run_id
        with pytest.raises(JobError, match="another request") as raised:
            manager.submit("confirmed", "optimized", "example-key")
        assert raised.value.status_code == 409
        completed = wait_for_terminal(job_store, run_id)
        assert completed.status == "COMPLETED"
        assert completed.result_json["audit"]["passed"]
        assert completed.result_json["audit"] == completed.audit_json
        assert completed.result_json["run_id"] == run_id
        assert completed.result_json["scenario_id"] == "confirmed"
        assert completed.result_json["metrics"]["total_demand"] > 0
        with pytest.raises(JobError, match="already finished") as raised:
            manager.cancel(run_id)
        assert raised.value.status_code == 409
        with job_store.sessions() as session:
            events = session.scalars(
                select(EventLog.event).where(EventLog.entity_id == run_id).order_by(EventLog.id)
            ).all()
        assert events[:2] == ["QUEUED", "RUNNING"]
        assert events[-2:] == ["AUDITING", "COMPLETED"]
    finally:
        manager.close()


def test_cancel_while_active_blocks_result_publication_and_admission_is_bounded(
    job_store, monkeypatch
):
    entered = Event()
    release = Event()

    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return solve(*args, **kwargs)

    monkeypatch.setattr(jobs, "solve", pause)
    manager = JobManager(job_store, 10)
    try:
        run_id = manager.submit("confirmed", "optimized", "current-job")
        assert entered.wait(5)
        assert manager.submit("confirmed", "optimized", "current-job") == run_id
        with pytest.raises(JobError) as raised:
            manager.submit("confirmed", "baseline", "waiting-job")
        assert raised.value.status_code == 429
        manager.cancel(run_id)
    finally:
        release.set()
        manager.close()
    cancelled = wait_for_terminal(job_store, run_id)
    assert cancelled.status == "CANCELLED"
    assert cancelled.result_json is cancelled.audit_json is None
    assert cancelled.error_json["code"] == "CANCELLED"


def test_restart_marks_unfinished_runs_and_timeout_has_no_result(job_store):
    with job_store.sessions.begin() as session:
        session.add(
            Run(
                id="unfinished",
                scenario_id="confirmed",
                kind="baseline",
                status="AUDITING",
                request_hash="a" * 64,
            )
        )
    manager = JobManager(job_store, 1e-8)
    try:
        interrupted = wait_for_terminal(job_store, "unfinished")
        assert interrupted.status == "INTERRUPTED"
        assert interrupted.result_json is interrupted.audit_json is None
        timeout_id = manager.submit("confirmed", "baseline")
        timeout = wait_for_terminal(job_store, timeout_id)
        assert timeout.status == "TIMED_OUT"
        assert timeout.result_json is timeout.audit_json is None
    finally:
        manager.close()


def test_result_changed_after_audit_cannot_be_published(job_store, monkeypatch):
    def changed_after_audit(*args, **kwargs):
        outcome = solve(*args, **kwargs)
        assert outcome.result is not None
        original = outcome.result
        modified = original.metrics.model_copy(update={"coverage_pct": 100.0})
        return replace(outcome, result=original.model_copy(update={"metrics": modified}))

    monkeypatch.setattr(jobs, "solve", changed_after_audit)
    manager = JobManager(job_store, 10)
    try:
        run_id = manager.submit("confirmed", "baseline")
        rejected = wait_for_terminal(job_store, run_id)
        assert rejected.status == "FAILED"
        assert rejected.solver_status == "AUDIT_FAILED"
        assert rejected.result_json is rejected.audit_json is None
    finally:
        manager.close()
