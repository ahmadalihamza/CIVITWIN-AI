import csv
import io
import json
from collections.abc import Iterable
from typing import Any

SYNTHETIC_WARNING = (
    "SYNTHETIC DEMONSTRATION. Fictional weekly service planning assumptions for Bajaur."
)


def export_document(
    result: dict[str, Any], plan: dict[str, Any], dataset: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "data_warning": (
            SYNTHETIC_WARNING if dataset["is_synthetic"] else "Aggregate planning assumptions."
        ),
        "time_horizon": "one modeled week",
        "units": {"demand": "visits/week", "travel": "minutes", "cost": "PKR/week"},
        "model_version": result["model_version"],
        "dataset_sha256": result["dataset_sha256"],
        "plan_hash": result["plan_hash"],
        "dataset": dataset,
        "plan": plan,
        "result": result,
    }


def safe_csv_cell(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    text = (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    )
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _csv_records(document: dict[str, Any]) -> Iterable[tuple[str, str, str, str, Any]]:
    for key, value in document.items():
        if key not in {"dataset", "plan", "result"}:
            yield "metadata", "", "", key, value
    dataset = document["dataset"]
    for key, value in dataset.items():
        yield "dataset", dataset["id"], "", key, value
    for key, value in document["plan"].items():
        yield "plan", "", "", key, value
    result = document["result"]
    for key, value in result.items():
        if key not in {"metrics", "assignments", "unmet_by_community"}:
            yield "result", result["run_id"], "", key, value
    for key, value in result["metrics"].items():
        if key == "clusters":
            for cluster in value:
                for field, metric in cluster.items():
                    if field != "community_id":
                        yield "cluster", cluster["community_id"], "", field, metric
        else:
            yield "metric", "", "", key, value
    for row in result["assignments"]:
        yield "assignment", row["community_id"], row["site_id"], "visits", row["visits"]
    for row in result["unmet_by_community"]:
        yield "unmet", row["community_id"], "", "visits", row["visits"]


def export_csv(document: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("section", "id", "related_id", "field", "value"))
    for row in _csv_records(document):
        writer.writerow([safe_csv_cell(value) for value in row])
    return output.getvalue()
