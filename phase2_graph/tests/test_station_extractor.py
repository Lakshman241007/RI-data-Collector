"""
tests/test_station_extractor.py
--------------------------------
Unit tests for graph.station_extractor.
"""

from __future__ import annotations

import pytest

from graph.station_extractor import STATION_TYPES, extract_stations
from tests.fixtures import make_node_object, make_way_object


class TestExtractStations:
    def test_extracts_station_node(self):
        obj = make_node_object(railway="station", lat=13.08, lon=80.27)
        result = extract_stations([obj])
        assert len(result) == 1
        assert result[0].railway == "station"
        assert result[0].latitude == pytest.approx(13.08)
        assert result[0].longitude == pytest.approx(80.27)

    def test_extracts_all_station_types(self):
        objects = [
            make_node_object(osm_id=str(i), railway=t)
            for i, t in enumerate(STATION_TYPES)
        ]
        result = extract_stations(objects)
        assert len(result) == len(STATION_TYPES)

    def test_ignores_track_types(self):
        obj = make_node_object(railway="rail")
        result = extract_stations([obj])
        assert result == []

    def test_skips_node_without_coordinates(self):
        from graph.models import RailwayObject

        obj = RailwayObject(
            osm_id="5",
            element_type="node",
            railway="station",
            tags={"railway": "station"},
        )
        result = extract_stations([obj])
        assert result == []

    def test_falls_back_to_geometry_for_coordinates(self):
        from graph.models import RailwayObject

        obj = RailwayObject(
            osm_id="6",
            element_type="way",
            railway="platform",
            tags={"railway": "platform"},
            geometry=[[80.27, 13.08], [80.28, 13.09]],
        )
        result = extract_stations([obj])
        assert len(result) == 1
        # geometry is [lon, lat], so lat=13.08
        assert result[0].latitude == pytest.approx(13.08)

    def test_preserves_metadata_fields(self):
        obj = make_node_object(
            railway="station",
            tags={
                "railway": "station",
                "name": "Chennai Central",
                "operator": "Southern Railway",
                "network": "Indian Railways",
                "zone": "SR",
                "division": "Chennai",
            },
        )
        result = extract_stations([obj])
        s = result[0]
        assert s.name == "Chennai Central"
        assert s.operator == "Southern Railway"
        assert s.network == "Indian Railways"
        assert s.zone == "SR"
        assert s.division == "Chennai"

    def test_preserves_all_original_tags(self):
        extra_tags = {
            "railway": "station",
            "name": "T. Nagar",
            "wikidata": "Q12345",
            "wheelchair": "yes",
        }
        obj = make_node_object(tags=extra_tags)
        result = extract_stations([obj])
        assert result[0].tags == extra_tags

    def test_to_dict_round_trip(self):
        obj = make_node_object()
        station = extract_stations([obj])[0]
        d = station.to_dict()
        assert d["osm_id"] == station.osm_id
        assert d["railway"] == station.railway
        assert d["latitude"] == station.latitude
        assert "tags" in d

    def test_empty_input_returns_empty_list(self):
        assert extract_stations([]) == []
