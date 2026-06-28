"""
graph/spatial_index.py
-----------------------
A lightweight, dependency-free 2-D spatial index used to efficiently find
the nearest GraphNode to an arbitrary (latitude, longitude) point.

Why this exists
----------------
Phase 2.2 must associate every track endpoint with the nearest station
node. With ~3k stations and ~7k tracks (2 endpoints each), a brute-force
nearest-neighbour search is O(n * m) — fine for a toy dataset but not
"production quality" and explicitly disallowed by the task brief.

Implementation
---------------
A classic KD-tree is built over stations projected onto a local
equirectangular plane (longitude scaled by cos(reference latitude) so
that the tree's notion of "near" in the projected plane reasonably
matches true geographic distance). Nearest-neighbour queries retrieve the
top-k candidates in the projected plane (O(log n) average case) and then
re-rank those few candidates using exact haversine (great-circle)
distance, so the distance ultimately reported is always geodesically
correct — only *candidate retrieval* relies on the projection.

No third-party dependencies (numpy/scipy/sklearn) are required, keeping
this module consistent with Phase 2.1's stdlib-only footprint.
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from graph.node_builder import GraphNode

logger = logging.getLogger(__name__)

_DEG_TO_M = 111_320.0  # approx. metres per degree of latitude (WGS-84)
_EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Geodesic distance (duplicated, minimal form of graph.utils.haversine_distance
# to keep this module self-contained and independently testable)
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexedPoint:
    """A single point stored in the spatial index."""

    key: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class NearestMatch:
    """Result of a nearest-neighbour query."""

    key: str
    distance_m: float


class _KDNode:
    __slots__ = ("point", "xy", "axis", "left", "right")

    def __init__(self, point: IndexedPoint, xy: tuple[float, float], axis: int):
        self.point = point
        self.xy = xy
        self.axis = axis
        self.left: "_KDNode | None" = None
        self.right: "_KDNode | None" = None


# ---------------------------------------------------------------------------
# Spatial index
# ---------------------------------------------------------------------------

class SpatialIndex:
    """
    A 2-D KD-tree over a set of geographic points, supporting fast nearest
    neighbour lookups.

    Parameters
    ----------
    points : sequence of IndexedPoint
        The points to index (typically one per GraphNode / station).
    k_candidates : int
        Number of projected-plane nearest neighbours retrieved per query
        before re-ranking by exact haversine distance. Higher values are
        more robust to projection distortion at the cost of speed.
    """

    def __init__(self, points: Sequence[IndexedPoint], k_candidates: int = 8):
        if not points:
            raise ValueError("SpatialIndex requires at least one point")

        self._k_candidates = max(1, k_candidates)
        self._ref_lat = sum(p.latitude for p in points) / len(points)

        items = [(p, self._project(p.latitude, p.longitude)) for p in points]
        self._root = self._build(items, depth=0)
        self._size = len(points)
        logger.info(
            "SpatialIndex built: %d points, k_candidates=%d, ref_lat=%.4f",
            self._size, self._k_candidates, self._ref_lat,
        )

    # -- construction --------------------------------------------------

    @classmethod
    def from_nodes(cls, nodes: Sequence["GraphNode"], k_candidates: int = 8) -> "SpatialIndex":
        """Build a SpatialIndex directly from a sequence of GraphNode."""
        points = [
            IndexedPoint(key=n.node_id, latitude=n.latitude, longitude=n.longitude)
            for n in nodes
        ]
        return cls(points, k_candidates=k_candidates)

    def _project(self, lat: float, lon: float) -> tuple[float, float]:
        """Equirectangular projection (metres) centred on the index's mean latitude."""
        x = lon * math.cos(math.radians(self._ref_lat)) * _DEG_TO_M
        y = lat * _DEG_TO_M
        return (x, y)

    def _build(self, items: list, depth: int) -> "_KDNode | None":
        if not items:
            return None
        axis = depth % 2
        items.sort(key=lambda it: it[1][axis])
        mid = len(items) // 2
        point, xy = items[mid]
        node = _KDNode(point, xy, axis)
        node.left = self._build(items[:mid], depth + 1)
        node.right = self._build(items[mid + 1:], depth + 1)
        return node

    # -- querying --------------------------------------------------------

    def __len__(self) -> int:
        return self._size

    def nearest(self, latitude: float, longitude: float) -> NearestMatch | None:
        """
        Return the nearest indexed point to (latitude, longitude), with the
        true great-circle distance in metres, or None if the index is empty.
        """
        if self._root is None:
            return None

        target_xy = self._project(latitude, longitude)
        heap: list[tuple[float, int, IndexedPoint]] = []  # (-dist2, tiebreak, point)
        counter = 0

        def visit(node: "_KDNode | None") -> None:
            nonlocal counter
            if node is None:
                return

            dx = node.xy[0] - target_xy[0]
            dy = node.xy[1] - target_xy[1]
            dist2 = dx * dx + dy * dy
            counter += 1
            entry = (-dist2, counter, node.point)

            if len(heap) < self._k_candidates:
                heapq.heappush(heap, entry)
            elif dist2 < -heap[0][0]:
                heapq.heapreplace(heap, entry)

            axis = node.axis
            diff = target_xy[axis] - node.xy[axis]
            near, far = (node.left, node.right) if diff < 0 else (node.right, node.left)

            visit(near)
            if len(heap) < self._k_candidates or diff * diff < -heap[0][0]:
                visit(far)

        visit(self._root)

        best_point: IndexedPoint | None = None
        best_dist = math.inf
        for _, _, point in heap:
            d = haversine_m(latitude, longitude, point.latitude, point.longitude)
            if d < best_dist:
                best_dist = d
                best_point = point

        if best_point is None:
            return None
        return NearestMatch(key=best_point.key, distance_m=best_dist)
