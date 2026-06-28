"""
graph/models.py
---------------
Dataclasses representing core railway domain objects.

Designed for Phase 2.1 (extraction only).
Phase 2.2 will extend these into graph nodes/edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Station:
    """Represents a railway station, halt, junction, stop, or platform."""

    osm_id: str
    name: str
    latitude: float
    longitude: float
    railway: str                            # station | halt | junction | stop | platform

    # Optional administrative / operational metadata
    operator: Optional[str] = None
    network: Optional[str] = None
    zone: Optional[str] = None
    division: Optional[str] = None

    # Full original tag bag – preserved for downstream phases
    tags: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalise osm_id to string regardless of source format
        self.osm_id = str(self.osm_id)

    # ------------------------------------------------------------------
    # Convenience helpers (read-only; no mutation)
    # ------------------------------------------------------------------

    @property
    def coordinates(self) -> tuple[float, float]:
        """(latitude, longitude) tuple."""
        return (self.latitude, self.longitude)

    def to_dict(self) -> dict[str, Any]:
        return {
            "osm_id": self.osm_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "railway": self.railway,
            "operator": self.operator,
            "network": self.network,
            "zone": self.zone,
            "division": self.division,
            "tags": self.tags,
        }


@dataclass
class Track:
    """Represents a railway track way."""

    osm_id: str
    railway: str                            # rail | tram | subway | …

    # Geometry as a list of [lon, lat] coordinate pairs (GeoJSON order)
    geometry: list[list[float]] = field(default_factory=list)
    length_m: Optional[float] = None

    # Physical / operational attributes
    gauge: Optional[str] = None
    electrified: Optional[str] = None
    maxspeed: Optional[str] = None
    usage: Optional[str] = None
    bridge: Optional[str] = None
    tunnel: Optional[str] = None
    layer: Optional[str] = None

    # Full original tag bag
    tags: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.osm_id = str(self.osm_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "osm_id": self.osm_id,
            "railway": self.railway,
            "geometry": self.geometry,
            "length_m": self.length_m,
            "gauge": self.gauge,
            "electrified": self.electrified,
            "maxspeed": self.maxspeed,
            "usage": self.usage,
            "bridge": self.bridge,
            "tunnel": self.tunnel,
            "layer": self.layer,
            "tags": self.tags,
        }


@dataclass
class RailwayObject:
    """
    Raw record as loaded from master_railway_dataset.json.

    The dataset stores every OSM element (node / way / relation) in a
    unified envelope; downstream extractors decide what to do with each.
    """

    osm_id: str
    element_type: str                       # node | way | relation
    railway: str                            # raw value of the 'railway' tag
    tags: dict[str, Any] = field(default_factory=dict)

    # Nodes carry a single point
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Ways carry a sequence of coordinate pairs [[lon, lat], …]
    geometry: list[list[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.osm_id = str(self.osm_id)
