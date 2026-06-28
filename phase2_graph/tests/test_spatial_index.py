"""
tests/test_spatial_index.py
-----------------------------
Unit tests for graph.spatial_index.
"""

from __future__ import annotations

import math

import pytest

from graph.spatial_index import (
    IndexedPoint,
    SpatialIndex,
    haversine_m,
)


# ---------------------------------------------------------------------------
# haversine_m
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_zero_distance_for_identical_points(self):
        assert haversine_m(13.08, 80.27, 13.08, 80.27) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_chennai_to_bangalore_roughly_correct(self):
        # Chennai (13.0827, 80.2707) -> Bengaluru (12.9716, 77.5946)
        d = haversine_m(13.0827, 80.2707, 12.9716, 77.5946)
        # Real-world distance is ~290 km; allow a generous tolerance.
        assert 250_000 < d < 330_000

    def test_distance_is_symmetric(self):
        d1 = haversine_m(13.08, 80.27, 12.97, 77.59)
        d2 = haversine_m(12.97, 77.59, 13.08, 80.27)
        assert d1 == pytest.approx(d2, rel=1e-9)


# ---------------------------------------------------------------------------
# SpatialIndex construction
# ---------------------------------------------------------------------------

class TestSpatialIndexConstruction:
    def test_raises_on_empty_points(self):
        with pytest.raises(ValueError):
            SpatialIndex([])

    def test_len_reports_point_count(self):
        points = [
            IndexedPoint("a", 13.0, 80.0),
            IndexedPoint("b", 14.0, 81.0),
        ]
        index = SpatialIndex(points)
        assert len(index) == 2

    def test_single_point_index(self):
        index = SpatialIndex([IndexedPoint("only", 13.0, 80.0)])
        match = index.nearest(13.001, 80.001)
        assert match is not None
        assert match.key == "only"


# ---------------------------------------------------------------------------
# Nearest-neighbour queries
# ---------------------------------------------------------------------------

class TestNearestQuery:
    def _make_grid_index(self) -> SpatialIndex:
        # A small 3x3 grid of points, ~0.1 degree apart (~11km).
        points = []
        for i in range(3):
            for j in range(3):
                points.append(
                    IndexedPoint(f"p_{i}_{j}", 13.0 + i * 0.1, 80.0 + j * 0.1)
                )
        return SpatialIndex(points, k_candidates=4)

    def test_finds_exact_match(self):
        index = self._make_grid_index()
        match = index.nearest(13.1, 80.1)
        assert match is not None
        assert match.key == "p_1_1"
        assert match.distance_m == pytest.approx(0.0, abs=1.0)

    def test_finds_closest_of_several_candidates(self):
        index = self._make_grid_index()
        # Slightly closer to p_0_0 than p_1_1 or p_0_1/p_1_0
        match = index.nearest(13.02, 80.02)
        assert match is not None
        assert match.key == "p_0_0"

    def test_distance_matches_haversine(self):
        points = [IndexedPoint("a", 13.0, 80.0)]
        index = SpatialIndex(points)
        match = index.nearest(13.05, 80.05)
        expected = haversine_m(13.05, 80.05, 13.0, 80.0)
        assert match is not None
        assert match.distance_m == pytest.approx(expected, rel=1e-6)

    def test_correctness_against_brute_force_on_random_points(self):
        import random

        rng = random.Random(42)
        points = [
            IndexedPoint(f"n{i}", rng.uniform(8.0, 37.0), rng.uniform(68.0, 97.0))
            for i in range(200)
        ]
        index = SpatialIndex(points, k_candidates=10)

        for _ in range(25):
            qlat = rng.uniform(8.0, 37.0)
            qlon = rng.uniform(68.0, 97.0)

            brute_force_best = min(
                points, key=lambda p: haversine_m(qlat, qlon, p.latitude, p.longitude)
            )
            brute_force_dist = haversine_m(
                qlat, qlon, brute_force_best.latitude, brute_force_best.longitude
            )

            match = index.nearest(qlat, qlon)
            assert match is not None
            assert match.distance_m == pytest.approx(brute_force_dist, rel=1e-6)

    def test_from_nodes_factory(self):
        from graph.node_builder import GraphNode

        nodes = [
            GraphNode("node_1", "1", "A", 13.0, 80.0),
            GraphNode("node_2", "2", "B", 14.0, 81.0),
        ]
        index = SpatialIndex.from_nodes(nodes)
        match = index.nearest(13.001, 80.001)
        assert match is not None
        assert match.key == "node_1"
