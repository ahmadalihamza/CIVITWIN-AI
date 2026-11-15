from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from sqlite3 import connect as sqlite_connect
from typing import Any
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import ROOT, Settings
from app.db.models import DatasetVersion, EventLog
from app.db.models import utc_now as utc_now
from app.domain.dataset import canonical_json, dataset_payload, load_dataset
from app.schemas.dataset import Dataset

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
ENTITY_TABLES = {"nodes", "edges", "communities", "sites"}


class DatasetConflict(ValueError):
    """An immutable version ID or digest already belongs to other content."""


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        url = make_url(settings.database_url)
        if url.get_backend_name() != "sqlite" or url.get_driver_name() != "pysqlite":
            raise ValueError("The local demo requires SQLite using the pysqlite driver.")
        if url.query:
            raise ValueError("SQLite URI options are unsupported by the local demo.")
        database = url.database
        self.path: Path | None = None
        if database not in {None, "", ":memory:"}:
            self.path = Path(database or "").resolve()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=self.path.as_posix())
        pool = {} if self.path is not None else {"poolclass": StaticPool}
        self.engine = create_engine(
            url, connect_args={"check_same_thread": False, "timeout": 10}, **pool
        )
        event.listen(self.engine, "connect", _enable_foreign_keys)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def prepare(self) -> None:
        config = migration_config()
        target = ScriptDirectory.from_config(config).get_current_head()
        with self.engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
            if current != target:
                if self.path is not None:
                    backup_database(self.path)
                connection.commit()
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                connection.commit()
        if self.settings.demo_mode:
            dataset = load_dataset(self.settings.demo_path.read_bytes())
            if not dataset.is_synthetic:
                raise ValueError("The demo seed must be explicitly synthetic.")
            with self.sessions.begin() as session:
                persist_dataset(session, dataset)

    def close(self) -> None:
        self.engine.dispose()


def _enable_foreign_keys(dbapi_connection: SQLiteConnection, _connection_record: object) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def migration_config() -> Config:
    config = Config(str(ROOT / "services/api/alembic.ini"))
    config.set_main_option("script_location", MIGRATIONS.as_posix().replace("%", "%%"))
    return config


def backup_database(path: Path) -> Path | None:
    """Create a consistent SQLite backup; empty initial files require no backup."""
    if not path.is_file() or path.stat().st_size == 0:
        return None
    stamp = utc_now().replace(":", "").replace("+0000", "Z")
    target = path.with_name(f"{path.name}.{stamp}.{uuid4().hex[:8]}.bak")
    with target.open("xb"):
        pass
    destination = sqlite_connect(target)
    try:
        source = sqlite_connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            source.backup(destination)
        finally:
            source.close()
    except Exception:
        destination.close()
        target.unlink()
        raise
    destination.close()
    return target


def dataset_record(dataset: Dataset) -> DatasetVersion:
    payload = dataset_payload(dataset)
    return DatasetVersion(
        id=dataset.id,
        district=dataset.district_label,
        version=dataset.version,
        sha256=dataset.sha256,
        manifest_json={key: value for key, value in payload.items() if key not in ENTITY_TABLES},
        payload_json=payload,
    )


def load_version(record: DatasetVersion) -> Dataset:
    dataset = load_dataset(canonical_json(record.payload_json))
    payload = dataset_payload(dataset)
    expected_manifest = {key: value for key, value in payload.items() if key not in ENTITY_TABLES}
    if (
        dataset.id != record.id
        or dataset.sha256 != record.sha256
        or dataset.version != record.version
        or dataset.district_label != record.district
        or expected_manifest != record.manifest_json
    ):
        raise ValueError("Stored dataset metadata does not match its immutable content.")
    return dataset


def persist_dataset(session: Session, dataset: Dataset) -> DatasetVersion:
    dataset = load_dataset(canonical_json(dataset_payload(dataset)))
    record = dataset_record(dataset)
    inserted = session.execute(
        insert(DatasetVersion)
        .values(
            id=record.id,
            district=record.district,
            version=record.version,
            sha256=record.sha256,
            manifest_json=record.manifest_json,
            payload_json=record.payload_json,
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
        .returning(DatasetVersion.id)
    ).scalar_one_or_none()
    stored = session.get(DatasetVersion, dataset.id)
    if stored is None:
        raise DatasetConflict("The dataset digest already exists under a different version ID.")
    if load_version(stored) != dataset:
        raise DatasetConflict("The dataset version ID is immutable. Choose a new version ID.")
    if inserted is not None:
        append_event(session, "dataset", dataset.id, "PUBLISHED", {"sha256": dataset.sha256})
    return stored


def append_event(
    session: Session,
    entity_type: str,
    entity_id: str,
    event: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        EventLog(
            entity_type=entity_type,
            entity_id=entity_id,
            event=event,
            safe_metadata_json=metadata or {},
        )
    )
