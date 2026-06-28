"""
graph/track_extractor.py
------------------------
Extracts Track objects from a list of RailwayObject instances.

Track-type railway values:
    rail | tram | subway | light_rail | narrow_gauge |
    construction | disused | preserved | miniature | monorail
"""

from __future__ import annotations

import logging
from typing import Sequence

from graph.models import RailwayObject, Track
from graph.utils import get_tag, polyline_length_m

logger = logging.getLogger(__name__)

TRACK_TYPES: frozenset[str] = frozenset(
    [
        "rail",
        "tram",
        "subway",
        "light_rail",
        "narrow_gauge",
        "construction",
        "disused",
        "preserved",
        "miniature",
        "monorail",
    ]
)


def extract_tracks(objects: Sequence[RailwayObject]) -> list[Track]:
    """
    Filter *objects* and return a list of Track dataclass instances.

    Only records whose ``railway`` value is in TRACK_TYPES are kept.
    Track length is computed from geometry where available.

    Parameters
    ----------
    objects : sequence of RailwayObject

    Returns
    -------
    list[Track]
    """
    logger.info(
        "Track extraction started — processing %d objects", len(objects)
    )

    tracks: list[Track] = []
    skipped_wrong_type = 0
    no_geometry = 0

    for obj in objects:
        if obj.railway not in TRACK_TYPES:
            skipped_wrong_type += 1
            continue

        track = _build_track(obj)
        if not track.geometry:
            no_geometry += 1
            logger.debug(
                "osm_id=%s (%s) has no geometry — length will be None",
                obj.osm_id,
                obj.railway,
            )
        tracks.append(track)

    logger.info(
        "Track extraction complete: %d extracted (%d without geometry), "
        "%d skipped (wrong type)",
        len(tracks),
        no_geometry,
        skipped_wrong_type,
    )
    return tracks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_track(obj: RailwayObject) -> Track:
    tags = obj.tags
    geometry = obj.geometry

    length_m: float | None = None
    if geometry:
        length_m = polyline_length_m(geometry)
        length_m = round(length_m, 2)

    return Track(
        osm_id=obj.osm_id,
        railway=obj.railway,
        geometry=geometry,
        length_m=length_m,
        gauge=get_tag(tags, "gauge"),
        electrified=get_tag(tags, "electrified"),
        maxspeed=get_tag(tags, "maxspeed"),
        usage=get_tag(tags, "usage"),
        bridge=get_tag(tags, "bridge"),
        tunnel=get_tag(tags, "tunnel"),
        layer=get_tag(tags, "layer"),
        tags=tags,
    )
