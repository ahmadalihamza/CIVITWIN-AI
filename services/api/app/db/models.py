from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Base(DeclarativeBase):
    pass


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    district: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(35), default=utc_now)


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    plan_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))
    confirmed_at: Mapped[str | None] = mapped_column(String(35))
    created_at: Mapped[str] = mapped_column(String(35), default=utc_now)


class JobState:
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    job_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    progress_stage: Mapped[str | None] = mapped_column(String(80))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    runtime_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(35), default=utc_now)
    updated_at: Mapped[str] = mapped_column(String(35), default=utc_now)
    started_at: Mapped[str | None] = mapped_column(String(35))
    completed_at: Mapped[str | None] = mapped_column(String(35))


class Run(JobState, Base):
    __tablename__ = "runs"

    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    solver_version: Mapped[str | None] = mapped_column(String(80))
    solver_status: Mapped[str | None] = mapped_column(String(30))
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    audit_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))


class StressRun(JobState, Base):
    __tablename__ = "stress_runs"

    baseline_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    alternative_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    seed: Mapped[int] = mapped_column(Integer)
    case_count: Mapped[int] = mapped_column(Integer)
    results_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))


class EventLog(Base):
    __tablename__ = "event_log"
    __table_args__ = (Index("ix_event_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(80))
    event: Mapped[str] = mapped_column(String(40))
    timestamp: Mapped[str] = mapped_column(String(35), default=utc_now)
    actor_label: Mapped[str] = mapped_column(String(30), default="local-planner")
    safe_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
