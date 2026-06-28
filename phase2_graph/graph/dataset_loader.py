"""
graph/dataset_loader.py
-----------------------
Loads master_railway_dataset.json and returns a list of validated
RailwayObject instances.

Expected top-level format (either of):

  [{"osm_id": …, "type": "node"|"way"|"relation", "tags": {…}, …}, …]

  or

  {"elements": [{…}, …]}

Every malformed record is skipped and logged; the loader never raises on
individual bad records so that a partial dataset is still usable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from graph.models import RailwayObject
from graph.utils import get_tag, load_json, safe_float

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> list[RailwayObject]:
    """
    Load the master railway dataset from *path*.

    Returns
    -------
    list[RailwayObject]
        All valid records.  Malformed records are skipped.
    """
    logger.info("Loading master dataset from: %s", path)

    raw = load_json(path)
    elements: list[dict[str, Any]] = _normalise_root(raw)

    logger.info("Total raw elements in dataset: %d", len(elements))

    objects: list[RailwayObject] = []
    skipped = 0

    for record in elements:
        obj = _parse_record(record)
        if obj is None:
            skipped += 1
            continue
        objects.append(obj)

    logger.info(
        "Loaded %d valid RailwayObjects (%d skipped / malformed)",
        len(objects),
        skipped,
    )
    return objects


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_root(raw: Any) -> list[dict[str, Any]]:
    """Accept both list-root and {elements: […]} formats."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # Overpass-style: {"elements": […]}
        if "elements" in raw:
            return raw["elements"]
        # Flat dict of id→record mappings (less common)
        return list(raw.values())
    logger.error("Unexpected root type in dataset: %s", type(raw).__name__)
    return []


def _parse_record(record: dict[str, Any]) -> RailwayObject | None:
    """
    Parse a single raw record into a RailwayObject.

    Returns None (and logs a warning) if the record is malformed.
    """
    if not isinstance(record, dict):
        logger.warning("Skipping non-dict record: %r", record)
        return None

    # ---- osm_id --------------------------------------------------------
    osm_id = record.get("osm_id") or record.get("id")
    if osm_id is None:
        logger.warning("Skipping record without osm_id: %r", record)
        return None

    # ---- element_type --------------------------------------------------
    element_type = str(record.get("type", "unknown")).lower()

    # ---- tags ----------------------------------------------------------
    tags: dict[str, Any] = record.get("tags") or {}
    if not isinstance(tags, dict):
        logger.warning("osm_id=%s has non-dict tags; using empty dict", osm_id)
        tags = {}

    # ---- railway value -------------------------------------------------
    railway = get_tag(tags, "railway")
    if railway is None:
        # Some datasets hoist railway to the top level
        railway = get_tag(record, "railway")
    if railway is None:
        logger.debug("osm_id=%s has no railway tag; skipping", osm_id)
        return None

    # ---- coordinates ---------------------------------------------------
    latitude = safe_float(record.get("lat") or record.get("latitude"))
    longitude = safe_float(record.get("lon") or record.get("longitude") or record.get("lng"))

    # ---- geometry (ways) -----------------------------------------------
    geometry: list[list[float]] = []
    raw_geom = record.get("geometry") or record.get("nodes_coords") or []
    if isinstance(raw_geom, list):
        geometry = _normalise_geometry(raw_geom)

    return RailwayObject(
        osm_id=str(osm_id),
        element_type=element_type,
        railway=railway,
        tags=tags,
        latitude=latitude,
        longitude=longitude,
        geometry=geometry,
    )


def _normalise_geometry(raw: list[Any]) -> list[list[float]]:
    """
    Accept multiple coordinate list formats and return [[lon, lat], …].

    Formats handled:
      • [[lon, lat], …]              – GeoJSON order
      • [{"lat": y, "lon": x}, …]   – Overpass node geometry
      • [[lat, lon], …]             – Legacy lat-first order (heuristic)
    """
    result: list[list[float]] = []
    for item in raw:
        if isinstance(item, dict):
            lat = safe_float(item.get("lat") or item.get("latitude"))
            lon = safe_float(item.get("lon") or item.get("longitude") or item.get("lng"))
            if lat is not None and lon is not None:
                result.append([lon, lat])
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            a, b = safe_float(item[0]), safe_float(item[1])
            if a is not None and b is not None:
                # Heuristic: longitudes are always < |180|; latitudes < |90|.
                # If first value's absolute is > 90 it is more likely a
                # longitude – keep as-is (already [lon, lat]).
                result.append([a, b])
    return result
