"""Tests for operations.train_loader."""
from __future__ import annotations

import pytest

from operations.train_loader import load_trains, _validate_uniqueness
from operations.models import Train, TrainType, PriorityLevel


_FAKE_ROUTE_IDS = [f"route_{i:05d}" for i in range(1, 60)]


class TestLoadTrains:
    def test_returns_requested_count(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 10)
        assert len(trains) == 10

    def test_capped_at_route_count(self):
        trains = load_trains(_FAKE_ROUTE_IDS[:3], 100)
        assert len(trains) == 3

    def test_unique_ids(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 20)
        ids = [t.train_id for t in trains]
        assert len(ids) == len(set(ids))

    def test_unique_numbers(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 20)
        numbers = [t.train_number for t in trains]
        assert len(numbers) == len(set(numbers))

    def test_all_types_present(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 20)
        types = {t.train_type for t in trains}
        assert TrainType.EXPRESS in types
        assert TrainType.PASSENGER in types
        assert TrainType.FREIGHT in types

    def test_emergency_priority_every_tenth(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 10)
        # index 9 (10th) should be EMERGENCY
        assert trains[9].priority == PriorityLevel.EMERGENCY

    def test_returns_tuple(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 5)
        assert isinstance(trains, tuple)

    def test_train_fields_complete(self):
        trains = load_trains(_FAKE_ROUTE_IDS, 1)
        t = trains[0]
        assert t.train_id
        assert t.train_number
        assert t.name
        assert t.max_speed_kmh > 0
        assert t.coaches > 0


class TestValidateUniqueness:
    def test_raises_on_duplicate_id(self):
        t = Train(
            train_id="dup", train_number="X-001",
            name="Test", train_type=TrainType.EXPRESS,
            priority=PriorityLevel.HIGH,
            max_speed_kmh=110, coaches=18, capacity=1260,
        )
        with pytest.raises(ValueError, match="Duplicate train IDs"):
            _validate_uniqueness([t, t])

    def test_passes_unique_trains(self):
        trains = list(load_trains(_FAKE_ROUTE_IDS, 5))
        # Should not raise
        _validate_uniqueness(trains)
