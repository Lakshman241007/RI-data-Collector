"""
graph/graph_validator.py
--------------------------
Validates the constructed Phase 2.2 railway graph for structural
integrity issues:

* isolated stations      — nodes with no connected edges
* disconnected tracks    — edges missing a source and/or target node
* duplicate edges        — multiple edges connecting the same node pair
* self loops             — edges whose source and target are the same node
* missing nodes          — edges referencing a node id absent from the
                            node set (defensive check; should not occur
                            given how edges are built, but verified anyway)

It also surfaces the snap-quality warnings raised by graph.edge_builder
(low-confidence matches and unmatched endpoints) so every issue produced
anywhere in the Phase 2.2 pipeline ends up in graph_validation.json.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from graph.edge_builder import GraphEdge
from graph.node_builder import GraphNode

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Aggregated validation findings for one graph build."""

    isolated_stations: list[dict[str, Any]] = field(default_factory=list)
    disconnected_tracks: list[dict[str, Any]] = field(default_factory=list)
    duplicate_edges: list[dict[str, Any]] = field(default_factory=list)
    self_loops: list[dict[str, Any]] = field(default_factory=list)
    missing_nodes: list[dict[str, Any]] = field(default_factory=list)
    low_confidence_matches: list[dict[str, Any]] = field(default_factory=list)
    unmatched_endpoints: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "issue_counts": {
                "isolated_stations": len(self.isolated_stations),
                "disconnected_tracks": len(self.disconnected_tracks),
                "duplicate_edges": len(self.duplicate_edges),
                "self_loops": len(self.self_loops),
                "missing_nodes": len(self.missing_nodes),
                "low_confidence_matches": len(self.low_confidence_matches),
                "unmatched_endpoints": len(self.unmatched_endpoints),
            },
            "isolated_stations": self.isolated_stations,
            "disconnected_tracks": self.disconnected_tracks,
            "duplicate_edges": self.duplicate_edges,
            "self_loops": self.self_loops,
            "missing_nodes": self.missing_nodes,
            "low_confidence_matches": self.low_confidence_matches,
            "unmatched_endpoints": self.unmatched_endpoints,
        }


def validate_graph(
    nodes: Sequence[GraphNode],
    edges: Sequence[GraphEdge],
    edge_warnings: Sequence[dict[str, Any]],
) -> ValidationReport:
    """
    Run all structural validation checks against a built graph.

    Parameters
    ----------
    nodes         : the graph's GraphNode list (with edge_ids populated by
                    graph.connectivity.attach_edges_to_nodes)
    edges         : the graph's GraphEdge list
    edge_warnings : warnings collected by graph.edge_builder.build_edges

    Returns
    -------
    ValidationReport
    """
    logger.info("Validating graph: %d nodes, %d edges", len(nodes), len(edges))

    node_ids = {n.node_id for n in nodes}

    isolated_stations = [
        {"node_id": n.node_id, "station_id": n.station_id, "name": n.name}
        for n in nodes
        if not n.edge_ids
    ]

    disconnected_tracks = [
        {
            "edge_id": e.edge_id,
            "track_id": e.track_id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
        }
        for e in edges
        if e.source_node_id is None or e.target_node_id is None
    ]

    self_loops = [
        {"edge_id": e.edge_id, "track_id": e.track_id, "node_id": e.source_node_id}
        for e in edges
        if e.source_node_id is not None and e.source_node_id == e.target_node_id
    ]

    duplicate_edges = _find_duplicate_edges(edges)
    missing_nodes = _find_missing_node_references(edges, node_ids)

    low_confidence_matches = [
        w for w in edge_warnings if w.get("type") == "low_confidence_match"
    ]
    unmatched_endpoints = [
        w for w in edge_warnings if w.get("type") == "unmatched_endpoint"
    ]

    report = ValidationReport(
        isolated_stations=isolated_stations,
        disconnected_tracks=disconnected_tracks,
        duplicate_edges=duplicate_edges,
        self_loops=self_loops,
        missing_nodes=missing_nodes,
        low_confidence_matches=low_confidence_matches,
        unmatched_endpoints=unmatched_endpoints,
    )

    logger.info(
        "Validation complete — isolated=%d disconnected=%d duplicates=%d "
        "self_loops=%d missing_nodes=%d low_confidence=%d unmatched=%d",
        len(isolated_stations), len(disconnected_tracks), len(duplicate_edges),
        len(self_loops), len(missing_nodes), len(low_confidence_matches),
        len(unmatched_endpoints),
    )
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_duplicate_edges(edges: Sequence[GraphEdge]) -> list[dict[str, Any]]:
    """Group fully-connected, non-self-loop edges by their node pair."""
    groups: dict[frozenset[str], list[str]] = defaultdict(list)

    for e in edges:
        if (
            e.source_node_id
            and e.target_node_id
            and e.source_node_id != e.target_node_id
        ):
            key = frozenset((e.source_node_id, e.target_node_id))
            groups[key].append(e.edge_id)

    return [
        {"node_pair": sorted(pair), "edge_ids": sorted(edge_ids)}
        for pair, edge_ids in groups.items()
        if len(edge_ids) > 1
    ]


def _find_missing_node_references(
    edges: Sequence[GraphEdge], node_ids: set[str]
) -> list[dict[str, Any]]:
    """Defensive check: every non-null endpoint must exist in the node set."""
    missing: list[dict[str, Any]] = []
    for e in edges:
        for role, nid in (("source", e.source_node_id), ("target", e.target_node_id)):
            if nid is not None and nid not in node_ids:
                missing.append({"edge_id": e.edge_id, "role": role, "node_id": nid})
    return missing
