"""Tests for operations.models – dataclass immutability and field completeness."""
from __future__ import annotations

import pytest

from operations.models import (
    DelayStatus,
    OperationState,
    PlatformAssignment,
    PriorityLevel,
    RouteAssignment,
    ScheduleType,
    Train,
    TimetableEntry,
    TrainRoute,
    TrainType,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)


class TestTrainImmutability:
    def test_frozen(self, sample_trains):
        t = sample_trains[0]
        with pytest.raises((AttributeError, TypeError)):
            t.train_id = "mutated"  # type: ignore[misc]


class TestTimetableEntryImmutability:
    def test_frozen(self, sample_timetable_entries):
        e = sample_timetable_entries[0]
        with pytest.raises((AttributeError, TypeError)):
            e.train_id = "mutated"  # type: ignore[misc]


class TestTrainRouteImmutability:
    def test_frozen(self, sample_route):
        with pytest.raises((AttributeError, TypeError)):
            sample_route.route_id = "mutated"  # type: ignore[misc]


class TestEnumValues:
    def test_train_types(self):
        assert TrainType.EXPRESS.value == "Express"
        assert TrainType.PASSENGER.value == "Passenger"
        assert TrainType.FREIGHT.value == "Freight"

    def test_priority_levels(self):
        values = {p.value for p in PriorityLevel}
        assert "Emergency" in values
        assert "High" in values
        assert "Medium" in values
        assert "Low" in values
        assert "Freight" in values

    def test_delay_statuses(self):
        assert DelayStatus.ON_TIME.value == "On Time"
        assert DelayStatus.DELAYED.value == "Delayed"

    def test_schedule_types(self):
        values = {s.value for s in ScheduleType}
        assert {"Daily", "Weekdays", "Weekends"}.issubset(values)


class TestValidationReport:
    def test_default_passed(self):
        r = ValidationReport()
        assert r.passed is True
        assert r.issues == []

    def test_mutable_issues_list(self):
        r = ValidationReport()
        issue = ValidationIssue(
            issue_id="i_00001",
            severity=ValidationSeverity.ERROR,
            category="test",
            message="test message",
        )
        r.issues.append(issue)
        assert len(r.issues) == 1
