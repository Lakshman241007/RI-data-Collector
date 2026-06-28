"""Tests for operations.priority_manager."""
from __future__ import annotations

from operations.priority_manager import (
    build_priority_index,
    sorted_by_priority,
    priority_distribution,
)
from operations.models import PriorityLevel


class TestBuildPriorityIndex:
    def test_all_trains_indexed(self, sample_trains):
        index = build_priority_index(sample_trains)
        total = sum(len(v) for v in index.values())
        assert total == len(sample_trains)

    def test_keys_are_priority_values(self, sample_trains):
        valid = {p.value for p in PriorityLevel}
        index = build_priority_index(sample_trains)
        for k in index:
            assert k in valid


class TestSortedByPriority:
    def test_emergency_first(self, sample_trains):
        from operations.models import PriorityLevel, TrainType
        from operations.train_loader import load_trains
        trains = load_trains([f"r{i}" for i in range(10)], 10)
        ordered = sorted_by_priority(trains)
        # Emergency train should be at the front
        emergency = [t for t in ordered if t.priority == PriorityLevel.EMERGENCY]
        others = [t for t in ordered if t.priority != PriorityLevel.EMERGENCY]
        if emergency:
            assert ordered.index(emergency[0]) < ordered.index(others[0])

    def test_returns_all_trains(self, sample_trains):
        ordered = sorted_by_priority(sample_trains)
        assert len(ordered) == len(sample_trains)


class TestPriorityDistribution:
    def test_sums_to_total(self, sample_trains):
        dist = priority_distribution(sample_trains)
        assert sum(dist.values()) == len(sample_trains)
