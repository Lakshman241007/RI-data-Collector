"""
routing.route_builder
-----------------------
Dispatches a ``RouteRequest`` to the appropriate pathfinding algorithm,
times the computation, and builds an ordered ``RouteResult`` (station
list, distance, node/edge counts).
"""

from __future__ import annotations

import logging
import time

from routing.astar import astar_shortest_path
from routing.bfs import bfs_shortest_path
from routing.dfs import dfs_path
from routing.dijkstra import dijkstra_shortest_path
from routing.models import AlgorithmType, Graph, PathResult, RouteRequest, RouteResult

logger = logging.getLogger(__name__)

_ALGORITHM_DISPATCH = {
    AlgorithmType.BFS: bfs_shortest_path,
    AlgorithmType.DFS: dfs_path,
    AlgorithmType.DIJKSTRA: dijkstra_shortest_path,
    AlgorithmType.ASTAR: astar_shortest_path,
}


def build_route(graph: Graph, request: RouteRequest) -> RouteResult:
    """Run ``request.algorithm`` for ``request`` and build a ``RouteResult``."""
    algorithm_fn = _ALGORITHM_DISPATCH.get(request.algorithm)
    if algorithm_fn is None:
        return RouteResult(
            route_id=request.request_id,
            algorithm=request.algorithm,
            source_id=request.source_id,
            target_id=request.target_id,
            success=False,
            error=f"unknown_algorithm:{request.algorithm}",
        )

    if not graph.has_node(request.source_id) or not graph.has_node(request.target_id):
        missing = [
            node_id
            for node_id in (request.source_id, request.target_id)
            if not graph.has_node(node_id)
        ]
        return RouteResult(
            route_id=request.request_id,
            algorithm=request.algorithm,
            source_id=request.source_id,
            target_id=request.target_id,
            success=False,
            error=f"missing_node:{','.join(missing)}",
        )

    t_start = time.perf_counter()
    result: PathResult = algorithm_fn(graph, request.source_id, request.target_id)
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    if not result.found:
        return RouteResult(
            route_id=request.request_id,
            algorithm=request.algorithm,
            source_id=request.source_id,
            target_id=request.target_id,
            success=False,
            computation_time_ms=elapsed_ms,
            nodes_expanded=result.nodes_expanded,
            error="disconnected",
        )

    station_names = [
        graph.nodes[node_id].name or graph.nodes[node_id].station_id
        for node_id in result.node_ids
    ]

    return RouteResult(
        route_id=request.request_id,
        algorithm=request.algorithm,
        source_id=request.source_id,
        target_id=request.target_id,
        success=True,
        station_ids=result.node_ids,
        station_names=station_names,
        edge_ids=result.edge_ids,
        distance_m=round(result.distance_m, 2),
        node_count=len(result.node_ids),
        edge_count=len(result.edge_ids),
        computation_time_ms=round(elapsed_ms, 4),
        nodes_expanded=result.nodes_expanded,
    )


def build_routes(graph: Graph, requests: list[RouteRequest]) -> list[RouteResult]:
    """Build a ``RouteResult`` for every request, logging progress."""
    results: list[RouteResult] = []
    for i, request in enumerate(requests, start=1):
        result = build_route(graph, request)
        results.append(result)
        if i % 50 == 0 or i == len(requests):
            logger.info("Built %d/%d routes", i, len(requests))
    return results
