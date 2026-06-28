"""
routing.bfs
-----------
Breadth-First Search utilities:

* ``bfs_connectivity``        — the set of nodes reachable from a start node.
* ``bfs_connected_components`` — partition the whole graph into components.
* ``bfs_shortest_path``       — unweighted (hop-count) shortest path between
                                 two nodes.
"""

from __future__ import annotations

import logging
from collections import deque

from routing.models import Graph, PathResult

logger = logging.getLogger(__name__)


def bfs_connectivity(graph: Graph, start_id: str) -> set[str]:
    """Return the set of node ids reachable from ``start_id`` (inclusive)."""
    if not graph.has_node(start_id):
        return set()

    visited: set[str] = {start_id}
    queue: deque[str] = deque([start_id])

    while queue:
        current = queue.popleft()
        for neighbor_id, _edge_id in graph.neighbors(current):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                queue.append(neighbor_id)

    return visited


def bfs_connected_components(graph: Graph) -> list[set[str]]:
    """Partition every node in the graph into its connected component."""
    seen: set[str] = set()
    components: list[set[str]] = []

    for node_id in graph.nodes:
        if node_id in seen:
            continue
        component = bfs_connectivity(graph, node_id)
        seen.update(component)
        components.append(component)

    logger.info("BFS found %d connected components", len(components))
    return components


def bfs_shortest_path(graph: Graph, start_id: str, end_id: str) -> PathResult:
    """Unweighted shortest path (fewest hops) between ``start_id`` and ``end_id``.

    Distance on the returned ``PathResult`` is still expressed in metres —
    it is the sum of ``length_m`` over the edges of the hop-minimal path
    found, not the hop count itself.
    """
    if not graph.has_node(start_id) or not graph.has_node(end_id):
        return PathResult(found=False)

    if start_id == end_id:
        return PathResult(found=True, node_ids=[start_id], edge_ids=[], distance_m=0.0)

    visited: set[str] = {start_id}
    queue: deque[str] = deque([start_id])
    parent: dict[str, tuple[str, str]] = {}  # node -> (parent_node, edge_id)
    nodes_expanded = 0

    while queue:
        current = queue.popleft()
        nodes_expanded += 1

        if current == end_id:
            break

        for neighbor_id, edge_id in graph.neighbors(current):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                parent[neighbor_id] = (current, edge_id)
                queue.append(neighbor_id)

    if end_id not in visited:
        return PathResult(found=False, nodes_expanded=nodes_expanded)

    # Reconstruct the path by walking parent pointers backwards.
    node_path: list[str] = [end_id]
    edge_path: list[str] = []
    cursor = end_id
    while cursor != start_id:
        prev_node, edge_id = parent[cursor]
        edge_path.append(edge_id)
        node_path.append(prev_node)
        cursor = prev_node

    node_path.reverse()
    edge_path.reverse()
    distance = sum(graph.edge_length(edge_id) for edge_id in edge_path)

    return PathResult(
        found=True,
        node_ids=node_path,
        edge_ids=edge_path,
        distance_m=distance,
        nodes_expanded=nodes_expanded,
    )
