from pathlib import Path
from sqlite3 import connect

import pytest
from app.config import Settings
from app.db.models import DatasetVersion, EventLog, Scenario
from app.db.store import DatasetConflict, Store, load_version, persist_dataset
from app.domain.dataset import create_dataset, dataset_payload
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError


def test_migration_seed_and_reopen(tmp_path):
    path = tmp_path / "nested" / "planning.db"
    settings = Settings(database_url=f"sqlite:///{path.as_posix()}")
    store = Store(settings)
    store.prepare()
    assert {
        "alembic_version",
        "dataset_versions",
        "event_log",
        "scenarios",
        "runs",
        "stress_runs",
    } == set(inspect(store.engine).get_table_names())
    store.close()
    store = Store(settings)
    store.prepare()
    with store.sessions() as session:
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 1
        assert session.scalar(select(func.count()).select_from(EventLog)) == 1
        record = session.get(DatasetVersion, "demo-bajaur-v1")
        assert load_version(record).is_synthetic
    assert not list(path.parent.glob("*.bak"))
    store.close()


def test_store_enforces_foreign_keys_and_immutable_dataset():
    store = Store(Settings(database_url="sqlite:///:memory:"))
    store.prepare()
    with pytest.raises(IntegrityError), store.sessions.begin() as session:
        session.add(
            Scenario(
                id="invalid",
                dataset_id="missing",
                plan_json={},
                plan_hash="x" * 64,
                status="VALIDATED",
            )
        )

    with pytest.raises(DatasetConflict), store.sessions.begin() as session:
        stored = session.get(DatasetVersion, "demo-bajaur-v1")
        payload = dataset_payload(load_version(stored))
        del payload["sha256"]
        payload["assumptions"].append("Modified content cannot reuse the version identifier.")
        persist_dataset(session, create_dataset(payload))
    with store.sessions() as session:
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 1
        assert session.scalar(select(func.count()).select_from(EventLog)) == 1
    store.close()


def test_migration_preserves_existing_file_and_makes_backup(tmp_path: Path):
    path = tmp_path / "existing.db"
    with connect(path) as connection:
        connection.execute("CREATE TABLE preserve_me (value INTEGER)")
        connection.execute("INSERT INTO preserve_me VALUES (42)")
    connection.close()

    store = Store(Settings(database_url=f"sqlite:///{path.as_posix()}", demo_mode=False))
    store.prepare()
    store.close()
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1
    for file in (path, backups[0]):
        with connect(file) as connection:
            assert connection.execute("SELECT value FROM preserve_me").fetchone() == (42,)
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            assert ("dataset_versions" in tables) == (file == path)
        connection.close()
