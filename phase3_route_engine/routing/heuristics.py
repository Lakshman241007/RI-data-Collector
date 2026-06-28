"""
routing.heuristics
-------------------
Geographic heuristics used by A*.

The graph's coordinates are plain latitude/longitude pairs, so the natural
admissible heuristic for "distance remaining" is the great-circle
(haversine) distance to the goal — it never overestimates the true
along-track distance, which is what makes A* with this heuristic optimal.
"""

from __future__ import annotations

import math

from routing.models import Graph

EARTH_RADIUS_M = 6_371_000.0


def haversine_distance_m(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def make_geo_heuristic(graph: Graph, target_id: str):
    """Build an ``h(node_id) -> metres`` heuristic function for A*.

    The heuristic is the haversine distance from ``node_id`` to
    ``target_id``. If either node is missing coordinates, falls back to 0
    (which degrades A* to Dijkstra for that lookup, but stays admissible).
    """
    target = graph.nodes.get(target_id)

    def heuristic(node_id: str) -> float:
        node = graph.nodes.get(node_id)
        if node is None or target is None:
            return 0.0
        return haversine_distance_m(
            node.latitude, node.longitude, target.latitude, target.longitude
        )

    return heuristic
