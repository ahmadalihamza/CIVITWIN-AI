"""Back up and reset the local synthetic database after explicit confirmation."""

import sys
from pathlib import Path

from sqlalchemy import delete, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from app.config import Settings  # noqa: E402
from app.db.models import DatasetVersion, EventLog, Run, Scenario, StressRun  # noqa: E402
from app.db.store import Store, backup_database, persist_dataset  # noqa: E402
from app.domain.dataset import load_dataset  # noqa: E402


def main():
    settings = Settings.from_env()
    if not settings.demo_mode:
        raise SystemExit("Reset requires DEMO_MODE=true.")
    store = Store(settings)
    try:
        if store.path is None:
            raise SystemExit("Reset requires a persistent local SQLite file.")
        print(
            f"Stop the planner first. Resetting {store.path} archives the current database and clears its planning history."
        )
        if input("Type RESET DEMO to proceed: ") != "RESET DEMO":
            raise SystemExit("Reset cancelled.")
        dataset = load_dataset(settings.demo_path.read_bytes())
        if not dataset.is_synthetic:
            raise SystemExit("The configured demo seed must be synthetic.")
        store.prepare()
        with store.sessions.begin() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            backup = backup_database(store.path)
            for entity in (StressRun, Run, Scenario, EventLog, DatasetVersion):
                session.execute(delete(entity))
            persist_dataset(session, dataset)
        print(f"Restored the synthetic seed. Previous database saved at {backup}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
