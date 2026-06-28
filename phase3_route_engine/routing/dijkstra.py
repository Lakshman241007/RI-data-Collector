"""
routing.dijkstra
-----------------
Dijkstra's algorithm — shortest weighted (``length_m``) path between two
nodes, using a binary heap (``heapq``) priority queue.
"""

from __future__ import annotations

import heapq
import itertools
import logging
import math

from routing.models import Graph, PathResult

logger = logging.getLogger(__name__)


def dijkstra_shortest_path(graph: Graph, start_id: str, end_id: str) -> PathResult:
    """Find the minimum-``length_m`` path between ``start_id`` and ``end_id``."""
    if not graph.has_node(start_id) or not graph.has_node(end_id):
        return PathResult(found=False)

    if start_id == end_id:
        return PathResult(found=True, node_ids=[start_id], edge_ids=[], distance_m=0.0)

    # Priority queue entries: (distance, tie_breaker, node_id)
    # The tie_breaker (a monotonically increasing counter) keeps heap
    # comparisons well-defined without ever comparing node ids directly.
    counter = itertools.count()
    queue: list[tuple[float, int, str]] = [(0.0, next(counter), start_id)]

    best_distance: dict[str, float] = {start_id: 0.0}
    parent: dict[str, tuple[str, str]] = {}
    visited: set[str] = set()
    nodes_expanded = 0

    while queue:
        dist, _, current = heapq.heappop(queue)

        if current in visited:
            continue
        visited.add(current)
        nodes_expanded += 1

        if current == end_id:
            break

        for neighbor_id, edge_id in graph.neighbors(current):
            if neighbor_id in visited:
                continue
            new_dist = dist + graph.edge_length(edge_id)
            if new_dist < best_distance.get(neighbor_id, math.inf):
                best_distance[neighbor_id] = new_dist
                parent[neighbor_id] = (current, edge_id)
                heapq.heappush(queue, (new_dist, next(counter), neighbor_id))

    if end_id not in best_distance:
        return PathResult(found=False, nodes_expanded=nodes_expanded)

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

    return PathResult(
        found=True,
        node_ids=node_path,
        edge_ids=edge_path,
        distance_m=best_distance[end_id],
        nodes_expanded=nodes_expanded,
    )
