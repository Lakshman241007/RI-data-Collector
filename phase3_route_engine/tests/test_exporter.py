"""Unit tests for routing.exporter."""

from __future__ import annotations

import json

from routing.exporter import export_routes, export_statistics, export_validation
from routing.models import AlgorithmType, RouteResult
from routing.statistics import compute_route_statistics
from routing.validator import validate_routes


def test_export_routes_writes_valid_json(tmp_path, sample_graph):
    routes = [
        RouteResult(
            route_id="r1",
            algorithm=AlgorithmType.BFS,
            source_id="A",
            target_id="B",
            success=True,
            station_ids=["A", "B"],
            edge_ids=["AB"],
            node_count=2,
            edge_count=1,
            distance_m=10_000.0,
        )
    ]
    out_path = tmp_path / "routes.json"
    export_routes(routes, out_path)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["route_count"] == 1
    assert data["routes"][0]["algorithm"] == "bfs"
    assert data["routes"][0]["station_ids"] == ["A", "B"]


def test_export_statistics_writes_valid_json(tmp_path):
    routes = [
        RouteResult(
            route_id="r1",
            algorithm=AlgorithmType.DIJKSTRA,
            source_id="A",
            target_id="B",
            success=True,
            distance_m=5000.0,
            node_count=2,
            edge_count=1,
        )
    ]
    stats = compute_route_statistics(routes)
    out_path = tmp_path / "statistics.json"
    export_statistics(stats, out_path)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["total_routes"] == 1
    assert "generated_at" in data
    assert "timings_by_algorithm" in data


def test_export_validation_writes_valid_json(tmp_path, sample_graph):
    report = validate_routes(sample_graph, [])
    out_path = tmp_path / "validation.json"
    export_validation(report, out_path)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "issue_counts" in data
    assert "graph_load_issues" in data
