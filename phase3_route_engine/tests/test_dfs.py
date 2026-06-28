"""Unit tests for routing.dfs."""

from __future__ import annotations

from routing.dfs import dfs_path, dfs_traversal


def test_dfs_traversal_visits_whole_component(sample_graph):
    order = dfs_traversal(sample_graph, "A")
    assert set(order) == {"A", "B", "C", "D", "E"}
    assert order[0] == "A"
    assert len(order) == len(set(order))  # no duplicates


def test_dfs_traversal_unknown_node(sample_graph):
    assert dfs_traversal(sample_graph, "ghost") == []


def test_dfs_path_finds_a_valid_path(sample_graph):
    result = dfs_path(sample_graph, "A", "E")

    assert result.found
    assert result.node_ids[0] == "A"
    assert result.node_ids[-1] == "E"
    # Every consecutive pair must be an actual edge in the graph.
    for i in range(len(result.node_ids) - 1):
        a, b = result.node_ids[i], result.node_ids[i + 1]
        neighbor_ids = {n for n, _e in sample_graph.neighbors(a)}
        assert b in neighbor_ids


def test_dfs_path_same_node(sample_graph):
    result = dfs_path(sample_graph, "A", "A")
    assert result.found
    assert result.node_ids == ["A"]


def test_dfs_path_disconnected(sample_graph):
    result = dfs_path(sample_graph, "A", "F")
    assert not result.found


def test_dfs_path_missing_node(sample_graph):
    result = dfs_path(sample_graph, "A", "ghost")
    assert not result.found
