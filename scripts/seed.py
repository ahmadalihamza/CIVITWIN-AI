"""Materialize the versioned synthetic inputs and their JSON schemas."""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.domain.dataset import create_dataset, dataset_payload  # noqa: E402
from app.schemas.dataset import Dataset  # noqa: E402
from app.schemas.plan import PlanSpec  # noqa: E402

SEED = 2026
SOURCE_DATE = "2026-11-13"
ZONE_CLASSES = ("Valley", "Foothill", "Ridge")


def manifest(identifier: str, district: str, assumptions: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": identifier,
        "version": "1.0.0",
        "district_label": district,
        "is_synthetic": True,
        "source_url": None,
        "source_date": SOURCE_DATE,
        "license": "CC0-1.0",
        "assumptions": assumptions,
        "model_scope": "Scheduled non-emergency outpatient access over one modeled week.",
        "provenance": [
            {
                "entity": entity,
                "field": field,
                "source": "CIVITWIN synthetic generator (seed 2026)",
                "method": "synthetic",
                "timestamp": f"{SOURCE_DATE}T00:00:00Z",
                "caveat": caveat,
            }
            for entity, field, caveat in (
                (
                    "communities",
                    "demand_visits_per_week",
                    "Fictional requested visits, not people.",
                ),
                ("sites", "capacity_per_week", "Fictional aggregate visits per modeled week."),
                (
                    "sites",
                    "fixed_cost_pkr",
                    "Illustrative weekly-equivalent planning costs in PKR.",
                ),
                ("edges", "minutes", "Illustrative graph costs, not observed travel times."),
                (
                    "nodes",
                    "display_x/display_y",
                    "Schematic positions without geographic coordinates.",
                ),
            )
        ],
    }


def node_id(index: int) -> str:
    return f"D{index + 1:02}"


def community(index: int, demand: int, zone_class: str) -> dict[str, Any]:
    return {
        "id": f"C{index + 1:02}",
        "label": f"Community {index + 1:02}",
        "demand_visits_per_week": demand,
        "zone_class": zone_class,
        "node_id": node_id(index),
    }


def site(kind: str, number: int, node: int, capacity: int, cost: int) -> dict[str, Any]:
    prefix, label = ("E", "Existing site") if kind == "existing" else ("N", "Candidate zone")
    return {
        "id": f"{prefix}{number:02}",
        "label": f"{label} {number:02}",
        "type": kind,
        "node_id": node_id(node),
        "capacity_per_week": capacity,
        "fixed_cost_pkr": cost,
        "eligible": True,
    }


def build_demo() -> Dataset:
    randomizer = random.Random(SEED)
    data = manifest(
        "demo-bajaur-v1",
        "Bajaur — synthetic planning sandbox",
        [
            "Synthetic demonstration. All demand, sites, capacities, travel and costs are fictional.",
            "Demand and capacity are visits per modeled week. Demand is not a population estimate.",
            "The schematic network is connected. Edge costs are integer minutes and bidirectional.",
            "Existing sites are already open. Candidate costs are weekly-equivalent PKR.",
        ],
    )
    nodes = []
    edges = []
    communities = []
    for index in range(24):
        row, column = divmod(index, 6)
        nodes.append(
            {
                "id": node_id(index),
                "display_x": 60 + column * 98 + randomizer.randint(-16, 16),
                "display_y": 45 + row * 88 + randomizer.randint(-14, 14),
                "label": f"Schematic node {index + 1:02}",
            }
        )
        communities.append(community(index, randomizer.randint(40, 160), ZONE_CLASSES[column // 2]))
        neighbors = []
        if column < 5:
            neighbors.append(index + 1)
        if row < 3:
            neighbors.append(index + 6)
        for neighbor in neighbors:
            edges.append(
                {
                    "from_node": node_id(index),
                    "to_node": node_id(neighbor),
                    "minutes": randomizer.randint(9, 21) + (5 if column >= 4 else 0),
                    "direction": "bidirectional",
                }
            )
    sites = [
        site("existing", number, node, randomizer.randint(150, 300), 0)
        for number, node in enumerate((0, 7, 12, 14, 20), 1)
    ]
    sites.extend(
        site(
            "candidate",
            number,
            node,
            randomizer.randint(180, 300),
            randomizer.randrange(90_000, 160_001, 1_000),
        )
        for number, node in enumerate((3, 5, 9, 11, 16, 17, 22, 23), 1)
    )
    return create_dataset(
        {**data, "nodes": nodes, "edges": edges, "communities": communities, "sites": sites}
    )


def build_disconnected() -> Dataset:
    data = manifest(
        "fixture-disconnected-v1",
        "Disconnected synthetic test fixture",
        [
            "The second community cannot reach the only existing service site.",
        ],
    )
    return create_dataset(
        {
            **data,
            "nodes": [
                {
                    "id": node_id(index),
                    "display_x": index * 100,
                    "display_y": 10,
                    "label": f"Node {index + 1}",
                }
                for index in range(2)
            ],
            "edges": [],
            "communities": [community(0, 60, "Valley"), community(1, 40, "Ridge")],
            "sites": [site("existing", 1, 0, 100, 0)],
        }
    )


def build_golden() -> Dataset:
    data = manifest(
        "fixture-golden-v1",
        "SRS golden fixture",
        [
            "Synthetic test fixture with the exact input values from SRS section 11.1.",
        ],
    )
    return create_dataset(
        {
            **data,
            "nodes": [
                {"id": name, "display_x": index * 10, "display_y": 10, "label": f"Node {name}"}
                for index, name in enumerate(("A", "B", "E", "N"))
            ],
            "edges": [
                {"from_node": start, "to_node": end, "minutes": minutes, "direction": "forward"}
                for start, end, minutes in (
                    ("A", "E", 10),
                    ("B", "E", 50),
                    ("A", "N", 40),
                    ("B", "N", 10),
                )
            ],
            "communities": [
                {**community(index, demand, "Fixture"), "id": name, "label": name, "node_id": name}
                for index, (name, demand) in enumerate((("A", 60), ("B", 40)))
            ],
            "sites": [
                {**site("existing", 1, 0, 60, 0), "id": "E", "label": "E", "node_id": "E"},
                {**site("candidate", 1, 0, 40, 100), "id": "N", "label": "N", "node_id": "N"},
            ],
        }
    )


def build_saturated() -> Dataset:
    golden = dataset_payload(build_golden())
    del golden["sha256"]
    capacities = {"E": 45, "N": 20}
    return create_dataset(
        {
            **golden,
            "id": "fixture-saturated-v1",
            "district_label": "Capacity saturation synthetic test fixture",
            "assumptions": ["Total modeled demand is 100 visits and total capacity is 65 visits."],
            "sites": [
                {**row, "capacity_per_week": capacities[row["id"]]} for row in golden["sites"]
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if tracked inputs differ from the generator."
    )
    args = parser.parse_args()
    artifacts = {
        ROOT / "data/demo/bajaur-v1.json": dataset_payload(build_demo()),
        ROOT / "services/api/tests/fixtures/disconnected.json": dataset_payload(
            build_disconnected()
        ),
        ROOT / "services/api/tests/fixtures/golden.json": dataset_payload(build_golden()),
        ROOT / "services/api/tests/fixtures/saturated.json": dataset_payload(build_saturated()),
        ROOT / "data/schemas/dataset.schema.json": Dataset.model_json_schema(),
        ROOT / "data/schemas/plan.schema.json": PlanSpec.model_json_schema(),
    }
    mismatches = []
    for path, payload in artifacts.items():
        expected = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                mismatches.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8", newline="\n")
    if mismatches:
        parser.exit(1, f"Generated artifacts differ: {', '.join(mismatches)}\n")
    print(
        "Verified synthetic inputs and schemas."
        if args.check
        else "Generated synthetic inputs and schemas."
    )


if __name__ == "__main__":
    main()
