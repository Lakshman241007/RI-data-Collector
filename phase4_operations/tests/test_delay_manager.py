"""Tests for operations.delay_manager."""
from __future__ import annotations

import pytest

from operations.delay_manager import (
    _classify_status,
    _add_minutes,
    compute_expected_times,
    build_operation_states,
)
from operations.models import DelayStatus


class TestClassifyStatus:
    def test_on_time(self):
        assert _classify_status(0.0) == DelayStatus.ON_TIME
        assert _classify_status(4.9) == DelayStatus.ON_TIME

    def test_delayed(self):
        assert _classify_status(5.0) == DelayStatus.DELAYED
        assert _classify_status(30.0) == DelayStatus.DELAYED

    def test_early(self):
        assert _classify_status(-3.0) == DelayStatus.EARLY


class TestAddMinutes:
    def test_basic_add(self):
        assert _add_minutes("06:00", 30) == "06:30"

    def test_wraps_midnight(self):
        assert _add_minutes("23:50", 20) == "00:10"

    def test_none_returns_none(self):
        assert _add_minutes(None, 10) is None


class TestComputeExpectedTimes:
    def test_no_delay(self):
        dep, arr = compute_expected_times("08:00", "09:30", 0)
        assert dep == "08:00"
        assert arr == "09:30"

    def test_with_delay(self):
        dep, arr = compute_expected_times("08:00", "09:30", 15)
        assert dep == "08:15"
        assert arr == "09:45"


class TestBuildOperationStates:
    def test_one_state_per_train(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.scheduler import generate_schedules
        schedules = generate_schedules(sample_trains)
        states = build_operation_states(
            [sample_trains[0]], [sample_route],
            sample_timetable_entries, schedules
        )
        assert len(states) == 1

    def test_all_active(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.scheduler import generate_schedules
        schedules = generate_schedules(sample_trains)
        states = build_operation_states(
            [sample_trains[0]], [sample_route],
            sample_timetable_entries, schedules
        )
        assert all(s.is_active for s in states)

    def test_delay_is_zero_initially(self, sample_trains, sample_route, sample_timetable_entries):
        from operations.scheduler import generate_schedules
        schedules = generate_schedules(sample_trains)
        states = build_operation_states(
            [sample_trains[0]], [sample_route],
            sample_timetable_entries, schedules
        )
        assert all(s.delay_minutes == 0.0 for s in states)
