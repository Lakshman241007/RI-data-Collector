"""Unit tests for routing.graph_loader."""

from __future__ import annotations

import json

from routing.graph_loader import load_graph


def _write_graph(tmp_path, nodes, edges):
    path = tmp_path / "graph.json"
    payload = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {"node_count": len(nodes), "edge_count": len(edges)},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_graph_basic(tmp_path):
    nodes = [
        {"id": "node_1", "station_id": "1", "name": "A", "latitude": 0.0, "longitude": 0.0, "station_type": "station"},
        {"id": "node_2", "station_id": "2", "name": "B", "latitude": 1.0, "longitude": 1.0, "station_type": "station"},
    ]
    edges = [
        {"id": "edge_1", "track_id": "1", "source": "node_1", "target": "node_2", "length_m": 100.0},
    ]
    path = _write_graph(tmp_path, nodes, edges)

    graph = load_graph(path)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert ("node_2", "edge_1") in graph.neighbors("node_1")
    assert ("node_1", "edge_1") in graph.neighbors("node_2")


def test_load_graph_skips_self_loops(tmp_path):
    nodes = [
        {"id": "node_1", "station_id": "1", "name": "A", "latitude": 0.0, "longitude": 0.0, "station_type": "station"},
    ]
    edges = [
        {"id": "edge_1", "track_id": "1", "source": "node_1", "target": "node_1", "length_m": 50.0},
    ]
    path = _write_graph(tmp_path, nodes, edges)

    graph = load_graph(path)

    assert graph.neighbors("node_1") == []
    assert graph.load_report.skipped_self_loops == 1


def test_load_graph_skips_null_endpoint_edges(tmp_path):
    nodes = [
        {"id": "node_1", "station_id": "1", "name": "A", "latitude": 0.0, "longitude": 0.0, "station_type": "station"},
    ]
    edges = [
        {"id": "edge_1", "track_id": "1", "source": "node_1", "target": None, "length_m": 50.0},
    ]
    path = _write_graph(tmp_path, nodes, edges)

    graph = load_graph(path)

    assert graph.neighbors("node_1") == []
    assert "edge_1" in graph.load_report.skipped_null_endpoint_edges


def test_load_graph_skips_missing_node_edges(tmp_path):
    nodes = [
        {"id": "node_1", "station_id": "1", "name": "A", "latitude": 0.0, "longitude": 0.0, "station_type": "station"},
    ]
    edges = [
        {"id": "edge_1", "track_id": "1", "source": "node_1", "target": "node_999", "length_m": 50.0},
    ]
    path = _write_graph(tmp_path, nodes, edges)

    graph = load_graph(path)

    assert graph.neighbors("node_1") == []
    assert "edge_1" in graph.load_report.skipped_missing_node_edges
