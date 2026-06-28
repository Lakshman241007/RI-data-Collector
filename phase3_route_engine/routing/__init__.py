"""
routing
-------
Phase 3.1 Railway Route Engine.

Pure-Python pathfinding over the Phase 2 railway graph artifact
(``railway_graph.json``). Implements BFS connectivity, DFS traversal,
Dijkstra shortest-distance, and A* (geographic-heuristic) shortest path,
plus route building, validation, statistics, and JSON export.
"""

from routing.models import (
    AlgorithmType,
    Edge,
    Graph,
    GraphLoadReport,
    Node,
    PathResult,
    RequestKind,
    RouteRequest,
    RouteResult,
)

__all__ = [
    "AlgorithmType",
    "Edge",
    "Graph",
    "GraphLoadReport",
    "Node",
    "PathResult",
    "RequestKind",
    "RouteRequest",
    "RouteResult",
]
