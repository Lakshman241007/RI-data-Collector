"""Tests for operations.scheduler."""
from __future__ import annotations

from operations.scheduler import generate_schedules
from operations.models import ScheduleType


class TestGenerateSchedules:
    def test_count_matches_trains(self, sample_trains):
        schedules = generate_schedules(sample_trains)
        assert len(schedules) == len(sample_trains)

    def test_all_have_required_keys(self, sample_trains):
        schedules = generate_schedules(sample_trains)
        required = {"schedule_id", "train_id", "train_number", "train_type",
                    "schedule_type", "priority"}
        for s in schedules:
            assert required.issubset(s.keys())

    def test_schedule_types_valid(self, sample_trains):
        valid = {st.value for st in ScheduleType}
        schedules = generate_schedules(sample_trains)
        for s in schedules:
            assert s["schedule_type"] in valid

    def test_returns_tuple(self, sample_trains):
        schedules = generate_schedules(sample_trains)
        assert isinstance(schedules, tuple)

    def test_train_ids_match(self, sample_trains):
        schedules = generate_schedules(sample_trains)
        expected_ids = {t.train_id for t in sample_trains}
        actual_ids = {s["train_id"] for s in schedules}
        assert expected_ids == actual_ids
