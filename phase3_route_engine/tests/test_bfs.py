"""Unit tests for routing.bfs."""

from __future__ import annotations

from routing.bfs import bfs_connected_components, bfs_connectivity, bfs_shortest_path


def test_bfs_connectivity_reaches_whole_component(sample_graph):
    reachable = bfs_connectivity(sample_graph, "A")
    assert reachable == {"A", "B", "C", "D", "E"}


def test_bfs_connectivity_unknown_node_returns_empty(sample_graph):
    assert bfs_connectivity(sample_graph, "does_not_exist") == set()


def test_bfs_connected_components(sample_graph):
    components = bfs_connected_components(sample_graph)
    component_sets = sorted((frozenset(c) for c in components), key=len, reverse=True)

    assert frozenset({"A", "B", "C", "D", "E"}) in component_sets
    assert frozenset({"F", "G"}) in component_sets
    assert frozenset({"H"}) in component_sets
    assert len(components) == 3


def test_bfs_shortest_path_within_component(sample_graph):
    result = bfs_shortest_path(sample_graph, "A", "E")

    assert result.found
    assert result.node_ids[0] == "A"
    assert result.node_ids[-1] == "E"
    # Fewest hops: A-D-E (2 hops) vs A-B-C-E (3 hops)
    assert len(result.node_ids) == 3
    assert result.node_ids == ["A", "D", "E"]


def test_bfs_shortest_path_same_node(sample_graph):
    result = bfs_shortest_path(sample_graph, "A", "A")
    assert result.found
    assert result.node_ids == ["A"]
    assert result.distance_m == 0.0


def test_bfs_shortest_path_disconnected(sample_graph):
    result = bfs_shortest_path(sample_graph, "A", "F")
    assert not result.found


def test_bfs_shortest_path_missing_node(sample_graph):
    result = bfs_shortest_path(sample_graph, "A", "ghost")
    assert not result.found
