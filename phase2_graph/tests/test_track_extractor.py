"""
tests/test_track_extractor.py
------------------------------
Unit tests for graph.track_extractor.
"""

from __future__ import annotations

import pytest

from graph.track_extractor import TRACK_TYPES, extract_tracks
from tests.fixtures import make_node_object, make_way_object


class TestExtractTracks:
    def test_extracts_rail_way(self):
        obj = make_way_object(railway="rail")
        result = extract_tracks([obj])
        assert len(result) == 1
        assert result[0].railway == "rail"

    def test_extracts_all_track_types(self):
        objects = [
            make_way_object(osm_id=str(i), railway=t)
            for i, t in enumerate(TRACK_TYPES)
        ]
        result = extract_tracks(objects)
        assert len(result) == len(TRACK_TYPES)

    def test_ignores_station_types(self):
        obj = make_node_object(railway="station")
        result = extract_tracks([obj])
        assert result == []

    def test_computes_length_from_geometry(self):
        # ~1.4 km segment
        obj = make_way_object(
            geometry=[[80.00, 13.00], [80.01, 13.01]]
        )
        result = extract_tracks([obj])
        assert result[0].length_m is not None
        assert result[0].length_m > 0

    def test_length_is_none_when_no_geometry(self):
        from graph.models import RailwayObject

        obj = RailwayObject(
            osm_id="99",
            element_type="way",
            railway="rail",
            tags={"railway": "rail"},
        )
        result = extract_tracks([obj])
        assert len(result) == 1
        assert result[0].length_m is None

    def test_preserves_physical_attributes(self):
        tags = {
            "railway": "rail",
            "gauge": "1676",
            "electrified": "contact_line",
            "maxspeed": "130",
            "usage": "main",
            "bridge": "yes",
            "tunnel": "no",
            "layer": "1",
        }
        obj = make_way_object(tags=tags)
        result = extract_tracks([obj])
        t = result[0]
        assert t.gauge == "1676"
        assert t.electrified == "contact_line"
        assert t.maxspeed == "130"
        assert t.usage == "main"
        assert t.bridge == "yes"
        assert t.tunnel == "no"
        assert t.layer == "1"

    def test_preserves_all_original_tags(self):
        tags = {
            "railway": "tram",
            "gauge": "1000",
            "operator": "MTC",
            "surface": "asphalt",
        }
        obj = make_way_object(railway="tram", tags=tags)
        result = extract_tracks([obj])
        assert result[0].tags == tags

    def test_geometry_is_preserved(self):
        geom = [[80.27, 13.08], [80.28, 13.09], [80.29, 13.10]]
        obj = make_way_object(geometry=geom)
        result = extract_tracks([obj])
        assert result[0].geometry == geom

    def test_to_dict_round_trip(self):
        obj = make_way_object()
        track = extract_tracks([obj])[0]
        d = track.to_dict()
        assert d["osm_id"] == track.osm_id
        assert d["railway"] == track.railway
        assert d["length_m"] == track.length_m
        assert "geometry" in d
        assert "tags" in d

    def test_empty_input_returns_empty_list(self):
        assert extract_tracks([]) == []

    def test_multipoint_length_sums_segments(self):
        # Three collinear points: total length ≈ sum of two segments
        geom = [[80.00, 13.00], [80.01, 13.00], [80.02, 13.00]]
        obj = make_way_object(geometry=geom)
        result = extract_tracks([obj])
        t = result[0]

        # Each ~0.01° lon at lat 13° ≈ 1083 m; two segments ≈ 2166 m total
        assert t.length_m == pytest.approx(2166.9, abs=50)
