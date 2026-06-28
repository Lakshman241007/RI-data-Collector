"""
graph/station_extractor.py
--------------------------
Extracts Station objects from a list of RailwayObject instances.

Station-type railway values:
    station | halt | junction | stop | platform
"""

from __future__ import annotations

import logging
from typing import Sequence

from graph.models import RailwayObject, Station
from graph.utils import get_tag, safe_float

logger = logging.getLogger(__name__)

# The set of railway tag values that identify station-like features.
STATION_TYPES: frozenset[str] = frozenset(
    ["station", "halt", "junction", "stop", "platform"]
)


def extract_stations(objects: Sequence[RailwayObject]) -> list[Station]:
    """
    Filter *objects* and return a list of Station dataclass instances.

    Only records whose ``railway`` value is in STATION_TYPES are kept.
    Records missing usable coordinates are skipped and logged.

    Parameters
    ----------
    objects : sequence of RailwayObject

    Returns
    -------
    list[Station]
    """
    logger.info(
        "Station extraction started — processing %d objects", len(objects)
    )

    stations: list[Station] = []
    skipped_no_coords = 0
    skipped_wrong_type = 0

    for obj in objects:
        if obj.railway not in STATION_TYPES:
            skipped_wrong_type += 1
            continue

        lat, lon = _resolve_coordinates(obj)
        if lat is None or lon is None:
            logger.debug(
                "osm_id=%s (%s) skipped — no usable coordinates",
                obj.osm_id,
                obj.railway,
            )
            skipped_no_coords += 1
            continue

        station = _build_station(obj, lat, lon)
        stations.append(station)

    logger.info(
        "Station extraction complete: %d extracted, %d skipped (no coords), "
        "%d skipped (wrong type)",
        len(stations),
        skipped_no_coords,
        skipped_wrong_type,
    )
    return stations


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_coordinates(
    obj: RailwayObject,
) -> tuple[float | None, float | None]:
    """
    Return (lat, lon) from node coordinates or the first geometry point.
    """
    if obj.latitude is not None and obj.longitude is not None:
        return obj.latitude, obj.longitude

    # Fall back to first geometry node (centre of a platform polygon, etc.)
    if obj.geometry:
        lon, lat = obj.geometry[0]
        return lat, lon

    # Try tags in case the dataset hoisted coordinates there
    lat = safe_float(obj.tags.get("lat") or obj.tags.get("latitude"))
    lon = safe_float(
        obj.tags.get("lon") or obj.tags.get("longitude") or obj.tags.get("lng")
    )
    return lat, lon


def _build_station(obj: RailwayObject, lat: float, lon: float) -> Station:
    tags = obj.tags

    return Station(
        osm_id=obj.osm_id,
        name=get_tag(tags, "name") or get_tag(tags, "name:en") or "",
        latitude=lat,
        longitude=lon,
        railway=obj.railway,
        operator=get_tag(tags, "operator"),
        network=get_tag(tags, "network"),
        zone=get_tag(tags, "zone") or get_tag(tags, "fare_zone"),
        division=get_tag(tags, "division"),
        tags=tags,
    )
