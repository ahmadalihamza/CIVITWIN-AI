"""Exercise the offline API and persistence with an isolated synthetic demo database."""

import csv
import io
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.schemas.plan import default_plan  # noqa: E402

API = "/api/v1"


def completed_run(client, scenario_url, kind):
    queued = client.post(scenario_url + "/runs", json={"kind": kind})
    queued.raise_for_status()
    url = f"{API}/runs/{queued.json()['run_id']}"
    deadline = monotonic() + 30
    while monotonic() < deadline:
        response = client.get(url)
        response.raise_for_status()
        run = response.json()
        if run["status"] == "COMPLETED":
            assert run["result"]["audit"]["passed"]
            return run
        if run["status"] not in {"QUEUED", "RUNNING", "AUDITING"}:
            raise RuntimeError(f"{kind} ended with {run['status']}")
        sleep(0.1)
    raise TimeoutError(f"{kind} exceeded the smoke-test deadline")


def main():
    with TemporaryDirectory() as directory:
        settings = Settings(database_url=f"sqlite:///{Path(directory).as_posix()}/smoke.db")
        with TestClient(create_app(settings)) as client:
            ready = client.get(API + "/ready").json()
            assert ready["status"] == "ready" and ready["ai_enabled"] is False
            draft = client.post(API + "/scenarios", json=default_plan().model_dump(mode="json"))
            draft.raise_for_status()
            scenario_url = f"{API}/scenarios/{draft.json()['scenario_id']}"
            confirmed = client.post(
                scenario_url + "/confirm", json={"plan_hash": draft.json()["plan_hash"]}
            )
            confirmed.raise_for_status()
            baseline, alternative = (
                completed_run(client, scenario_url, kind) for kind in ("baseline", "optimized")
            )
            pair = {
                "baseline_run_id": baseline["run_id"],
                "alternative_run_id": alternative["run_id"],
            }
            comparison = client.post(API + "/comparisons", json=pair)
            comparison.raise_for_status()
            added = comparison.json()["deltas"]["covered_visits"]
            assert added == 533
        with TestClient(create_app(settings)) as restarted:
            url = f"{API}/runs/{alternative['run_id']}/export"
            document = restarted.get(url).json()
            assert (
                document["result"]["audit"]["passed"]
                and document["plan_hash"] == draft.json()["plan_hash"]
            )
            cells = csv.DictReader(io.StringIO(restarted.get(url + "?format=csv").text))
            assert any(
                row["field"] == "dataset_sha256" and row["value"] == document["dataset_sha256"]
                for row in cells
            )
        print(
            f"Offline smoke passed. Two audited runs, {added} added covered visits/week, JSON and CSV restored after restart."
        )


if __name__ == "__main__":
    main()
