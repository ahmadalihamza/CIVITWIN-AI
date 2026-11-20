from pathlib import Path

import pytest
from app.config import Settings
from app.db.models import DatasetVersion
from app.db.store import Store, persist_dataset
from app.domain.dataset import load_dataset

from scripts.reset_demo import main


def test_confirmed_demo_reset_preserves_a_restorable_backup(tmp_path, monkeypatch):
    database = tmp_path / "reset.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DEMO_MODE", "true")
    settings = Settings(database_url=url)
    store = Store(settings)
    store.prepare()
    fixture = load_dataset((Path(__file__).parents[1] / "fixtures/golden.json").read_bytes())
    with store.sessions.begin() as session:
        persist_dataset(session, fixture)
    store.close()

    monkeypatch.setattr("builtins.input", lambda prompt: "cancel")
    with pytest.raises(SystemExit, match="cancelled"):
        main()
    assert not list(tmp_path.glob("*.bak"))

    monkeypatch.setattr("builtins.input", lambda prompt: "RESET DEMO")
    main()
    (backup,) = tmp_path.glob("*.bak")
    for path, expected in ((database, False), (backup, True)):
        restored = Store(Settings(database_url=f"sqlite:///{path.as_posix()}"))
        with restored.sessions() as session:
            assert session.get(DatasetVersion, "demo-bajaur-v1") is not None
            assert (session.get(DatasetVersion, fixture.id) is not None) is expected
        restored.close()
