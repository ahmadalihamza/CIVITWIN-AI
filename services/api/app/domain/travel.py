from collections import OrderedDict
from collections.abc import Mapping
from threading import Lock
from types import MappingProxyType

import networkx as nx

from app.schemas.dataset import Dataset

TravelMatrix = Mapping[tuple[str, str], int]
_CACHE_LIMIT = 16
_cache: OrderedDict[str, TravelMatrix] = OrderedDict()
_cache_lock = Lock()


def travel_matrix(dataset: Dataset) -> TravelMatrix:
    """Shortest integer-minute paths from each community to each reachable site."""
    with _cache_lock:
        if (cached := _cache.get(dataset.sha256)) is not None:
            _cache.move_to_end(dataset.sha256)
            return cached

    graph = nx.DiGraph()
    graph.add_nodes_from(node.id for node in dataset.nodes)
    for edge in dataset.edges:
        graph.add_edge(edge.from_node, edge.to_node, minutes=edge.minutes)
        if edge.direction == "bidirectional":
            graph.add_edge(edge.to_node, edge.from_node, minutes=edge.minutes)

    # Several communities may share a source node. One traversal per source is sufficient.
    by_node: dict[str, dict[str, int]] = {}
    matrix = {}
    sites = sorted(dataset.sites, key=lambda site: site.id)
    for community in sorted(dataset.communities, key=lambda community: community.id):
        if community.node_id not in by_node:
            by_node[community.node_id] = nx.single_source_dijkstra_path_length(
                graph, community.node_id, weight="minutes"
            )
        distances = by_node[community.node_id]
        for site in sites:
            if site.node_id in distances:
                matrix[community.id, site.id] = distances[site.node_id]

    result = MappingProxyType(matrix)
    with _cache_lock:
        _cache[dataset.sha256] = result
        _cache.move_to_end(dataset.sha256)
        if len(_cache) > _CACHE_LIMIT:
            _cache.popitem(last=False)
    return result


def scaled_travel(matrix: TravelMatrix, multiplier_pct: int) -> TravelMatrix:
    """Round each perturbed shortest-path cost once, half up to whole minutes."""
    if multiplier_pct == 100:
        return matrix
    return MappingProxyType(
        {pair: (minutes * multiplier_pct + 50) // 100 for pair, minutes in matrix.items()}
    )
