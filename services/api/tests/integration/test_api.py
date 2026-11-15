import csv
import io
from pathlib import Path
from time import monotonic, sleep

import pytest
from app.config import Settings
from app.domain.dataset import create_dataset, dataset_payload, load_dataset
from app.main import create_app
from app.schemas.plan import default_plan
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[4]
PREFIX = "/api/v1"


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as browser:
        yield browser


def publish_fixture(client, filename="golden"):
    raw = (ROOT / f"services/api/tests/fixtures/{filename}.json").read_bytes()
    response = client.post(
        PREFIX + "/datasets/import", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def scenario(client, dataset_id, **overrides):
    plan = {
        **default_plan(dataset_id).model_dump(mode="json"),
        "budget_pkr": 100,
        "max_new_units": 1,
        "threshold_minutes": 30,
        **overrides,
    }
    response = client.post(PREFIX + "/scenarios", json=plan)
    assert response.status_code == 201, response.text
    return response.json()


def confirm(client, draft):
    response = client.post(
        f"{PREFIX}/scenarios/{draft['scenario_id']}/confirm",
        json={"plan_hash": draft["plan_hash"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CONFIRMED"


def run(client, draft, kind, key):
    url = f"{PREFIX}/scenarios/{draft['scenario_id']}/runs"
    response = client.post(url, json={"kind": kind}, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    deadline = monotonic() + 15
    while monotonic() < deadline:
        response = client.get(f"{PREFIX}/runs/{run_id}")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        if snapshot["status"] not in ("QUEUED", "RUNNING", "AUDITING"):
            return snapshot
        sleep(0.025)
    pytest.fail("The test run did not reach a terminal state.")


def test_t06_invalid_dataset_import_is_atomic_with_row_errors(client):
    response = client.get(PREFIX + "/datasets")
    before = response.json()
    payload = dataset_payload(load_dataset((ROOT / "data/demo/bajaur-v1.json").read_bytes()))
    payload["communities"][1]["id"] = payload["communities"][0]["id"]
    invalid = client.post(PREFIX + "/datasets/import", json=payload)
    assert invalid.status_code == 422, invalid.text
    assert {
        "code": "duplicate_id",
        "field": ["communities", 1, "id"],
        "message": "ID occurs more than once.",
    } in invalid.json()["field_errors"]
    assert client.get(PREFIX + "/datasets").json() == before
    assert client.post(PREFIX + "/datasets/import", content="{}").status_code == 400
    large = client.post(
        PREFIX + "/datasets/import",
        content=b"x" * 2_000_001,
        headers={"Content-Type": "application/json"},
    )
    assert large.status_code == 422 and large.json()["code"] == "IMPORT_SIZE"


def test_t08_compatible_and_mismatched_comparisons(client):
    dataset_id = publish_fixture(client)
    draft = scenario(client, dataset_id)
    confirm(client, draft)
    base = run(client, draft, "baseline", "compare-baseline")
    alt = run(client, draft, "optimized", "compare-alt")
    assert base["status"] == alt["status"] == "COMPLETED", (base, alt)
    pair = {"baseline_run_id": base["run_id"], "alternative_run_id": alt["run_id"]}
    accepted = client.post(PREFIX + "/comparisons", json=pair)
    assert accepted.status_code == 200, accepted.text
    deltas = accepted.json()["deltas"]
    assert deltas["coverage_pp"] == 40
    assert deltas["additional_cost_per_added_covered_visit"] == 2.5
    different = scenario(client, dataset_id, budget_pkr=101)
    confirm(client, different)
    another = run(client, different, "optimized", "compare-different-plan")
    conflict = client.post(
        PREFIX + "/comparisons", json={**pair, "alternative_run_id": another["run_id"]}
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "INCOMPATIBLE_COMPARISON"


def test_t12_audited_export_json_csv_and_spreadsheet_safety(client):
    raw = (ROOT / "services/api/tests/fixtures/golden.json").read_bytes()
    payload = dataset_payload(load_dataset(raw))
    del payload["sha256"]
    payload["id"] = "golden-export"
    payload["district_label"] = "=1+1"
    dataset = create_dataset(payload)
    response = client.post(PREFIX + "/datasets/import", json=dataset_payload(dataset))
    assert response.status_code == 201, response.text
    draft = scenario(client, dataset.id)
    confirm(client, draft)
    snapshot = run(client, draft, "optimized", "export-alt")
    url = f"{PREFIX}/runs/{snapshot['run_id']}/export"
    json_response = client.get(url)
    assert json_response.status_code == 200, json_response.text
    report = json_response.json()
    assert report["dataset_sha256"] == dataset.sha256
    assert report["plan_hash"] == draft["plan_hash"]
    assert report["dataset"]["provenance"]
    assert report["result"]["audit"]["passed"]
    assert report["data_warning"].startswith("SYNTHETIC DEMONSTRATION")
    exported = client.get(url, params={"format": "csv"})
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert any(row["field"] == "district_label" and row["value"] == "'=1+1" for row in rows)
    assert any(row["field"] == "dataset_sha256" and row["value"] == dataset.sha256 for row in rows)
    assert any(row["section"] == "assignment" and row["id"] == "A" for row in rows)


def test_confirmation_idempotency_and_completed_snapshot_survive_restart(settings):
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        assert client.get(PREFIX + "/ready").status_code == 200
        dataset_id = publish_fixture(client)
        draft = scenario(client, dataset_id)
        scenario_url = f"{PREFIX}/scenarios/{draft['scenario_id']}"
        post = client.post(scenario_url + "/runs", json={"kind": "baseline"})
        assert post.status_code == 409
        bad = client.post(scenario_url + "/confirm", json={"plan_hash": "0" * 64})
        assert bad.status_code == 409 and bad.json()["code"] == "PLAN_HASH_MISMATCH"
        confirm(client, draft)
        snapshot = run(client, draft, "baseline", "persisted-key")
        assert snapshot["status"] == "COMPLETED", snapshot
        assert run(client, draft, "baseline", "persisted-key")["run_id"] == snapshot["run_id"]
        mismatch = client.post(
            scenario_url + "/runs",
            json={"kind": "optimized"},
            headers={"Idempotency-Key": "persisted-key"},
        )
        assert mismatch.status_code == 409
    with TestClient(create_app(settings)) as client:
        assert client.get(scenario_url).json()["status"] == "CONFIRMED"
        saved = client.get(f"{PREFIX}/runs/{snapshot['run_id']}").json()
        assert saved == snapshot
        assert client.get(PREFIX + "/runs").json()[0]["run_id"] == snapshot["run_id"]


def test_malformed_and_invalid_plan_have_safe_error_envelope(client):
    response = client.post(
        PREFIX + "/scenarios", content="{", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["request_id"] == response.headers["x-request-id"]
    invalid = client.post(PREFIX + "/scenarios", json={"budget_pkr": "sensitive-user-value"})
    assert invalid.status_code == 422
    assert invalid.json()["field_errors"]
    assert "sensitive-user-value" not in invalid.text
