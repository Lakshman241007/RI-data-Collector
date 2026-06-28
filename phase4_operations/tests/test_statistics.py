"""Tests for operations.statistics."""
from __future__ import annotations

from operations.statistics import compute_statistics


class TestComputeStatistics:
    def test_total_trains_correct(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.platform_manager import assign_platforms
        from operations.scheduler import generate_schedules
        routes = [sample_route]
        trains = [sample_trains[0]]
        scheds = generate_schedules(trains)
        pas, _ = assign_platforms(sample_timetable_entries)
        stats = compute_statistics(trains, routes, sample_timetable_entries, pas, scheds)
        assert stats["total_trains"] == 1

    def test_type_counts_present(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.platform_manager import assign_platforms
        from operations.scheduler import generate_schedules
        routes = [sample_route]
        trains = [sample_trains[0]]
        scheds = generate_schedules(trains)
        pas, _ = assign_platforms(sample_timetable_entries)
        stats = compute_statistics(trains, routes, sample_timetable_entries, pas, scheds)
        assert "train_type_counts" in stats
        assert "Express" in stats["train_type_counts"]

    def test_platform_utilisation_keys(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.platform_manager import assign_platforms
        from operations.scheduler import generate_schedules
        routes = [sample_route]
        trains = [sample_trains[0]]
        scheds = generate_schedules(trains)
        pas, _ = assign_platforms(sample_timetable_entries)
        stats = compute_statistics(trains, routes, sample_timetable_entries, pas, scheds, 6)
        util = stats["platform_utilisation"]
        assert set(util.keys()) == {str(p) for p in range(1, 7)}

    def test_travel_time_structure(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.platform_manager import assign_platforms
        from operations.scheduler import generate_schedules
        routes = [sample_route]
        trains = [sample_trains[0]]
        scheds = generate_schedules(trains)
        pas, _ = assign_platforms(sample_timetable_entries)
        stats = compute_statistics(trains, routes, sample_timetable_entries, pas, scheds)
        tt = stats["travel_time_minutes"]
        assert "average" in tt and "minimum" in tt and "maximum" in tt
