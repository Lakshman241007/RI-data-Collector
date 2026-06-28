"""
graph/graph_builder.py
-----------------------
Phase 2.2 orchestrator.

Builds a connected railway graph (GraphNode + GraphEdge) from the Phase
2.1 outputs (output/stations.json, output/tracks.json) and writes:

    output/railway_graph.json
    output/graph_statistics.json
    output/graph_validation.json

This module consumes Phase 2.1's outputs exactly as produced. It does not
import, modify, or re-implement any Phase 2.1 extraction logic
(graph/dataset_loader.py, graph/station_extractor.py,
graph/track_extractor.py, graph/exporter.py, graph/statistics.py,
graph/models.py).

Pipeline
--------
1. Load station/track records (plain JSON, Phase 2.1 output shape).
2. Build GraphNode objects from stations           (graph.node_builder)
3. Build a spatial index over the nodes            (graph.spatial_index)
4. Build GraphEdge objects from tracks, snapping
   endpoints to the nearest node                    (graph.edge_builder)
5. Attach edges to nodes, compute components        (graph.connectivity)
6. Validate the graph                               (graph.graph_validator)
7. Serialise railway_graph.json / graph_statistics.json /
   graph_validation.json
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from graph.connectivity import attach_edges_to_nodes, compute_connected_components
from graph.edge_builder import EdgeMatchConfig, GraphEdge, build_edges
from graph.graph_validator import ValidationReport, validate_graph
from graph.node_builder import GraphNode, build_nodes
from graph.spatial_index import SpatialIndex
from graph.utils import load_json, save_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loading Phase 2.1 outputs
# ---------------------------------------------------------------------------

def load_station_records(path: Path) -> list[dict[str, Any]]:
    """Load output/stations.json (Phase 2.1 output) as a list of dicts."""
    records = load_json(path)
    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON array of stations in {path}")
    return records


def load_track_records(path: Path) -> list[dict[str, Any]]:
    """Load output/tracks.json (Phase 2.1 output) as a list of dicts."""
    records = load_json(path)
    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON array of tracks in {path}")
    return records


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(
    station_records: list[dict[str, Any]],
    track_records: list[dict[str, Any]],
    edge_config: EdgeMatchConfig | None = None,
    k_candidates: int = 8,
) -> tuple[
    list[GraphNode],
    list[GraphEdge],
    list[list[str]],
    list[dict[str, Any]],
    ValidationReport,
]:
    """
    Build the full railway graph from raw station/track records.

    Returns
    -------
    (nodes, edges, components, edge_warnings, validation)
    """
    logger.info(
        "Building railway graph from %d stations and %d tracks",
        len(station_records), len(track_records),
    )

    nodes = build_nodes(station_records)
    if not nodes:
        raise ValueError("No valid stations available to build graph nodes")

    index = SpatialIndex.from_nodes(nodes, k_candidates=k_candidates)

    edges, edge_warnings = build_edges(
        track_records, index, edge_config or EdgeMatchConfig()
    )

    attach_edges_to_nodes(nodes, edges)
    components = compute_connected_components(nodes, edges)
    validation = validate_graph(nodes, edges, edge_warnings)

    logger.info(
        "Graph built: %d nodes, %d edges, %d connected components",
        len(nodes), len(edges), len(components),
    )
    return nodes, edges, components, edge_warnings, validation


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def serialize_graph(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    station_count: int,
    track_count: int,
) -> dict[str, Any]:
    """Build the railway_graph.json document structure."""
    return {
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
        "metadata": {
            "stations": station_count,
            "tracks": track_count,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def compute_graph_statistics(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    components: list[list[str]],
    validation: ValidationReport,
) -> dict[str, Any]:
    """Build the graph_statistics.json document structure."""
    num_nodes = len(nodes)
    num_edges = len(edges)
    degree_sum = sum(len(n.edge_ids) for n in nodes)
    average_degree = round(degree_sum / num_nodes, 4) if num_nodes else 0.0

    total_length_m = sum(e.length_m for e in edges if e.length_m is not None)

    return {
        "node_count": num_nodes,
        "edge_count": num_edges,
        "average_node_degree": average_degree,
        "isolated_stations": len(validation.isolated_stations),
        "connected_components": len(components),
        "largest_component_size": max((len(c) for c in components), default=0),
        "total_track_length_m": round(total_length_m, 2),
        "total_track_length_km": round(total_length_m / 1000, 3),
        "self_loops": len(validation.self_loops),
        "duplicate_edges": len(validation.duplicate_edges),
        "disconnected_tracks": len(validation.disconnected_tracks),
        "low_confidence_matches": len(validation.low_confidence_matches),
        "unmatched_endpoints": len(validation.unmatched_endpoints),
    }


# ---------------------------------------------------------------------------
# High-level pipeline entry point (used by main.py)
# ---------------------------------------------------------------------------

def run_graph_pipeline(settings: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """
    Run the complete Phase 2.2 pipeline using a settings dict shaped like
    config/graph_settings.json, resolved relative to *base_dir*.

    Reads stations.json / tracks.json, builds the graph, validates it, and
    writes railway_graph.json, graph_statistics.json, and
    graph_validation.json.

    Returns
    -------
    dict
        The graph_statistics.json contents (useful for logging a summary).
    """
    input_cfg = settings["input"]
    output_cfg = settings["output"]

    stations_path = base_dir / input_cfg["directory"] / input_cfg["stations_file"]
    tracks_path = base_dir / input_cfg["directory"] / input_cfg["tracks_file"]

    out_dir = base_dir / output_cfg["directory"]
    out_dir.mkdir(parents=True, exist_ok=True)

    graph_path = out_dir / output_cfg["graph_file"]
    stats_path = out_dir / output_cfg["statistics_file"]
    validation_path = out_dir / output_cfg["validation_file"]

    spatial_cfg = settings.get("spatial_index", {})
    matching_cfg = settings.get("edge_matching", {})
    edge_config = EdgeMatchConfig(
        warn_snap_distance_m=matching_cfg.get("warn_snap_distance_m", 20_000.0),
        max_snap_distance_m=matching_cfg.get("max_snap_distance_m", 75_000.0),
    )

    station_records = load_station_records(stations_path)
    track_records = load_track_records(tracks_path)

    nodes, edges, components, _warnings, validation = build_graph(
        station_records,
        track_records,
        edge_config=edge_config,
        k_candidates=spatial_cfg.get("k_nearest_candidates", 8),
    )

    graph_json = serialize_graph(
        nodes, edges, len(station_records), len(track_records)
    )
    stats_json = compute_graph_statistics(nodes, edges, components, validation)
    validation_json = validation.to_dict()

    save_json(graph_json, graph_path)
    save_json(stats_json, stats_path)
    save_json(validation_json, validation_path)

    logger.info("railway_graph.json written → %s", graph_path)
    logger.info("graph_statistics.json written → %s", stats_path)
    logger.info("graph_validation.json written → %s", validation_path)

    return stats_json
