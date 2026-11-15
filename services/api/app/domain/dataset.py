import json
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from app.schemas.dataset import Dataset, integrity_errors

MAX_UPLOAD_BYTES = 2_000_000


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_json(raw: str | bytes) -> Any:
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(encoded) > MAX_UPLOAD_BYTES:
        raise ValueError("Dataset bundle exceeds 2 MB.")
    try:
        return json.loads(encoded.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the allowed depth.") from exc


def dataset_payload(dataset: Dataset) -> dict[str, Any]:
    payload = dataset.model_dump(mode="json")
    for collection in ("communities", "nodes", "sites"):
        payload[collection].sort(key=lambda row: row["id"])
    for edge in payload["edges"]:
        if edge["direction"] == "bidirectional" and edge["from_node"] > edge["to_node"]:
            edge["from_node"], edge["to_node"] = edge["to_node"], edge["from_node"]
    payload["edges"].sort(key=lambda row: (row["from_node"], row["to_node"], row["direction"]))
    payload["provenance"].sort(key=canonical_json)
    return payload


def canonical_dataset_hash(dataset: Dataset) -> str:
    payload = dataset_payload(dataset)
    del payload["sha256"]
    return sha256(canonical_json(payload)).hexdigest()


def _validated(raw: bytes) -> Dataset:
    dataset = Dataset.model_validate_json(raw)
    if errors := integrity_errors(dataset):
        raise ValidationError.from_exception_data("Dataset", errors)
    return dataset


def create_dataset(payload: dict[str, Any]) -> Dataset:
    """Validate and hash data from a trusted version generator or adapter."""
    if "sha256" in payload:
        raise ValueError("Supply unsigned dataset content when creating a new hash.")
    dataset = _validated(canonical_json({**payload, "sha256": "0" * 64}))
    return Dataset.model_validate_json(
        canonical_json({**dataset_payload(dataset), "sha256": canonical_dataset_hash(dataset)})
    )


def load_dataset(raw: bytes | str) -> Dataset:
    """Validate a complete dataset version and verify its content digest."""
    dataset = _validated(canonical_json(decode_json(raw)))
    if dataset.sha256 != canonical_dataset_hash(dataset):
        raise ValueError("Dataset SHA-256 does not match canonical content.")
    return Dataset.model_validate_json(canonical_json(dataset_payload(dataset)))
