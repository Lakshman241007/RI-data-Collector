"""Unit tests for routing.route_builder."""

from __future__ import annotations

from routing.models import AlgorithmType, RequestKind, RouteRequest
from routing.route_builder import build_route, build_routes


def _req(algorithm, source, target, request_id="r1"):
    return RouteRequest(
        request_id=request_id,
        source_id=source,
        target_id=target,
        algorithm=algorithm,
        kind=RequestKind.SAMPLED,
    )


def test_build_route_success_dijkstra(sample_graph):
    request = _req(AlgorithmType.DIJKSTRA, "A", "E")
    route = build_route(sample_graph, request)

    assert route.success
    assert route.station_ids == ["A", "B", "C", "E"]
    assert route.station_names == ["Alpha", "Bravo", "Charlie", "Echo"]
    assert route.node_count == 4
    assert route.edge_count == 3
    assert route.distance_m == 35_000.0
    assert route.computation_time_ms >= 0.0


def test_build_route_missing_node(sample_graph):
    request = _req(AlgorithmType.BFS, "A", "ghost")
    route = build_route(sample_graph, request)

    assert not route.success
    assert route.error is not None
    assert route.error.startswith("missing_node")


def test_build_route_disconnected(sample_graph):
    request = _req(AlgorithmType.ASTAR, "A", "F")
    route = build_route(sample_graph, request)

    assert not route.success
    assert route.error == "disconnected"


def test_build_routes_batch(sample_graph):
    requests = [
        _req(AlgorithmType.BFS, "A", "E", "r1"),
        _req(AlgorithmType.DFS, "A", "C", "r2"),
        _req(AlgorithmType.DIJKSTRA, "A", "ghost", "r3"),
    ]
    routes = build_routes(sample_graph, requests)

    assert len(routes) == 3
    assert routes[0].success
    assert routes[1].success
    assert not routes[2].success
