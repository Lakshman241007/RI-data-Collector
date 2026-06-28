"""
tests/test_edge_builder.py
-----------------------------
Unit tests for graph.edge_builder.
"""

from __future__ import annotations

from graph.edge_builder import EdgeMatchConfig, GraphEdge, build_edges
from graph.node_builder import GraphNode
from graph.spatial_index import SpatialIndex


def _track_record(**overrides) -> dict:
    record = {
        "osm_id": "100",
        "railway": "rail",
        "geometry": [[80.27, 13.08], [80.30, 13.10]],
        "length_m": 3500.0,
        "gauge": "1676",
        "electrified": "contact_line",
        "usage": "main",
        "tags": {"railway": "rail", "gauge": "1676"},
    }
    record.update(overrides)
    return record


def _index_with_stations() -> SpatialIndex:
    nodes = [
        GraphNode("node_a", "a", "Station A", 13.08, 80.27),
        GraphNode("node_b", "b", "Station B", 13.10, 80.30),
        GraphNode("node_c", "c", "Far Station", 30.0, 90.0),
    ]
    return SpatialIndex.from_nodes(nodes)


class TestBuildEdges:
    def test_builds_one_edge_per_track(self):
        index = _index_with_stations()
        edges, warnings = build_edges([_track_record(osm_id="1"), _track_record(osm_id="2")], index)
        assert len(edges) == 2

    def test_edge_fields_mapped_correctly(self):
        index = _index_with_stations()
        record = _track_record(
            osm_id="55", gauge="1000", electrified="no", usage="branch",
            railway="narrow_gauge",
        )
        edges, _ = build_edges([record], index)
        edge = edges[0]
        assert edge.edge_id == "edge_55"
        assert edge.track_id == "55"
        assert edge.gauge == "1000"
        assert edge.electrified == "no"
        assert edge.usage == "branch"
        assert edge.railway_type == "narrow_gauge"
        assert edge.geometry == record["geometry"]
        assert edge.tags == record["tags"]

    def test_endpoints_snap_to_nearest_nodes(self):
        index = _index_with_stations()
        # Geometry starts right at Station A and ends right at Station B.
        record = _track_record(geometry=[[80.27, 13.08], [80.30, 13.10]])
        edges, _ = build_edges([record], index)
        edge = edges[0]
        assert edge.source_node_id == "node_a"
        assert edge.target_node_id == "node_b"

    def test_track_with_insufficient_geometry_is_skipped(self):
        index = _index_with_stations()
        record = _track_record(geometry=[[80.27, 13.08]])
        edges, _ = build_edges([record], index)
        assert edges == []

    def test_track_with_empty_geometry_is_skipped(self):
        index = _index_with_stations()
        record = _track_record(geometry=[])
        edges, _ = build_edges([record], index)
        assert edges == []

    def test_far_endpoint_marked_unmatched_beyond_max_distance(self):
        index = _index_with_stations()
        config = EdgeMatchConfig(warn_snap_distance_m=1_000.0, max_snap_distance_m=5_000.0)
        # Endpoint far from any station (~thousands of km from all three).
        record = _track_record(geometry=[[80.27, 13.08], [0.0, 0.0]])
        edges, warnings = build_edges([record], index, config)
        edge = edges[0]
        assert edge.target_node_id is None
        assert any(w["type"] == "unmatched_endpoint" for w in warnings)

    def test_moderately_far_endpoint_flagged_low_confidence(self):
        index = _index_with_stations()
        config = EdgeMatchConfig(warn_snap_distance_m=100.0, max_snap_distance_m=50_000.0)
        # Endpoints offset slightly (~500m) from the exact station coordinates
        # so the snap distance falls between warn_snap_distance_m and max.
        record = _track_record(geometry=[[80.275, 13.085], [80.305, 13.105]])
        edges, warnings = build_edges([record], index, config)
        edge = edges[0]
        # Both endpoints are matched (within max), but flagged as low confidence
        assert edge.source_node_id is not None
        assert edge.target_node_id is not None
        assert any(w["type"] == "low_confidence_match" for w in warnings)

    def test_default_config_used_when_none_provided(self):
        index = _index_with_stations()
        edges, _ = build_edges([_track_record()], index, config=None)
        assert len(edges) == 1

    def test_empty_track_list_returns_empty_results(self):
        index = _index_with_stations()
        edges, warnings = build_edges([], index)
        assert edges == []
        assert warnings == []


class TestGraphEdgeToDict:
    def test_to_dict_contains_required_fields(self):
        edge = GraphEdge(
            edge_id="edge_1", track_id="1", source_node_id="node_a",
            target_node_id="node_b", geometry=[[80.0, 13.0], [80.1, 13.1]],
            length_m=1000.0, gauge="1676", electrified="no", usage="main",
            railway_type="rail", tags={"railway": "rail"},
        )
        data = edge.to_dict()
        for field in (
            "id", "track_id", "source", "target", "geometry",
            "length_m", "gauge", "electrified", "usage", "tags",
        ):
            assert field in data
        assert data["source"] == "node_a"
        assert data["target"] == "node_b"
