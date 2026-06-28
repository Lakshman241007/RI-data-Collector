"""Tests for operations.operations_validator."""
from __future__ import annotations

import pytest

from operations.operations_validator import validate_all
from operations.models import (
    PriorityLevel,
    Train,
    TrainRoute,
    TrainType,
    ValidationSeverity,
)


def _make_sched(train_id: str, schedule_type: str = "Daily") -> dict:
    return {
        "schedule_id": f"s_{train_id}",
        "train_id": train_id,
        "train_number": "TN-XX-0001",
        "train_type": "Express",
        "schedule_type": schedule_type,
        "priority": "High",
    }


class TestValidateAll:
    def test_clean_data_passes(self, sample_trains, sample_route, sample_timetable_entries):
        scheds = [_make_sched(t.train_id) for t in sample_trains]
        # supply one route per train
        from operations.models import TrainRoute
        routes = [
            TrainRoute(
                assignment_id=f"ra_{i}",
                train_id=t.train_id,
                route_id="route_00001",
                source_id="A", target_id="B",
                station_ids=("A", "B"),
                station_names=("A", "B"),
                distance_m=1000, distance_km=1.0,
                estimated_travel_time_minutes=1.0,
                algorithm="bfs", node_count=2, edge_count=1,
            )
            for i, t in enumerate(sample_trains)
        ]
        report = validate_all(sample_trains, routes, sample_timetable_entries, scheds, [])
        assert report.passed
        assert report.error_count == 0

    def test_missing_route_is_error(self, sample_trains, sample_timetable_entries):
        scheds = [_make_sched(t.train_id) for t in sample_trains]
        report = validate_all(sample_trains, [], sample_timetable_entries, scheds, [])
        assert not report.passed
        assert report.error_count > 0
        categories = [i.category for i in report.issues]
        assert "missing_route" in categories

    def test_platform_conflict_is_warning(self, sample_trains, sample_timetable_entries):
        scheds = [_make_sched(t.train_id) for t in sample_trains]
        from operations.models import TrainRoute
        routes = [
            TrainRoute(
                assignment_id=f"ra_{i}",
                train_id=t.train_id,
                route_id="route_00001",
                source_id="A", target_id="B",
                station_ids=("A", "B"),
                station_names=("A", "B"),
                distance_m=1000, distance_km=1.0,
                estimated_travel_time_minutes=1.0,
                algorithm="bfs", node_count=2, edge_count=1,
            )
            for i, t in enumerate(sample_trains)
        ]
        report = validate_all(
            sample_trains, routes, sample_timetable_entries, scheds,
            ["Platform conflict at station 'X': platform 1, trains t1 and t2"]
        )
        warnings = [i for i in report.issues if i.severity == ValidationSeverity.WARNING]
        assert len(warnings) >= 1

    def test_invalid_schedule_type_is_warning(self, sample_trains, sample_timetable_entries):
        scheds = [_make_sched(t.train_id, "INVALID") for t in sample_trains]
        from operations.models import TrainRoute
        routes = [
            TrainRoute(
                assignment_id=f"ra_{i}",
                train_id=t.train_id,
                route_id="route_00001",
                source_id="A", target_id="B",
                station_ids=("A", "B"),
                station_names=("A", "B"),
                distance_m=1000, distance_km=1.0,
                estimated_travel_time_minutes=1.0,
                algorithm="bfs", node_count=2, edge_count=1,
            )
            for i, t in enumerate(sample_trains)
        ]
        report = validate_all(sample_trains, routes, sample_timetable_entries, scheds, [])
        categories = [i.category for i in report.issues]
        assert "invalid_schedule_type" in categories
