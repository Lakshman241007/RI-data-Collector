"""
tests/fixtures.py
-----------------
Shared test data factories for Phase 2.1 unit tests.
"""

from __future__ import annotations

from graph.models import RailwayObject, Station, Track


# ---------------------------------------------------------------------------
# RailwayObject factories
# ---------------------------------------------------------------------------

def make_node_object(
    osm_id: str = "1",
    railway: str = "station",
    lat: float = 13.08,
    lon: float = 80.27,
    tags: dict | None = None,
) -> RailwayObject:
    return RailwayObject(
        osm_id=osm_id,
        element_type="node",
        railway=railway,
        tags=tags or {"railway": railway, "name": "Test Station"},
        latitude=lat,
        longitude=lon,
    )


def make_way_object(
    osm_id: str = "2",
    railway: str = "rail",
    geometry: list | None = None,
    tags: dict | None = None,
) -> RailwayObject:
    if geometry is None:
        # ~1 km segment
        geometry = [[80.27, 13.08], [80.28, 13.09]]
    return RailwayObject(
        osm_id=osm_id,
        element_type="way",
        railway=railway,
        tags=tags or {"railway": railway, "gauge": "1676", "electrified": "contact_line"},
        geometry=geometry,
    )


# ---------------------------------------------------------------------------
# Station / Track factories
# ---------------------------------------------------------------------------

def make_station(
    osm_id: str = "1",
    name: str = "Test Station",
    railway: str = "station",
) -> Station:
    return Station(
        osm_id=osm_id,
        name=name,
        latitude=13.08,
        longitude=80.27,
        railway=railway,
    )


def make_track(
    osm_id: str = "2",
    railway: str = "rail",
    geometry: list | None = None,
) -> Track:
    if geometry is None:
        geometry = [[80.27, 13.08], [80.28, 13.09]]
    from graph.utils import polyline_length_m

    length_m = round(polyline_length_m(geometry), 2)
    return Track(
        osm_id=osm_id,
        railway=railway,
        geometry=geometry,
        length_m=length_m,
        gauge="1676",
        electrified="contact_line",
    )
