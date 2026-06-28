"""
graph/edge_builder.py
-----------------------
Converts Phase 2.1 track records (output/tracks.json) into GraphEdge
objects — the edges of the Phase 2.2 railway graph — by snapping each
track's two endpoints to the nearest station node via
graph.spatial_index.SpatialIndex.

This module reads the plain dict shape produced by Track.to_dict()
(graph/models.py, Phase 2.1) and never imports or mutates Phase 2.1 code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from graph.spatial_index import SpatialIndex

logger = logging.getLogger(__name__)


@dataclass
class EdgeMatchConfig:
    """
    Thresholds controlling how track endpoints are snapped to stations.

    distance_m <= warn_snap_distance_m         -> confident match
    warn_snap_distance_m < distance_m <= max   -> match kept, but flagged
                                                   as a low-confidence match
    distance_m > max_snap_distance_m           -> endpoint left unmatched
                                                   (source/target = None)
    """

    warn_snap_distance_m: float = 20_000.0
    max_snap_distance_m: float = 75_000.0


@dataclass
class GraphEdge:
    """An edge of the railway graph, derived from one Phase 2.1 track."""

    edge_id: str
    track_id: str
    source_node_id: str | None
    target_node_id: str | None
    geometry: list[list[float]]
    length_m: float | None
    gauge: str | None
    electrified: str | None
    usage: str | None
    railway_type: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    source_distance_m: float | None = None
    target_distance_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.edge_id,
            "track_id": self.track_id,
            "source": self.source_node_id,
            "target": self.target_node_id,
            "geometry": self.geometry,
            "length_m": self.length_m,
            "gauge": self.gauge,
            "electrified": self.electrified,
            "usage": self.usage,
            "railway_type": self.railway_type,
            "tags": self.tags,
        }


def build_edges(
    track_records: Sequence[dict[str, Any]],
    index: SpatialIndex,
    config: EdgeMatchConfig | None = None,
) -> tuple[list[GraphEdge], list[dict[str, Any]]]:
    """
    Build one GraphEdge per valid track record, snapping both endpoints to
    the nearest GraphNode found via *index*.

    Parameters
    ----------
    track_records : sequence of dict
        Records shaped like Phase 2.1's tracks.json entries.
    index : SpatialIndex
        Pre-built spatial index over the graph's station nodes.
    config : EdgeMatchConfig, optional
        Snap-distance thresholds; defaults are used if omitted.

    Returns
    -------
    (edges, warnings)
        edges    : list[GraphEdge], one per track with usable geometry.
        warnings : list[dict] describing snap-quality issues (low
                   confidence matches / unmatched endpoints), consumed by
                   graph.graph_validator to populate graph_validation.json.
    """
    config = config or EdgeMatchConfig()
    logger.info("Building graph edges from %d track records", len(track_records))

    edges: list[GraphEdge] = []
    warnings: list[dict[str, Any]] = []
    skipped_bad_geometry = 0

    for record in track_records:
        track_id = str(record.get("osm_id"))
        geometry = record.get("geometry") or []

        if len(geometry) < 2:
            logger.warning(
                "Track osm_id=%s skipped — geometry has fewer than 2 points",
                track_id,
            )
            skipped_bad_geometry += 1
            continue

        lon0, lat0 = geometry[0][0], geometry[0][1]
        lon1, lat1 = geometry[-1][0], geometry[-1][1]

        source_id, source_dist = _snap_endpoint(
            track_id, "source", lat0, lon0, index, config, warnings
        )
        target_id, target_dist = _snap_endpoint(
            track_id, "target", lat1, lon1, index, config, warnings
        )

        edges.append(
            GraphEdge(
                edge_id=f"edge_{track_id}",
                track_id=track_id,
                source_node_id=source_id,
                target_node_id=target_id,
                geometry=geometry,
                length_m=record.get("length_m"),
                gauge=record.get("gauge"),
                electrified=record.get("electrified"),
                usage=record.get("usage"),
                railway_type=record.get("railway") or "",
                tags=record.get("tags") or {},
                source_distance_m=source_dist,
                target_distance_m=target_dist,
            )
        )

    logger.info(
        "Built %d graph edges (%d skipped: bad geometry, %d snap warnings)",
        len(edges), skipped_bad_geometry, len(warnings),
    )
    return edges, warnings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _snap_endpoint(
    track_id: str,
    role: str,
    lat: float,
    lon: float,
    index: SpatialIndex,
    config: EdgeMatchConfig,
    warnings: list[dict[str, Any]],
) -> tuple[str | None, float | None]:
    """Snap a single track endpoint to the nearest node, recording warnings."""
    match = index.nearest(lat, lon)

    if match is None:
        warnings.append(
            {
                "type": "unmatched_endpoint",
                "track_id": track_id,
                "role": role,
                "reason": "no_stations_available",
            }
        )
        return None, None

    if match.distance_m > config.max_snap_distance_m:
        warnings.append(
            {
                "type": "unmatched_endpoint",
                "track_id": track_id,
                "role": role,
                "nearest_node_id": match.key,
                "distance_m": round(match.distance_m, 2),
            }
        )
        return None, match.distance_m

    if match.distance_m > config.warn_snap_distance_m:
        warnings.append(
            {
                "type": "low_confidence_match",
                "track_id": track_id,
                "role": role,
                "node_id": match.key,
                "distance_m": round(match.distance_m, 2),
            }
        )

    return match.key, match.distance_m
