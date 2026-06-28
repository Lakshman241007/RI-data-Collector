"""
graph/node_builder.py
-----------------------
Converts Phase 2.1 station records (output/stations.json) into GraphNode
objects — the vertices of the Phase 2.2 railway graph.

This module reads the plain dict shape produced by Station.to_dict()
(graph/models.py, Phase 2.1) and never imports or mutates Phase 2.1 code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """A vertex of the railway graph, derived from one Phase 2.1 station."""

    node_id: str
    station_id: str
    name: str
    latitude: float
    longitude: float
    station_type: str = ""
    edge_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "station_id": self.station_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "station_type": self.station_type,
            "edge_ids": sorted(self.edge_ids),
        }


def build_nodes(station_records: Sequence[dict[str, Any]]) -> list[GraphNode]:
    """
    Build one GraphNode per valid station record.

    Parameters
    ----------
    station_records : sequence of dict
        Records shaped like Phase 2.1's stations.json entries, i.e. with
        at least ``osm_id``, ``latitude``, ``longitude``; ``name`` and
        ``railway`` are used if present.

    Returns
    -------
    list[GraphNode]
        One node per station with usable coordinates and a unique id.
        Records with missing coordinates or a duplicate station id are
        skipped and logged (never silently dropped without a trace).
    """
    logger.info("Building graph nodes from %d station records", len(station_records))

    nodes: list[GraphNode] = []
    seen_ids: set[str] = set()
    skipped_no_coords = 0
    skipped_duplicate = 0

    for record in station_records:
        station_id = str(record.get("osm_id"))
        latitude = record.get("latitude")
        longitude = record.get("longitude")

        if latitude is None or longitude is None:
            logger.warning(
                "Station osm_id=%s skipped — missing coordinates", station_id
            )
            skipped_no_coords += 1
            continue

        node_id = f"node_{station_id}"
        if node_id in seen_ids:
            logger.warning(
                "Station osm_id=%s skipped — duplicate station id", station_id
            )
            skipped_duplicate += 1
            continue
        seen_ids.add(node_id)

        nodes.append(
            GraphNode(
                node_id=node_id,
                station_id=station_id,
                name=record.get("name") or "",
                latitude=float(latitude),
                longitude=float(longitude),
                station_type=record.get("railway") or "",
            )
        )

    logger.info(
        "Built %d graph nodes (%d skipped: no coords, %d skipped: duplicate)",
        len(nodes), skipped_no_coords, skipped_duplicate,
    )
    return nodes


def build_node_lookup(nodes: Sequence[GraphNode]) -> dict[str, GraphNode]:
    """Return a node_id -> GraphNode lookup dict."""
    return {node.node_id: node for node in nodes}
