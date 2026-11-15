import csv
import io
import json
from pathlib import Path

import pytest
from app.domain.dataset import canonical_dataset_hash, create_dataset, dataset_payload, load_dataset
from app.domain.dataset_import import TABLE_FIELDS, load_import
from app.schemas.plan import PlanSpec, default_plan, scaled_visits
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[4]
DEMO = ROOT / "data/demo/bajaur-v1.json"
DISCONNECTED = ROOT / "services/api/tests/fixtures/disconnected.json"


def test_seed_schema_bounds_and_connectivity():
    dataset = load_dataset(DEMO.read_bytes())
    assert dataset.is_synthetic and dataset.source_url is None
    assert dataset.id == "demo-bajaur-v1"
    assert len(dataset.nodes) == len(dataset.communities) == 24
    assert len(dataset.edges) == 38
    assert [row.id for row in dataset.communities] == [f"C{i:02}" for i in range(1, 25)]
    assert all(
        40 <= row.demand_visits_per_week <= 160 and row.population is None
        for row in dataset.communities
    )
    existing = [row for row in dataset.sites if row.type == "existing"]
    candidates = [row for row in dataset.sites if row.type == "candidate"]
    assert len(existing) == 5 and all(150 <= row.capacity_per_week <= 300 for row in existing)
    assert dataset.eligible_candidate_count == len(candidates) == 8
    assert all(
        180 <= row.capacity_per_week <= 300 and 90_000 <= row.fixed_cost_pkr <= 160_000
        for row in candidates
    )
    reachable = {dataset.nodes[0].id}
    for _ in dataset.nodes:
        for edge in dataset.edges:
            assert edge.direction == "bidirectional"
            if reachable.intersection((edge.from_node, edge.to_node)):
                reachable.update((edge.from_node, edge.to_node))
    assert reachable == {node.id for node in dataset.nodes}
    assert default_plan().validate_for(dataset).plan_hash
    assert not load_dataset(DISCONNECTED.read_bytes()).edges


def test_dataset_canonical_order_and_mutation():
    original = load_dataset(DEMO.read_bytes())
    payload = dataset_payload(original)
    for collection in ("nodes", "communities", "sites", "edges", "provenance"):
        payload[collection].reverse()
    edge = payload["edges"][0]
    edge["from_node"], edge["to_node"] = edge["to_node"], edge["from_node"]
    reloaded = load_dataset(json.dumps(payload))
    assert reloaded == original
    assert canonical_dataset_hash(reloaded) == original.sha256
    with pytest.raises(ValidationError, match="frozen"):
        reloaded.nodes[0].label = "Changed"
    payload["nodes"][0]["label"] = "Changed"
    with pytest.raises(ValueError, match="SHA-256"):
        load_dataset(json.dumps(payload))


def test_bad_import_has_row_and_field_errors():
    payload = json.loads(DEMO.read_bytes())
    payload["nodes"][1]["id"] = payload["nodes"][0]["id"]
    payload["communities"][0]["node_id"] = "unknown"
    edge = payload["edges"][0]
    payload["edges"].append({**edge, "from_node": edge["to_node"], "to_node": edge["from_node"]})
    with pytest.raises(ValidationError) as raised:
        load_dataset(json.dumps(payload))
    issues = {(row["type"], row["loc"]) for row in raised.value.errors()}
    assert ("duplicate_id", ("nodes", 1, "id")) in issues
    assert ("unknown_node", ("communities", 0, "node_id")) in issues
    assert ("duplicate_edge", ("edges", 38)) in issues


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("budget_pkr", True),
        ("max_new_units", "2"),
        ("threshold_minutes", 0),
        ("demand_multiplier_pct", 301),
        ("equity_min_pct", 101),
        ("seed", -1),
        ("policy", "anything"),
        ("unexpected", 1),
    ],
)
def test_plan_contract_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        PlanSpec.model_validate({**default_plan().model_dump(), field: value})


def test_dataset_specific_plan_constraints_and_rounding():
    dataset = load_dataset(DEMO.read_bytes())
    plan = default_plan().model_dump()
    with pytest.raises(ValueError, match="eligible"):
        PlanSpec.model_validate({**plan, "max_new_units": 9}).validate_for(dataset)
    with pytest.raises(ValueError, match="version"):
        default_plan("unregistered").validate_for(dataset)
    payload = dataset_payload(dataset)
    del payload["sha256"]
    for row in payload["communities"]:
        row["demand_visits_per_week"] = 1
    with pytest.raises(ValueError, match="positive total weekly demand"):
        PlanSpec.model_validate({**plan, "demand_multiplier_pct": 1}).validate_for(
            create_dataset(payload)
        )
    assert scaled_visits(1, 50) == 1
    assert scaled_visits(1, 49) == 0
    assert (
        PlanSpec.model_validate({**plan, "equity_min_pct": 10}).plan_hash
        != default_plan().plan_hash
    )


def test_json_parser_rejects_duplicate_keys_and_oversized_payloads():
    with pytest.raises(ValueError, match="Duplicate JSON field"):
        load_dataset('{"id":"a","id":"b"}')
    with pytest.raises(ValueError, match="2 MB"):
        load_dataset(b" " * 2_000_001)


def test_csv_bundle_matches_json_and_rejects_invalid_rows():
    original = load_dataset(DEMO.read_bytes())
    manifest = dataset_payload(original)
    tables = {}
    for table, fields in TABLE_FIELDS.items():
        output = io.StringIO()
        writer = csv.DictWriter(output, sorted(fields), extrasaction="ignore")
        writer.writeheader()
        for row in manifest.pop(table):
            writer.writerow(
                {
                    key: str(value).lower() if isinstance(value, bool) else value
                    for key, value in row.items()
                }
            )
        tables[table] = output.getvalue()
    assert load_import(json.dumps({"manifest": manifest, "tables": tables})) == original
    tables["edges"] = "direction,from_node,minutes,to_node\nbidirectional,D01,-3,D02\n"
    with pytest.raises(ValidationError) as raised:
        load_import(json.dumps({"manifest": manifest, "tables": tables}))
    assert raised.value.errors()[0]["loc"] == ("edges", 0, "minutes")
    tables["edges"] = "direction,from_node,minutes,to_node,unexpected\n"
    with pytest.raises(ValidationError) as raised:
        load_import(json.dumps({"manifest": manifest, "tables": tables}))
    assert raised.value.errors()[0]["loc"] == ("edges", "header")
