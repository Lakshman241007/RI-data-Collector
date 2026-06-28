"""
routing.models
--------------
Core data structures shared across the Phase 3.1 Railway Route Engine.

These are plain ``dataclasses`` with type hints (Python 3.13). No module in
this package depends on Phase 2 code directly — the engine only ever reads
the Phase 2 *output* artifact ``railway_graph.json`` from disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Node:
    """A single railway node (station / halt / junction / platform / stop)."""

    id: str
    station_id: str
    name: str
    latitude: float
    longitude: float
    station_type: str


@dataclass(frozen=True, slots=True)
class Edge:
    """A single railway track segment connecting two nodes."""

    id: str
    track_id: str
    source: str
    target: str
    length_m: float
    gauge: Optional[str] = None
    electrified: Optional[str] = None
    usage: Optional[str] = None
    railway_type: Optional[str] = None


@dataclass(slots=True)
class GraphLoadReport:
    """Issues encountered while loading the graph from disk.

    These are *data quality* issues inherited from the Phase 2 artifact
    (e.g. a track with a null endpoint, or a self-loop). They are kept
    separate from per-route validation issues but are surfaced in
    ``validation.json`` for transparency.
    """

    node_count: int = 0
    edge_count: int = 0
    skipped_self_loops: int = 0
    skipped_null_endpoint_edges: list[str] = field(default_factory=list)
    skipped_missing_node_edges: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Graph:
    """In-memory railway graph with an adjacency-list representation."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    # node_id -> list of (neighbor_node_id, edge_id)
    adjacency: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    load_report: GraphLoadReport = field(default_factory=GraphLoadReport)

    def neighbors(self, node_id: str) -> list[tuple[str, str]]:
        """Return ``[(neighbor_node_id, edge_id), ...]`` for ``node_id``."""
        return self.adjacency.get(node_id, [])

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def edge_length(self, edge_id: str) -> float:
        edge = self.edges.get(edge_id)
        return edge.length_m if edge is not None else 0.0


# ---------------------------------------------------------------------------
# Routing primitives
# ---------------------------------------------------------------------------

class AlgorithmType(str, Enum):
    """Supported pathfinding algorithms."""

    BFS = "bfs"
    DFS = "dfs"
    DIJKSTRA = "dijkstra"
    ASTAR = "astar"


class RequestKind(str, Enum):
    """How a route request was generated — used purely for reporting."""

    SAMPLED = "sampled"
    SYNTHETIC_DISCONNECTED = "synthetic_disconnected"
    SYNTHETIC_MISSING_NODE = "synthetic_missing_node"


@dataclass(slots=True)
class RouteRequest:
    """A request to find a route between two nodes using a given algorithm."""

    request_id: str
    source_id: str
    target_id: str
    algorithm: AlgorithmType
    kind: RequestKind = RequestKind.SAMPLED


@dataclass(slots=True)
class PathResult:
    """Raw output of a pathfinding algorithm, before route-building."""

    found: bool
    node_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    distance_m: float = 0.0
    nodes_expanded: int = 0


@dataclass(slots=True)
class RouteResult:
    """A fully built, exportable route (or a recorded failure)."""

    route_id: str
    algorithm: AlgorithmType
    source_id: str
    target_id: str
    success: bool
    station_ids: list[str] = field(default_factory=list)
    station_names: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    distance_m: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    computation_time_ms: float = 0.0
    nodes_expanded: int = 0
    error: Optional[str] = None
