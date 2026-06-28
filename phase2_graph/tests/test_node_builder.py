"""
tests/test_node_builder.py
-----------------------------
Unit tests for graph.node_builder.
"""

from __future__ import annotations

from graph.node_builder import GraphNode, build_node_lookup, build_nodes


def _station_record(**overrides) -> dict:
    record = {
        "osm_id": "1",
        "name": "Egmore",
        "latitude": 13.08,
        "longitude": 80.27,
        "railway": "station",
        "tags": {"railway": "station", "name": "Egmore"},
    }
    record.update(overrides)
    return record


class TestBuildNodes:
    def test_builds_one_node_per_record(self):
        records = [_station_record(osm_id="1"), _station_record(osm_id="2")]
        nodes = build_nodes(records)
        assert len(nodes) == 2

    def test_node_fields_mapped_correctly(self):
        record = _station_record(
            osm_id="42", name="Chennai Central", latitude=13.082, longitude=80.275,
            railway="junction",
        )
        nodes = build_nodes([record])
        node = nodes[0]
        assert node.station_id == "42"
        assert node.name == "Chennai Central"
        assert node.latitude == 13.082
        assert node.longitude == 80.275
        assert node.station_type == "junction"
        assert node.node_id == "node_42"
        assert node.edge_ids == []

    def test_node_id_is_deterministic_and_unique(self):
        nodes = build_nodes([_station_record(osm_id="1"), _station_record(osm_id="2")])
        ids = {n.node_id for n in nodes}
        assert ids == {"node_1", "node_2"}

    def test_missing_coordinates_skipped(self):
        records = [
            _station_record(osm_id="1", latitude=None),
            _station_record(osm_id="2", longitude=None),
            _station_record(osm_id="3"),
        ]
        nodes = build_nodes(records)
        assert len(nodes) == 1
        assert nodes[0].station_id == "3"

    def test_duplicate_station_id_skipped(self):
        records = [_station_record(osm_id="1"), _station_record(osm_id="1")]
        nodes = build_nodes(records)
        assert len(nodes) == 1

    def test_missing_name_defaults_to_empty_string(self):
        record = _station_record(osm_id="1", name=None)
        nodes = build_nodes([record])
        assert nodes[0].name == ""

    def test_empty_input_returns_empty_list(self):
        assert build_nodes([]) == []


class TestGraphNodeToDict:
    def test_to_dict_contains_required_fields(self):
        node = GraphNode(
            node_id="node_1", station_id="1", name="Egmore",
            latitude=13.08, longitude=80.27, station_type="station",
        )
        node.edge_ids = ["edge_2", "edge_1"]
        data = node.to_dict()
        for field in ("id", "station_id", "name", "latitude", "longitude", "edge_ids"):
            assert field in data
        assert data["id"] == "node_1"
        assert data["station_id"] == "1"
        # edge_ids should be sorted for deterministic output
        assert data["edge_ids"] == ["edge_1", "edge_2"]


class TestBuildNodeLookup:
    def test_lookup_maps_node_id_to_node(self):
        nodes = build_nodes([_station_record(osm_id="1"), _station_record(osm_id="2")])
        lookup = build_node_lookup(nodes)
        assert set(lookup.keys()) == {"node_1", "node_2"}
        assert lookup["node_1"] is nodes[0]
