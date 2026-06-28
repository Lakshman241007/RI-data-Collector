"""
extractor.merger
==================

Merges the bulk GeoFabrik extract with the latest Overpass edits into a
single deduplicated list of ``RailwayObject`` instances.

Rule: if the same OSM type+id exists in both sources, the Overpass
version wins (it reflects the most recent edits). All railway tags on
the winning object are preserved as-is — no tags are dropped or
rewritten during merge.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from extractor.models import RailwayObject

logger = logging.getLogger("pipeline")


def _key(obj: RailwayObject) -> Tuple[str, int]:
    return (obj.osm_type, obj.osm_id)


def merge_datasets(
    geofabrik_objects: List[RailwayObject],
    overpass_objects: List[RailwayObject],
) -> Tuple[List[RailwayObject], int]:
    """Merge GeoFabrik (bulk) and Overpass (latest) railway objects.

    Returns a tuple of ``(merged_objects, duplicate_count)`` where
    ``duplicate_count`` is the number of OSM ids present in both
    sources (and therefore resolved in favor of Overpass).
    """
    merged: Dict[Tuple[str, int], RailwayObject] = {}

    for obj in geofabrik_objects:
        merged[_key(obj)] = obj

    duplicate_count = 0
    for obj in overpass_objects:
        key = _key(obj)
        if key in merged:
            duplicate_count += 1
            logger.debug("Duplicate OSM id %s — preferring newer Overpass object", key)
        merged[key] = obj  # Overpass always wins on conflict

    result = list(merged.values())
    logger.info(
        "Merge complete: %s GeoFabrik + %s Overpass objects -> %s unique "
        "(%s duplicates resolved in favor of Overpass)",
        len(geofabrik_objects),
        len(overpass_objects),
        len(result),
        duplicate_count,
    )
    return result, duplicate_count
