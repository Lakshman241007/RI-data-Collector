"""
routing.graph_loader
---------------------
Loads the Phase 2 artifact ``railway_graph.json`` and builds an in-memory
``Graph`` (nodes, edges, adjacency lists) for use by the routing algorithms.

This module is read-only with respect to Phase 2: it never imports or
modifies any Phase 2 code, it only consumes the JSON file that Phase 2
already produced.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from routing.models import Edge, Graph, GraphLoadReport, Node

logger = logging.getLogger(__name__)


def load_graph(path: Path | str) -> Graph:
    """Load ``railway_graph.json`` from ``path`` and build a ``Graph``.

    Data-quality issues inherited from Phase 2 (self-loops, edges with a
    null endpoint, edges referencing a node id that doesn't exist in the
    ``nodes`` array) are skipped when building the adjacency list, but are
    recorded on ``Graph.load_report`` so they can be surfaced later in
    ``validation.json``.
    """
    path = Path(path)
    logger.info("Loading railway graph from %s", path)

    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    nodes: dict[str, Node] = {}
    for raw_node in raw.get("nodes", []):
        node = Node(
            id=raw_node["id"],
            station_id=raw_node.get("station_id", ""),
            name=raw_node.get("name", "") or "",
            latitude=float(raw_node["latitude"]),
            longitude=float(raw_node["longitude"]),
            station_type=raw_node.get("station_type", "unknown"),
        )
        nodes[node.id] = node

    edges: dict[str, Edge] = {}
    adjacency: dict[str, list[tuple[str, str]]] = {node_id: [] for node_id in nodes}
    report = GraphLoadReport(node_count=len(nodes))

    for raw_edge in raw.get("edges", []):
        edge_id = raw_edge["id"]
        source = raw_edge.get("source")
        target = raw_edge.get("target")

        edge = Edge(
            id=edge_id,
            track_id=raw_edge.get("track_id", ""),
            source=source or "",
            target=target or "",
            length_m=float(raw_edge.get("length_m") or 0.0),
            gauge=raw_edge.get("gauge"),
            electrified=raw_edge.get("electrified"),
            usage=raw_edge.get("usage"),
            railway_type=raw_edge.get("railway_type"),
        )
        edges[edge_id] = edge

        # -- Skip edges with a missing (null) endpoint -----------------
        if not source or not target:
            report.skipped_null_endpoint_edges.append(edge_id)
            continue

        # -- Skip edges referencing a node id absent from `nodes` -------
        if source not in nodes or target not in nodes:
            report.skipped_missing_node_edges.append(edge_id)
            continue

        # -- Skip self-loops; they never help pathfinding ---------------
        if source == target:
            report.skipped_self_loops += 1
            continue

        adjacency.setdefault(source, []).append((target, edge_id))
        adjacency.setdefault(target, []).append((source, edge_id))

    report.edge_count = len(edges)

    logger.info(
        "Graph loaded: nodes=%d edges=%d (skipped: self_loops=%d "
        "null_endpoint=%d missing_node=%d)",
        len(nodes),
        len(edges),
        report.skipped_self_loops,
        len(report.skipped_null_endpoint_edges),
        len(report.skipped_missing_node_edges),
    )

    return Graph(nodes=nodes, edges=edges, adjacency=adjacency, load_report=report)
