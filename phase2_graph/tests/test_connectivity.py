"""
tests/test_connectivity.py
-----------------------------
Unit tests for graph.connectivity.
"""

from __future__ import annotations

from graph.connectivity import (
    attach_edges_to_nodes,
    compute_connected_components,
    find_isolated_nodes,
)
from graph.edge_builder import GraphEdge
from graph.node_builder import GraphNode


def _node(node_id: str) -> GraphNode:
    return GraphNode(node_id=node_id, station_id=node_id, name=node_id, latitude=0.0, longitude=0.0)


def _edge(edge_id: str, source: str | None, target: str | None) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id, track_id=edge_id, source_node_id=source,
        target_node_id=target, geometry=[[0.0, 0.0], [1.0, 1.0]],
        length_m=100.0, gauge=None, electrified=None, usage=None,
    )


class TestAttachEdgesToNodes:
    def test_attaches_edge_to_both_endpoints(self):
        nodes = [_node("a"), _node("b")]
        edges = [_edge("e1", "a", "b")]
        attach_edges_to_nodes(nodes, edges)
        assert nodes[0].edge_ids == ["e1"]
        assert nodes[1].edge_ids == ["e1"]

    def test_self_loop_attaches_once(self):
        nodes = [_node("a")]
        edges = [_edge("e1", "a", "a")]
        attach_edges_to_nodes(nodes, edges)
        assert nodes[0].edge_ids == ["e1"]

    def test_edge_with_unmatched_endpoint_attaches_only_to_known_node(self):
        nodes = [_node("a")]
        edges = [_edge("e1", "a", None)]
        attach_edges_to_nodes(nodes, edges)
        assert nodes[0].edge_ids == ["e1"]

    def test_multiple_edges_accumulate(self):
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("e1", "a", "b"), _edge("e2", "a", "c")]
        attach_edges_to_nodes(nodes, edges)
        assert sorted(nodes[0].edge_ids) == ["e1", "e2"]
        assert nodes[1].edge_ids == ["e1"]
        assert nodes[2].edge_ids == ["e2"]


class TestFindIsolatedNodes:
    def test_nodes_with_no_edges_are_isolated(self):
        a, b = _node("a"), _node("b")
        b.edge_ids = ["e1"]
        isolated = find_isolated_nodes([a, b])
        assert isolated == [a]

    def test_empty_node_list(self):
        assert find_isolated_nodes([]) == []


class TestComputeConnectedComponents:
    def test_single_connected_chain(self):
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("e1", "a", "b"), _edge("e2", "b", "c")]
        components = compute_connected_components(nodes, edges)
        assert len(components) == 1
        assert sorted(components[0]) == ["a", "b", "c"]

    def test_two_disconnected_components(self):
        nodes = [_node("a"), _node("b"), _node("c"), _node("d")]
        edges = [_edge("e1", "a", "b"), _edge("e2", "c", "d")]
        components = compute_connected_components(nodes, edges)
        assert len(components) == 2
        sizes = sorted(len(c) for c in components)
        assert sizes == [2, 2]

    def test_isolated_node_is_its_own_component(self):
        nodes = [_node("a"), _node("b"), _node("isolated")]
        edges = [_edge("e1", "a", "b")]
        components = compute_connected_components(nodes, edges)
        assert len(components) == 2
        assert ["isolated"] in components

    def test_edges_with_missing_endpoint_do_not_merge_components(self):
        nodes = [_node("a"), _node("b")]
        edges = [_edge("e1", "a", None)]
        components = compute_connected_components(nodes, edges)
        assert len(components) == 2

    def test_components_sorted_largest_first(self):
        nodes = [_node(n) for n in ("a", "b", "c", "d", "e")]
        edges = [_edge("e1", "a", "b"), _edge("e2", "b", "c"), _edge("e3", "d", "e")]
        components = compute_connected_components(nodes, edges)
        assert len(components[0]) >= len(components[1])

    def test_empty_graph_returns_empty_list(self):
        assert compute_connected_components([], []) == []
