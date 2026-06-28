"""Unit tests for routing.validator."""

from __future__ import annotations

from routing.models import AlgorithmType, RouteResult
from routing.validator import validate_routes


def _success_route(route_id, source, target, station_ids, edge_ids):
    return RouteResult(
        route_id=route_id,
        algorithm=AlgorithmType.DIJKSTRA,
        source_id=source,
        target_id=target,
        success=True,
        station_ids=station_ids,
        edge_ids=edge_ids,
        node_count=len(station_ids),
        edge_count=len(edge_ids),
    )


def test_validate_routes_classifies_missing_node(sample_graph):
    routes = [
        RouteResult(
            route_id="r1",
            algorithm=AlgorithmType.BFS,
            source_id="A",
            target_id="ghost",
            success=False,
            error="missing_node:ghost",
        )
    ]
    report = validate_routes(sample_graph, routes)
    assert report.issue_counts["missing_nodes"] == 1
    assert report.issue_counts["disconnected_paths"] == 0
    assert report.issue_counts["invalid_routes"] == 0


def test_validate_routes_classifies_disconnected(sample_graph):
    routes = [
        RouteResult(
            route_id="r1",
            algorithm=AlgorithmType.DFS,
            source_id="A",
            target_id="F",
            success=False,
            error="disconnected",
        )
    ]
    report = validate_routes(sample_graph, routes)
    assert report.issue_counts["disconnected_paths"] == 1


def test_validate_routes_passes_valid_route(sample_graph):
    routes = [_success_route("r1", "A", "B", ["A", "B"], ["AB"])]
    report = validate_routes(sample_graph, routes)
    assert report.issue_counts["invalid_routes"] == 0


def test_validate_routes_flags_repeated_station(sample_graph):
    routes = [_success_route("r1", "A", "A", ["A", "B", "A"], ["AB", "AB"])]
    report = validate_routes(sample_graph, routes)
    assert report.issue_counts["invalid_routes"] == 1
    assert report.invalid_routes[0]["detail"] == "repeated_station_in_route"


def test_validate_routes_flags_edge_endpoint_mismatch(sample_graph):
    # Claims edge "AB" connects A and C, which is false.
    routes = [_success_route("r1", "A", "C", ["A", "C"], ["AB"])]
    report = validate_routes(sample_graph, routes)
    assert report.issue_counts["invalid_routes"] == 1
    assert "edge_endpoint_mismatch" in report.invalid_routes[0]["detail"]


def test_validate_routes_includes_graph_load_issues(sample_graph):
    report = validate_routes(sample_graph, [])
    assert report.graph_load_issues["node_count"] == len(sample_graph.nodes)
