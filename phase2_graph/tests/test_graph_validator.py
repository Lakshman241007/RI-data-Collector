"""
tests/test_graph_validator.py
--------------------------------
Unit tests for graph.graph_validator.
"""

from __future__ import annotations

from graph.edge_builder import GraphEdge
from graph.graph_validator import ValidationReport, validate_graph
from graph.node_builder import GraphNode


def _node(node_id: str, edge_ids: list[str] | None = None) -> GraphNode:
    n = GraphNode(node_id=node_id, station_id=node_id, name=node_id, latitude=0.0, longitude=0.0)
    n.edge_ids = edge_ids or []
    return n


def _edge(edge_id: str, source: str | None, target: str | None) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id, track_id=edge_id, source_node_id=source,
        target_node_id=target, geometry=[[0.0, 0.0], [1.0, 1.0]],
        length_m=100.0, gauge=None, electrified=None, usage=None,
    )


class TestValidateGraph:
    def test_isolated_station_detected(self):
        nodes = [_node("a", edge_ids=["e1"]), _node("b", edge_ids=[])]
        edges = [_edge("e1", "a", "a")]
        report = validate_graph(nodes, edges, [])
        assert len(report.isolated_stations) == 1
        assert report.isolated_stations[0]["node_id"] == "b"

    def test_disconnected_track_detected(self):
        nodes = [_node("a", edge_ids=["e1"])]
        edges = [_edge("e1", "a", None)]
        report = validate_graph(nodes, edges, [])
        assert len(report.disconnected_tracks) == 1
        assert report.disconnected_tracks[0]["edge_id"] == "e1"

    def test_self_loop_detected(self):
        nodes = [_node("a", edge_ids=["e1"])]
        edges = [_edge("e1", "a", "a")]
        report = validate_graph(nodes, edges, [])
        assert len(report.self_loops) == 1
        assert report.self_loops[0]["node_id"] == "a"

    def test_duplicate_edges_detected(self):
        nodes = [_node("a", edge_ids=["e1", "e2"]), _node("b", edge_ids=["e1", "e2"])]
        edges = [_edge("e1", "a", "b"), _edge("e2", "a", "b")]
        report = validate_graph(nodes, edges, [])
        assert len(report.duplicate_edges) == 1
        assert sorted(report.duplicate_edges[0]["edge_ids"]) == ["e1", "e2"]

    def test_no_duplicates_when_node_pairs_differ(self):
        nodes = [_node("a", ["e1"]), _node("b", ["e1"]), _node("c", ["e2"]), _node("d", ["e2"])]
        edges = [_edge("e1", "a", "b"), _edge("e2", "c", "d")]
        report = validate_graph(nodes, edges, [])
        assert report.duplicate_edges == []

    def test_self_loops_excluded_from_duplicate_detection(self):
        nodes = [_node("a", ["e1", "e2"])]
        edges = [_edge("e1", "a", "a"), _edge("e2", "a", "a")]
        report = validate_graph(nodes, edges, [])
        # Both are self-loops, not "duplicate edges between two distinct nodes"
        assert report.duplicate_edges == []
        assert len(report.self_loops) == 2

    def test_missing_node_reference_detected(self):
        nodes = [_node("a", edge_ids=["e1"])]
        edges = [_edge("e1", "a", "ghost")]
        report = validate_graph(nodes, edges, [])
        assert len(report.missing_nodes) == 1
        assert report.missing_nodes[0]["node_id"] == "ghost"
        assert report.missing_nodes[0]["role"] == "target"

    def test_edge_warnings_partitioned_by_type(self):
        nodes = [_node("a", ["e1"])]
        edges = [_edge("e1", "a", "a")]
        warnings = [
            {"type": "low_confidence_match", "track_id": "1"},
            {"type": "unmatched_endpoint", "track_id": "2"},
            {"type": "low_confidence_match", "track_id": "3"},
        ]
        report = validate_graph(nodes, edges, warnings)
        assert len(report.low_confidence_matches) == 2
        assert len(report.unmatched_endpoints) == 1

    def test_clean_graph_has_no_issues(self):
        nodes = [_node("a", ["e1"]), _node("b", ["e1"])]
        edges = [_edge("e1", "a", "b")]
        report = validate_graph(nodes, edges, [])
        assert report.isolated_stations == []
        assert report.disconnected_tracks == []
        assert report.duplicate_edges == []
        assert report.self_loops == []
        assert report.missing_nodes == []


class TestValidationReportToDict:
    def test_to_dict_includes_issue_counts(self):
        report = ValidationReport(
            isolated_stations=[{"node_id": "a"}],
            self_loops=[{"edge_id": "e1"}],
        )
        data = report.to_dict()
        assert data["issue_counts"]["isolated_stations"] == 1
        assert data["issue_counts"]["self_loops"] == 1
        assert data["issue_counts"]["disconnected_tracks"] == 0
        assert "generated_at" in data
