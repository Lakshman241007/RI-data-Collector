"""
tests/test_graph_builder.py
------------------------------
Unit and integration tests for graph.graph_builder — the Phase 2.2
orchestrator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph.edge_builder import EdgeMatchConfig
from graph.graph_builder import (
    build_graph,
    compute_graph_statistics,
    load_station_records,
    load_track_records,
    run_graph_pipeline,
    serialize_graph,
)


def _station(osm_id, lat, lon, name="", railway="station"):
    return {
        "osm_id": osm_id, "name": name, "latitude": lat, "longitude": lon,
        "railway": railway, "tags": {"railway": railway},
    }


def _track(osm_id, geometry, **overrides):
    record = {
        "osm_id": osm_id, "railway": "rail", "geometry": geometry,
        "length_m": 1000.0, "gauge": "1676", "electrified": "no",
        "usage": "main", "tags": {"railway": "rail"},
    }
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

class TestLoadRecords:
    def test_load_station_records_reads_json_array(self, tmp_path: Path):
        path = tmp_path / "stations.json"
        path.write_text(json.dumps([_station("1", 13.0, 80.0)]))
        records = load_station_records(path)
        assert len(records) == 1

    def test_load_track_records_reads_json_array(self, tmp_path: Path):
        path = tmp_path / "tracks.json"
        path.write_text(json.dumps([_track("1", [[80.0, 13.0], [80.1, 13.1]])]))
        records = load_track_records(path)
        assert len(records) == 1

    def test_load_station_records_rejects_non_array(self, tmp_path: Path):
        path = tmp_path / "stations.json"
        path.write_text(json.dumps({"not": "a list"}))
        with pytest.raises(ValueError):
            load_station_records(path)


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_builds_nodes_and_edges_from_records(self):
        stations = [
            _station("1", 13.08, 80.27, name="A"),
            _station("2", 13.10, 80.30, name="B"),
        ]
        tracks = [_track("100", [[80.27, 13.08], [80.30, 13.10]])]

        nodes, edges, components, warnings, validation = build_graph(stations, tracks)

        assert len(nodes) == 2
        assert len(edges) == 1
        assert edges[0].source_node_id == "node_1"
        assert edges[0].target_node_id == "node_2"
        assert len(components) == 1

    def test_raises_when_no_stations(self):
        with pytest.raises(ValueError):
            build_graph([], [_track("1", [[80.0, 13.0], [80.1, 13.1]])])

    def test_handles_no_tracks(self):
        stations = [_station("1", 13.0, 80.0)]
        nodes, edges, components, warnings, validation = build_graph(stations, [])
        assert len(nodes) == 1
        assert edges == []
        assert len(components) == 1  # the lone station is its own component
        assert len(validation.isolated_stations) == 1

    def test_respects_custom_edge_config(self):
        stations = [
            _station("1", 13.0, 80.0),
            _station("2", 13.0, 82.0),  # ~220 km away
        ]
        tracks = [_track("100", [[80.001, 13.0], [81.999, 13.0]])]
        strict_config = EdgeMatchConfig(warn_snap_distance_m=10.0, max_snap_distance_m=100.0)

        nodes, edges, components, warnings, validation = build_graph(
            stations, tracks, edge_config=strict_config
        )
        # Both endpoints are far beyond the strict max -> unmatched
        assert edges[0].source_node_id is None
        assert edges[0].target_node_id is None
        assert len(validation.disconnected_tracks) == 1


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

class TestSerializeGraph:
    def test_output_shape_matches_spec(self):
        stations = [_station("1", 13.0, 80.0)]
        tracks = []
        nodes, edges, components, warnings, validation = build_graph(stations, tracks)
        doc = serialize_graph(nodes, edges, len(stations), len(tracks))

        assert set(doc.keys()) == {"nodes", "edges", "metadata"}
        assert doc["metadata"]["stations"] == 1
        assert doc["metadata"]["tracks"] == 0
        assert isinstance(doc["nodes"], list)
        assert isinstance(doc["edges"], list)


class TestComputeGraphStatistics:
    def test_statistics_keys_present(self):
        stations = [_station("1", 13.0, 80.0), _station("2", 13.1, 80.1)]
        tracks = [_track("100", [[80.0, 13.0], [80.1, 13.1]])]
        nodes, edges, components, warnings, validation = build_graph(stations, tracks)
        stats = compute_graph_statistics(nodes, edges, components, validation)

        expected_keys = {
            "node_count", "edge_count", "average_node_degree",
            "isolated_stations", "connected_components",
            "largest_component_size", "total_track_length_m",
            "total_track_length_km", "self_loops", "duplicate_edges",
            "disconnected_tracks",
        }
        assert expected_keys.issubset(stats.keys())
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 1

    def test_average_degree_zero_when_no_nodes(self):
        stats = compute_graph_statistics([], [], [], _empty_validation())
        assert stats["average_node_degree"] == 0.0
        assert stats["node_count"] == 0


def _empty_validation():
    from graph.graph_validator import ValidationReport
    return ValidationReport()


# ---------------------------------------------------------------------------
# End-to-end pipeline (writes real files)
# ---------------------------------------------------------------------------

class TestRunGraphPipeline:
    def _settings(self) -> dict:
        return {
            "input": {
                "directory": "input",
                "stations_file": "stations.json",
                "tracks_file": "tracks.json",
            },
            "output": {
                "directory": "output",
                "graph_file": "railway_graph.json",
                "statistics_file": "graph_statistics.json",
                "validation_file": "graph_validation.json",
            },
            "spatial_index": {"k_nearest_candidates": 4},
            "edge_matching": {"warn_snap_distance_m": 5000, "max_snap_distance_m": 50000},
        }

    def test_pipeline_writes_all_three_output_files(self, tmp_path: Path):
        (tmp_path / "input").mkdir()
        (tmp_path / "input" / "stations.json").write_text(
            json.dumps([_station("1", 13.0, 80.0), _station("2", 13.05, 80.05)])
        )
        (tmp_path / "input" / "tracks.json").write_text(
            json.dumps([_track("100", [[80.0, 13.0], [80.05, 13.05]])])
        )

        stats = run_graph_pipeline(self._settings(), tmp_path)

        out_dir = tmp_path / "output"
        assert (out_dir / "railway_graph.json").exists()
        assert (out_dir / "graph_statistics.json").exists()
        assert (out_dir / "graph_validation.json").exists()
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 1

    def test_pipeline_output_is_valid_json(self, tmp_path: Path):
        (tmp_path / "input").mkdir()
        (tmp_path / "input" / "stations.json").write_text(
            json.dumps([_station("1", 13.0, 80.0)])
        )
        (tmp_path / "input" / "tracks.json").write_text(json.dumps([]))

        run_graph_pipeline(self._settings(), tmp_path)

        graph_doc = json.loads((tmp_path / "output" / "railway_graph.json").read_text())
        assert "nodes" in graph_doc and "edges" in graph_doc and "metadata" in graph_doc

        validation_doc = json.loads(
            (tmp_path / "output" / "graph_validation.json").read_text()
        )
        assert "issue_counts" in validation_doc
