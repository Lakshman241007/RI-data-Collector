"""Unit tests for routing.dijkstra."""

from __future__ import annotations

from routing.dijkstra import dijkstra_shortest_path


def test_dijkstra_finds_min_weight_path(sample_graph):
    result = dijkstra_shortest_path(sample_graph, "A", "E")

    assert result.found
    # A-D-E = 15km + 30km = 45km
    # A-B-C-E = 10km + 20km + 5km = 35km  <- cheaper
    assert result.node_ids == ["A", "B", "C", "E"]
    assert result.distance_m == 35_000.0


def test_dijkstra_same_node(sample_graph):
    result = dijkstra_shortest_path(sample_graph, "A", "A")
    assert result.found
    assert result.distance_m == 0.0


def test_dijkstra_disconnected(sample_graph):
    result = dijkstra_shortest_path(sample_graph, "A", "F")
    assert not result.found


def test_dijkstra_missing_node(sample_graph):
    result = dijkstra_shortest_path(sample_graph, "A", "ghost")
    assert not result.found


def test_dijkstra_edge_count_matches_node_count_minus_one(sample_graph):
    result = dijkstra_shortest_path(sample_graph, "A", "E")
    assert len(result.edge_ids) == len(result.node_ids) - 1
