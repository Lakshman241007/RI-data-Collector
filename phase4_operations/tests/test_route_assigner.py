"""Tests for operations.route_assigner."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from operations.route_assigner import assign_routes, _travel_time_minutes


class TestTravelTimeMinutes:
    def test_basic_calculation(self):
        # 60 km at 60 km/h = 60 minutes
        result = _travel_time_minutes(60.0, 60.0)
        assert result == pytest.approx(60.0)

    def test_zero_speed_returns_zero(self):
        assert _travel_time_minutes(100.0, 0.0) == 0.0

    def test_proportional(self):
        t1 = _travel_time_minutes(100.0, 100.0)
        t2 = _travel_time_minutes(200.0, 100.0)
        assert t2 == pytest.approx(t1 * 2)


class TestAssignRoutes:
    def test_returns_one_route_per_train(self, tmp_path, sample_trains):
        routes_json = {
            "routes": [
                {
                    "route_id": "route_00001",
                    "success": True,
                    "source_id": "node_A",
                    "target_id": "node_B",
                    "station_ids": ["node_A", "node_B"],
                    "station_names": ["A", "B"],
                    "distance_m": 20000.0,
                    "node_count": 2,
                    "edge_count": 1,
                    "algorithm": "bfs",
                }
            ]
        }
        p = tmp_path / "routes.json"
        p.write_text(json.dumps(routes_json))
        train_routes, route_assignments = assign_routes(sample_trains, p)
        assert len(train_routes) == len(sample_trains)
        assert len(route_assignments) == len(sample_trains)

    def test_raises_on_empty_routes(self, tmp_path, sample_trains):
        p = tmp_path / "routes.json"
        p.write_text(json.dumps({"routes": []}))
        with pytest.raises(RuntimeError, match="No successful routes"):
            assign_routes(sample_trains, p)

    def test_distance_km_correct(self, tmp_path, sample_trains):
        routes_json = {
            "routes": [
                {
                    "route_id": "route_00001",
                    "success": True,
                    "source_id": "node_A",
                    "target_id": "node_B",
                    "station_ids": ["node_A", "node_B"],
                    "station_names": ["A", "B"],
                    "distance_m": 50000.0,
                    "node_count": 2,
                    "edge_count": 1,
                    "algorithm": "dijkstra",
                }
            ]
        }
        p = tmp_path / "routes.json"
        p.write_text(json.dumps(routes_json))
        train_routes, _ = assign_routes(sample_trains[:1], p)
        assert train_routes[0].distance_km == pytest.approx(50.0)
