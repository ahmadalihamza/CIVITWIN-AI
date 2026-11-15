from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints
from pydantic_core import InitErrorDetails, PydanticCustomError

MAX_NODES = 500
MAX_COMMUNITIES = 200
MAX_SITES = 100
MAX_EDGES = 5_000
MAX_VISITS = 1_000_000
MAX_EDGE_MINUTES = 1_440
MAX_COST_PKR = 100_000_000

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
WeeklyVisits = Annotated[int, Field(ge=0, le=MAX_VISITS)]
SchematicPosition = Annotated[int, Field(ge=0, le=10_000)]
SourceUrl = Annotated[str, StringConstraints(pattern=r"^https?://[^\s]+$", max_length=2_048)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Node(Contract):
    id: Identifier
    display_x: SchematicPosition
    display_y: SchematicPosition
    label: Label


class Edge(Contract):
    from_node: Identifier
    to_node: Identifier
    minutes: Annotated[int, Field(gt=0, le=MAX_EDGE_MINUTES)]
    direction: Literal["forward", "bidirectional"]


class Community(Contract):
    id: Identifier
    label: Label
    demand_visits_per_week: WeeklyVisits
    population: Annotated[int, Field(ge=0, le=100_000_000)] | None = None
    zone_class: Label
    node_id: Identifier


class Site(Contract):
    id: Identifier
    label: Label
    type: Literal["existing", "candidate"]
    node_id: Identifier
    capacity_per_week: WeeklyVisits
    fixed_cost_pkr: Annotated[int, Field(ge=0, le=MAX_COST_PKR)]
    eligible: bool


class Provenance(Contract):
    entity: Label
    field: Label
    source: Description
    method: Literal["synthetic", "observed", "estimated"]
    timestamp: AwareDatetime
    caveat: Description


class Dataset(Contract):
    schema_version: Literal[1]
    id: Identifier
    version: Identifier
    district_label: Label
    is_synthetic: bool
    source_url: SourceUrl | None
    source_date: date
    license: Label
    sha256: Digest
    assumptions: Annotated[tuple[Description, ...], Field(min_length=1, max_length=30)]
    model_scope: Description
    nodes: Annotated[tuple[Node, ...], Field(min_length=1, max_length=MAX_NODES)]
    edges: Annotated[tuple[Edge, ...], Field(max_length=MAX_EDGES)]
    communities: Annotated[tuple[Community, ...], Field(min_length=1, max_length=MAX_COMMUNITIES)]
    sites: Annotated[tuple[Site, ...], Field(min_length=1, max_length=MAX_SITES)]
    provenance: Annotated[tuple[Provenance, ...], Field(min_length=1, max_length=100)]

    @property
    def eligible_candidate_count(self) -> int:
        return sum(site.type == "candidate" and site.eligible for site in self.sites)


def integrity_errors(dataset: Dataset) -> list[InitErrorDetails]:
    errors: list[InitErrorDetails] = []

    def add(code: str, message: str, field: tuple[str | int, ...], value: object) -> None:
        errors.append(
            InitErrorDetails(type=PydanticCustomError(code, message), loc=field, input=value)
        )

    entity_tables: tuple[tuple[str, tuple[Node | Community | Site, ...]], ...] = (
        ("nodes", dataset.nodes),
        ("communities", dataset.communities),
        ("sites", dataset.sites),
    )
    for collection, entities in entity_tables:
        ids: set[str] = set()
        for row, entity in enumerate(entities):
            if entity.id in ids:
                add("duplicate_id", "ID occurs more than once.", (collection, row, "id"), entity.id)
            ids.add(entity.id)

    node_ids = {node.id for node in dataset.nodes}
    node_users: tuple[tuple[str, tuple[Community | Site, ...]], ...] = (
        ("communities", dataset.communities),
        ("sites", dataset.sites),
    )
    for collection, users in node_users:
        for row, user in enumerate(users):
            if user.node_id not in node_ids:
                add(
                    "unknown_node",
                    "Node ID is missing from the graph.",
                    (collection, row, "node_id"),
                    user.node_id,
                )

    arcs: set[tuple[str, str]] = set()
    for row, edge in enumerate(dataset.edges):
        for field in ("from_node", "to_node"):
            if (node := getattr(edge, field)) not in node_ids:
                add(
                    "unknown_node",
                    "Node ID is missing from the graph.",
                    ("edges", row, field),
                    node,
                )
        if edge.from_node == edge.to_node:
            add("self_edge", "Edge endpoints must differ.", ("edges", row, "to_node"), edge.to_node)
            continue
        pair = (edge.from_node, edge.to_node)
        edge_arcs = {pair, pair[::-1]} if edge.direction == "bidirectional" else {pair}
        if not arcs.isdisjoint(edge_arcs):
            add("duplicate_edge", "Travel direction is already defined.", ("edges", row), pair)
        arcs.update(edge_arcs)
    return errors
