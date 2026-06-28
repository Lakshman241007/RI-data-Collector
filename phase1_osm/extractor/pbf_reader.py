"""
extractor.pbf_reader
=====================

Reads the GeoFabrik ``india-latest.osm.pbf`` extract with pyosmium and
returns every ``railway=*`` node, way, and relation as a structured
``RailwayObject``.

Only objects tagged ``railway=*`` are kept; everything else (roads,
buildings, land use, etc.) is discarded while streaming through the
file so memory usage stays bounded.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

import osmium

from extractor.models import RailwayObject

logger = logging.getLogger("geofabrik")

# pyosmium represents relation member types as single-character codes;
# normalize to the same full words Overpass uses ("node"/"way"/"relation")
# so downstream merge/validation code doesn't need to care which source
# a relation came from.
_MEMBER_TYPE_MAP = {"n": "node", "w": "way", "r": "relation"}


class _RailwayHandler(osmium.SimpleHandler):
    """Collects every node/way/relation tagged railway=* from a PBF stream."""

    def __init__(self) -> None:
        super().__init__()
        self.objects: List[RailwayObject] = []

    def node(self, n: "osmium.osm.Node") -> None:
        if "railway" not in n.tags:
            return

        geometry = None
        if n.location.valid():
            geometry = [n.location.lon, n.location.lat]

        self.objects.append(
            RailwayObject(
                osm_id=n.id,
                osm_type="node",
                tags=dict(n.tags),
                geometry=geometry,
                source="geofabrik",
                version=n.version or None,
                timestamp=str(n.timestamp) if n.timestamp else None,
            )
        )

    def way(self, w: "osmium.osm.Way") -> None:
        if "railway" not in w.tags:
            return

        geometry = []
        for node_ref in w.nodes:
            try:
                if node_ref.location.valid():
                    geometry.append([node_ref.location.lon, node_ref.location.lat])
            except osmium.InvalidLocationError:
                logger.warning("Missing node location while resolving way %s", w.id)

        self.objects.append(
            RailwayObject(
                osm_id=w.id,
                osm_type="way",
                tags=dict(w.tags),
                geometry=geometry,
                source="geofabrik",
                version=w.version or None,
                timestamp=str(w.timestamp) if w.timestamp else None,
            )
        )

    def relation(self, r: "osmium.osm.Relation") -> None:
        if "railway" not in r.tags:
            return

        members = [
            {
                "type": _MEMBER_TYPE_MAP.get(member.type, member.type),
                "ref": member.ref,
                "role": member.role,
            }
            for member in r.members
        ]

        self.objects.append(
            RailwayObject(
                osm_id=r.id,
                osm_type="relation",
                tags=dict(r.tags),
                geometry=members,
                source="geofabrik",
                version=r.version or None,
                timestamp=str(r.timestamp) if r.timestamp else None,
            )
        )


def extract_railway_objects(pbf_path: Union[str, Path]) -> List[RailwayObject]:
    """Read an OSM PBF (or .osm XML) file and return all railway=* features.

    ``locations=True`` tells pyosmium to cache node coordinates as it
    streams through the file so that way geometries can be resolved
    without a second pass.
    """
    pbf_path = Path(pbf_path)
    if not pbf_path.exists():
        raise FileNotFoundError(f"PBF file not found: {pbf_path}")

    logger.info("Reading railway data from %s", pbf_path)
    handler = _RailwayHandler()
    handler.apply_file(str(pbf_path), locations=True)
    logger.info("Extracted %s railway objects from %s", len(handler.objects), pbf_path)
    return handler.objects
