import csv
import io
import re
from typing import Any

from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError

from app.domain.dataset import canonical_json, decode_json, load_dataset
from app.schemas.dataset import MAX_COMMUNITIES, MAX_EDGES, MAX_NODES, MAX_SITES, Dataset

TABLE_FIELDS = {
    "nodes": {"id", "display_x", "display_y", "label"},
    "edges": {"from_node", "to_node", "minutes", "direction"},
    "communities": {"id", "label", "demand_visits_per_week", "zone_class", "node_id"},
    "sites": {"id", "label", "type", "node_id", "capacity_per_week", "fixed_cost_pkr", "eligible"},
}
TABLE_LIMITS = {
    "nodes": MAX_NODES,
    "edges": MAX_EDGES,
    "communities": MAX_COMMUNITIES,
    "sites": MAX_SITES,
}
INTEGER_FIELDS = {
    "display_x",
    "display_y",
    "minutes",
    "demand_visits_per_week",
    "population",
    "capacity_per_week",
    "fixed_cost_pkr",
}
CSV_INTEGERS = re.compile(r"(?:0|[1-9][0-9]{0,8})\Z", flags=re.ASCII)


def _issue(message: str, loc: tuple[str | int, ...]) -> InitErrorDetails:
    return InitErrorDetails(type=PydanticCustomError("csv_invalid", message), loc=loc, input=None)


def _cell(field: str, value: str) -> str | int | bool | None:
    if field == "population" and not value:
        return None
    if field in INTEGER_FIELDS:
        if not CSV_INTEGERS.fullmatch(value):
            raise ValueError("Expected an unsigned decimal integer with at most nine digits.")
        return int(value)
    if field == "eligible":
        if value not in {"true", "false"}:
            raise ValueError("Expected true or false.")
        return value == "true"
    return value


def _read_table(table: str, value: Any, errors: list[InitErrorDetails]) -> list[dict[str, Any]]:
    if not isinstance(value, str):
        errors.append(_issue("Expected UTF-8 CSV text.", (table,)))
        return []
    reader = csv.reader(io.StringIO(value, newline=""), strict=True)
    rows = []
    try:
        headers = next(reader, [])
        required = TABLE_FIELDS[table]
        allowed = required | {"population"} if table == "communities" else required
        columns = set(headers)
        if columns - allowed or required - columns or len(columns) != len(headers):
            errors.append(
                _issue(
                    "CSV headers must contain each required field once and no unknown fields.",
                    (table, "header"),
                )
            )
            return []
        for index, values in enumerate(reader):
            if index >= TABLE_LIMITS[table]:
                errors.append(_issue(f"Table exceeds {TABLE_LIMITS[table]} rows.", (table, index)))
                break
            if len(values) != len(headers):
                errors.append(_issue("CSV row length must match the header.", (table, index)))
                continue
            row = {}
            for field, raw in zip(headers, values, strict=True):
                try:
                    row[field] = _cell(field, raw)
                except ValueError as exc:
                    errors.append(_issue(str(exc), (table, index, field)))
            rows.append(row)
    except csv.Error:
        errors.append(_issue("Malformed CSV record.", (table, reader.line_num)))
    return rows


def load_import(raw: bytes | str) -> Dataset:
    """Read a canonical dataset JSON document or a JSON manifest with four CSV tables."""
    payload = decode_json(raw)
    if not isinstance(payload, dict) or not {"manifest", "tables"}.intersection(payload):
        return load_dataset(raw)
    manifest = payload.get("manifest")
    tables = payload.get("tables")
    if (
        set(payload) != {"manifest", "tables"}
        or not isinstance(manifest, dict)
        or TABLE_FIELDS.keys() & manifest.keys()
        or not isinstance(tables, dict)
        or set(tables) != set(TABLE_FIELDS)
    ):
        raise ValueError(
            "Expected a manifest and exactly four CSV tables: nodes, edges, communities and sites."
        )
    errors: list[InitErrorDetails] = []
    records = {table: _read_table(table, tables[table], errors) for table in TABLE_FIELDS}
    if errors:
        raise ValidationError.from_exception_data("CSV dataset", errors)
    return load_dataset(canonical_json({**manifest, **records}))
