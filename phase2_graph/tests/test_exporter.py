"""
tests/test_exporter.py
-----------------------
Unit tests for graph.exporter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph.exporter import export_stations, export_tracks
from tests.fixtures import make_station, make_track


class TestExportStations:
    def test_creates_file(self, tmp_path):
        stations = [make_station()]
        out = tmp_path / "stations.json"
        export_stations(stations, out)
        assert out.exists()

    def test_output_is_valid_json_array(self, tmp_path):
        stations = [make_station("1"), make_station("2", name="T. Nagar")]
        out = tmp_path / "stations.json"
        export_stations(stations, out)
        data = json.loads(out.read_text())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_station_fields_present(self, tmp_path):
        s = make_station(osm_id="42", name="Egmore")
        out = tmp_path / "stations.json"
        export_stations([s], out)
        data = json.loads(out.read_text())
        record = data[0]
        for field in ("osm_id", "name", "latitude", "longitude", "railway", "tags"):
            assert field in record, f"Missing field: {field}"
        assert record["osm_id"] == "42"
        assert record["name"] == "Egmore"

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "deep" / "nested" / "stations.json"
        export_stations([], out)
        assert out.exists()

    def test_empty_list_produces_empty_array(self, tmp_path):
        out = tmp_path / "stations.json"
        export_stations([], out)
        assert json.loads(out.read_text()) == []


class TestExportTracks:
    def test_creates_file(self, tmp_path):
        tracks = [make_track()]
        out = tmp_path / "tracks.json"
        export_tracks(tracks, out)
        assert out.exists()

    def test_output_is_valid_json_array(self, tmp_path):
        tracks = [make_track("1"), make_track("2", railway="tram")]
        out = tmp_path / "tracks.json"
        export_tracks(tracks, out)
        data = json.loads(out.read_text())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_track_fields_present(self, tmp_path):
        t = make_track(osm_id="99")
        out = tmp_path / "tracks.json"
        export_tracks([t], out)
        data = json.loads(out.read_text())
        record = data[0]
        for field in (
            "osm_id", "railway", "geometry", "length_m",
            "gauge", "electrified", "maxspeed", "tags"
        ):
            assert field in record, f"Missing field: {field}"
        assert record["osm_id"] == "99"

    def test_geometry_serialised_correctly(self, tmp_path):
        geom = [[80.27, 13.08], [80.28, 13.09]]
        t = make_track(geometry=geom)
        out = tmp_path / "tracks.json"
        export_tracks([t], out)
        data = json.loads(out.read_text())
        assert data[0]["geometry"] == geom

    def test_empty_list_produces_empty_array(self, tmp_path):
        out = tmp_path / "tracks.json"
        export_tracks([], out)
        assert json.loads(out.read_text()) == []
