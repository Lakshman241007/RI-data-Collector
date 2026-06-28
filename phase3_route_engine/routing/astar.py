"""
routing.astar
-------------
A* search — shortest weighted (``length_m``) path between two nodes,
guided by a geographic (haversine) heuristic so that fewer nodes need to
be expanded than plain Dijkstra.
"""

from __future__ import annotations

import heapq
import itertools
import logging
import math
from typing import Callable

from routing.heuristics import make_geo_heuristic
from routing.models import Graph, PathResult

logger = logging.getLogger(__name__)


def astar_shortest_path(
    graph: Graph,
    start_id: str,
    end_id: str,
    heuristic: Callable[[str], float] | None = None,
) -> PathResult:
    """Find the minimum-``length_m`` path between ``start_id`` and ``end_id``.

    ``heuristic(node_id) -> metres`` estimates the remaining distance from
    ``node_id`` to ``end_id``. If omitted, the haversine distance between
    each node's coordinates and the target's is used (built via
    ``routing.heuristics.make_geo_heuristic``).
    """
    if not graph.has_node(start_id) or not graph.has_node(end_id):
        return PathResult(found=False)

    if start_id == end_id:
        return PathResult(found=True, node_ids=[start_id], edge_ids=[], distance_m=0.0)

    if heuristic is None:
        heuristic = make_geo_heuristic(graph, end_id)

    counter = itertools.count()
    # Priority queue entries: (f_score, tie_breaker, node_id)
    queue: list[tuple[float, int, str]] = [(heuristic(start_id), next(counter), start_id)]

    g_score: dict[str, float] = {start_id: 0.0}
    parent: dict[str, tuple[str, str]] = {}
    visited: set[str] = set()
    nodes_expanded = 0

    while queue:
        _f, _, current = heapq.heappop(queue)

        if current in visited:
            continue
        visited.add(current)
        nodes_expanded += 1

        if current == end_id:
            break

        for neighbor_id, edge_id in graph.neighbors(current):
            if neighbor_id in visited:
                continue
            tentative_g = g_score[current] + graph.edge_length(edge_id)
            if tentative_g < g_score.get(neighbor_id, math.inf):
                g_score[neighbor_id] = tentative_g
                parent[neighbor_id] = (current, edge_id)
                f_score = tentative_g + heuristic(neighbor_id)
                heapq.heappush(queue, (f_score, next(counter), neighbor_id))

    if end_id not in g_score:
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
        distance_m=g_score[end_id],
        nodes_expanded=nodes_expanded,
    )
