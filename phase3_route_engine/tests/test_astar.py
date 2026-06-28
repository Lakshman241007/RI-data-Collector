"""Unit tests for routing.astar and routing.heuristics."""

from __future__ import annotations

from routing.astar import astar_shortest_path
from routing.dijkstra import dijkstra_shortest_path
from routing.heuristics import haversine_distance_m, make_geo_heuristic


def test_haversine_distance_zero_for_same_point():
    assert haversine_distance_m(10.0, 20.0, 10.0, 20.0) == 0.0


def test_haversine_distance_positive_for_distinct_points():
    d = haversine_distance_m(0.0, 0.0, 1.0, 1.0)
    assert d > 0.0


def test_geo_heuristic_zero_at_target(sample_graph):
    heuristic = make_geo_heuristic(sample_graph, "E")
    assert heuristic("E") == 0.0


def test_astar_matches_dijkstra_distance(sample_graph):
    """A* with an admissible heuristic must find the same optimal distance
    as Dijkstra (it may differ in nodes_expanded, not in the result)."""
    astar_result = astar_shortest_path(sample_graph, "A", "E")
    dijkstra_result = dijkstra_shortest_path(sample_graph, "A", "E")

    assert astar_result.found and dijkstra_result.found
    assert astar_result.distance_m == dijkstra_result.distance_m
    assert astar_result.node_ids == dijkstra_result.node_ids


def test_astar_same_node(sample_graph):
    result = astar_shortest_path(sample_graph, "A", "A")
    assert result.found
    assert result.distance_m == 0.0


def test_astar_disconnected(sample_graph):
    result = astar_shortest_path(sample_graph, "A", "F")
    assert not result.found


def test_astar_missing_node(sample_graph):
    result = astar_shortest_path(sample_graph, "A", "ghost")
    assert not result.found
