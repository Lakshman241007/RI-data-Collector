"""
extractor.models
================

Shared data model for the Railway Data Collection platform (Phase 1).

Every railway feature pulled from either OpenStreetMap Overpass or the
GeoFabrik PBF extract is normalized into a single ``RailwayObject`` so
that the merger, validator, and output stages do not need to know
which source produced a given feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# Geometry shapes by OSM type:
#   node      -> [lon, lat]
#   way       -> [[lon, lat], [lon, lat], ...]
#   relation  -> [{"type": "way", "ref": 123, "role": "..."}, ...]
Geometry = Optional[Union[List[float], List[List[float]], List[Dict[str, Any]]]]


@dataclass
class RailwayObject:
    """A single railway=* OSM node, way, or relation."""

    osm_id: int
    osm_type: str  # "node" | "way" | "relation"
    tags: Dict[str, str] = field(default_factory=dict)
    geometry: Geometry = None
    source: str = "unknown"  # "overpass" | "geofabrik"
    version: Optional[int] = None
    timestamp: Optional[str] = None

    @property
    def unique_id(self) -> str:
        """Composite key used to detect duplicates across sources."""
        return f"{self.osm_type}/{self.osm_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "osm_id": self.osm_id,
            "osm_type": self.osm_type,
            "tags": self.tags,
            "geometry": self.geometry,
            "source": self.source,
            "version": self.version,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RailwayObject":
        return cls(
            osm_id=data["osm_id"],
            osm_type=data["osm_type"],
            tags=data.get("tags", {}) or {},
            geometry=data.get("geometry"),
            source=data.get("source", "unknown"),
            version=data.get("version"),
            timestamp=data.get("timestamp"),
        )
