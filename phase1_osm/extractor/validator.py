"""
extractor.validator
=====================

Validates the merged railway dataset and produces statistics on data
quality issues. This module never fixes data — it only reports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from extractor.models import RailwayObject

logger = logging.getLogger("pipeline")

# Common OSM railway=* values. Anything outside this set is flagged as
# an "invalid_railway_tag" warning rather than silently accepted, since
# Phase 1 must surface unrecognised/likely-typo tag values for review.
KNOWN_RAILWAY_VALUES: Set[str] = {
    "rail", "light_rail", "subway", "tram", "narrow_gauge", "monorail",
    "funicular", "miniature", "disused", "abandoned", "construction",
    "proposed", "razed", "preserved",
    "station", "halt", "platform", "platform_edge", "tram_stop",
    "signal", "signal_box", "switch", "crossing", "level_crossing",
    "railway_crossing", "buffer_stop", "derail", "stop", "milestone",
    "turntable", "wash", "ventilation_shaft", "yard", "service_station",
    "traverser", "spur_junction", "junction",
}


@dataclass
class ValidationReport:
    total_objects: int = 0
    missing_id_count: int = 0
    missing_coordinates_count: int = 0
    duplicate_id_count: int = 0
    invalid_railway_tag_count: int = 0
    broken_geometry_count: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_objects": self.total_objects,
            "missing_id_count": self.missing_id_count,
            "missing_coordinates_count": self.missing_coordinates_count,
            "duplicate_id_count": self.duplicate_id_count,
            "invalid_railway_tag_count": self.invalid_railway_tag_count,
            "broken_geometry_count": self.broken_geometry_count,
            "issues": self.issues,
        }


def _has_coordinates(obj: RailwayObject) -> bool:
    if obj.osm_type == "node":
        return (
            isinstance(obj.geometry, list)
            and len(obj.geometry) == 2
            and obj.geometry[0] is not None
            and obj.geometry[1] is not None
        )
    if obj.osm_type == "way":
        return isinstance(obj.geometry, list) and len(obj.geometry) > 0
    # Relations are graphs of members, not raw coordinates.
    return True


def _is_valid_lon_lat(lon: Any, lat: Any) -> bool:
    if lon is None or lat is None:
        return False
    try:
        return -180.0 <= float(lon) <= 180.0 and -90.0 <= float(lat) <= 90.0
    except (TypeError, ValueError):
        return False


def _has_broken_geometry(obj: RailwayObject) -> bool:
    if obj.osm_type == "node":
        if not isinstance(obj.geometry, list) or len(obj.geometry) != 2:
            return True
        return not _is_valid_lon_lat(obj.geometry[0], obj.geometry[1])

    if obj.osm_type == "way":
        if not isinstance(obj.geometry, list) or len(obj.geometry) < 2:
            return True
        for point in obj.geometry:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                return True
            if not _is_valid_lon_lat(point[0], point[1]):
                return True

    return False


def validate_dataset(objects: List[RailwayObject]) -> ValidationReport:
    """Run all Phase 1 validation checks against the merged dataset."""
    report = ValidationReport(total_objects=len(objects))
    seen_ids: Set[Tuple[str, int]] = set()

    for obj in objects:
        if obj.osm_id is None:
            report.missing_id_count += 1
            report.issues.append(
                {"osm_type": obj.osm_type, "osm_id": obj.osm_id, "issue": "missing_id"}
            )
            continue  # nothing else can be meaningfully checked without an id

        key = (obj.osm_type, obj.osm_id)
        if key in seen_ids:
            report.duplicate_id_count += 1
            report.issues.append(
                {"osm_type": obj.osm_type, "osm_id": obj.osm_id, "issue": "duplicate_id"}
            )
        else:
            seen_ids.add(key)

        if not _has_coordinates(obj):
            report.missing_coordinates_count += 1
            report.issues.append(
                {"osm_type": obj.osm_type, "osm_id": obj.osm_id, "issue": "missing_coordinates"}
            )

        railway_value = obj.tags.get("railway")
        if railway_value is None:
            report.invalid_railway_tag_count += 1
            report.issues.append({
                "osm_type": obj.osm_type,
                "osm_id": obj.osm_id,
                "issue": "invalid_railway_tag",
                "detail": "missing 'railway' tag",
            })
        elif railway_value not in KNOWN_RAILWAY_VALUES:
            report.invalid_railway_tag_count += 1
            report.issues.append({
                "osm_type": obj.osm_type,
                "osm_id": obj.osm_id,
                "issue": "invalid_railway_tag",
                "detail": f"unrecognized railway value '{railway_value}'",
            })

        if _has_broken_geometry(obj):
            report.broken_geometry_count += 1
            report.issues.append(
                {"osm_type": obj.osm_type, "osm_id": obj.osm_id, "issue": "broken_geometry"}
            )

    logger.info(
        "Validation complete: %s objects | %s duplicate ids | %s missing coords | "
        "%s invalid tags | %s broken geometry",
        report.total_objects,
        report.duplicate_id_count,
        report.missing_coordinates_count,
        report.invalid_railway_tag_count,
        report.broken_geometry_count,
    )
    return report
