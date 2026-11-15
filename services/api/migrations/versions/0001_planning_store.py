"""Create immutable dataset versions and persistent planning history."""

import sqlalchemy as sa
from alembic import op

revision = "0001_planning_store"
down_revision = None
branch_labels = None
depends_on = None


def _job_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("job_key", sa.String(128), unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("progress_stage", sa.String(80)),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error_json", sa.JSON(none_as_null=True)),
        sa.Column("runtime_ms", sa.Integer()),
        sa.Column("created_at", sa.String(35), nullable=False),
        sa.Column("updated_at", sa.String(35), nullable=False),
        sa.Column("started_at", sa.String(35)),
        sa.Column("completed_at", sa.String(35)),
    )


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("district", sa.String(160), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(35), nullable=False),
    )
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "dataset_id", sa.String(80), sa.ForeignKey("dataset_versions.id"), nullable=False
        ),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("confirmed_at", sa.String(35)),
        sa.Column("created_at", sa.String(35), nullable=False),
    )
    op.create_index("ix_scenarios_dataset_id", "scenarios", ["dataset_id"])
    op.create_index("ix_scenarios_plan_hash", "scenarios", ["plan_hash"])
    op.create_table(
        "runs",
        *_job_columns(),
        sa.Column("scenario_id", sa.String(80), sa.ForeignKey("scenarios.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("solver_version", sa.String(80)),
        sa.Column("solver_status", sa.String(30)),
        sa.Column("result_json", sa.JSON(none_as_null=True)),
        sa.Column("audit_json", sa.JSON(none_as_null=True)),
    )
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_scenario_id", "runs", ["scenario_id"])
    op.create_table(
        "stress_runs",
        *_job_columns(),
        sa.Column("baseline_run_id", sa.String(80), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("alternative_run_id", sa.String(80), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("results_json", sa.JSON(none_as_null=True)),
    )
    op.create_index("ix_stress_runs_status", "stress_runs", ["status"])
    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=False),
        sa.Column("event", sa.String(40), nullable=False),
        sa.Column("timestamp", sa.String(35), nullable=False),
        sa.Column("actor_label", sa.String(30), nullable=False),
        sa.Column("safe_metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_event_entity", "event_log", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("event_log")
    op.drop_table("stress_runs")
    op.drop_table("runs")
    op.drop_table("scenarios")
    op.drop_table("dataset_versions")
