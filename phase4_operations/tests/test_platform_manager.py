"""Tests for operations.platform_manager."""
from __future__ import annotations

from operations.platform_manager import assign_platforms, platform_utilization
from operations.models import TimetableEntry


def _make_entry(
    idx: int,
    train_id: str,
    station_id: str,
    station_name: str,
    arrival: str | None,
    departure: str | None,
    platform: int,
    seq: int,
) -> TimetableEntry:
    return TimetableEntry(
        entry_id=f"tte_{idx:06d}",
        train_id=train_id,
        station_id=station_id,
        station_name=station_name,
        arrival_time=arrival,
        departure_time=departure,
        platform=platform,
        halt_duration_minutes=5,
        stop_sequence=seq,
    )


class TestAssignPlatforms:
    def test_one_assignment_per_entry(self, sample_timetable_entries):
        assignments, _ = assign_platforms(sample_timetable_entries, 6)
        assert len(assignments) == len(sample_timetable_entries)

    def test_no_conflict_for_different_platforms(self):
        e1 = _make_entry(1, "t1", "S1", "Station 1", "06:00", "06:10", 1, 0)
        e2 = _make_entry(2, "t2", "S1", "Station 1", "06:00", "06:10", 2, 0)
        _, conflicts = assign_platforms([e1, e2], 6)
        assert len(conflicts) == 0

    def test_conflict_detected_same_platform_same_time(self):
        e1 = _make_entry(1, "t1", "S1", "Station 1", "06:00", "06:30", 1, 0)
        e2 = _make_entry(2, "t2", "S1", "Station 1", "06:10", "06:40", 1, 0)
        _, conflicts = assign_platforms([e1, e2], 6)
        assert len(conflicts) >= 1

    def test_returns_tuple(self, sample_timetable_entries):
        assignments, _ = assign_platforms(sample_timetable_entries, 6)
        assert isinstance(assignments, tuple)


class TestPlatformUtilization:
    def test_all_platforms_present(self, sample_timetable_entries):
        assignments, _ = assign_platforms(sample_timetable_entries, 6)
        util = platform_utilization(assignments, 6)
        assert set(util.keys()) == set(range(1, 7))

    def test_total_matches_assignments(self, sample_timetable_entries):
        assignments, _ = assign_platforms(sample_timetable_entries, 6)
        util = platform_utilization(assignments, 6)
        assert sum(util.values()) == len(assignments)
