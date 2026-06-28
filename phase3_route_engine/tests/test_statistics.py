"""Unit tests for routing.statistics."""

from __future__ import annotations

from routing.models import AlgorithmType, RouteResult
from routing.statistics import compute_route_statistics


def _route(route_id, algorithm, distance_m, node_count, success=True, time_ms=1.0):
    return RouteResult(
        route_id=route_id,
        algorithm=algorithm,
        source_id="A",
        target_id="B",
        success=success,
        distance_m=distance_m,
        node_count=node_count,
        edge_count=max(node_count - 1, 0),
        computation_time_ms=time_ms,
    )


def test_compute_route_statistics_basic_counts():
    routes = [
        _route("r1", AlgorithmType.BFS, 1000.0, 2),
        _route("r2", AlgorithmType.DIJKSTRA, 2000.0, 3),
        _route("r3", AlgorithmType.ASTAR, 500.0, 2, success=False),
    ]
    stats = compute_route_statistics(routes)

    assert stats.total_routes == 3
    assert stats.successful_routes == 2
    assert stats.failed_routes == 1


def test_compute_route_statistics_longest_and_shortest():
    routes = [
        _route("r1", AlgorithmType.BFS, 1000.0, 2),
        _route("r2", AlgorithmType.DIJKSTRA, 5000.0, 4),
        _route("r3", AlgorithmType.ASTAR, 250.0, 2),
    ]
    stats = compute_route_statistics(routes)

    assert stats.longest_route["route_id"] == "r2"
    assert stats.shortest_route["route_id"] == "r3"


def test_compute_route_statistics_average_length():
    routes = [
        _route("r1", AlgorithmType.BFS, 1000.0, 2),
        _route("r2", AlgorithmType.DIJKSTRA, 3000.0, 2),
    ]
    stats = compute_route_statistics(routes)
    assert stats.average_route_length_m == 2000.0


def test_compute_route_statistics_per_algorithm_timing():
    routes = [
        _route("r1", AlgorithmType.BFS, 1000.0, 2, time_ms=2.0),
        _route("r2", AlgorithmType.BFS, 1000.0, 2, time_ms=4.0),
        _route("r3", AlgorithmType.DIJKSTRA, 1000.0, 2, time_ms=10.0),
    ]
    stats = compute_route_statistics(routes)

    bfs_timing = stats.timings_by_algorithm["bfs"]
    assert bfs_timing.route_count == 2
    assert bfs_timing.average_time_ms == 3.0

    dijkstra_timing = stats.timings_by_algorithm["dijkstra"]
    assert dijkstra_timing.route_count == 1
    assert dijkstra_timing.average_time_ms == 10.0


def test_compute_route_statistics_handles_no_successful_routes():
    routes = [_route("r1", AlgorithmType.BFS, 1000.0, 2, success=False)]
    stats = compute_route_statistics(routes)

    assert stats.successful_routes == 0
    assert stats.longest_route is None
    assert stats.shortest_route is None
