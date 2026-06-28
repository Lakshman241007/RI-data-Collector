"""Shared fixtures for Phase 4 tests."""
from __future__ import annotations

import pytest

from operations.models import (
    PriorityLevel,
    Train,
    TrainRoute,
    TrainType,
    TimetableEntry,
)


@pytest.fixture()
def sample_trains() -> list[Train]:
    return [
        Train(
            train_id="train_00001",
            train_number="TN-EX-0001",
            name="Shatabdi Express",
            train_type=TrainType.EXPRESS,
            priority=PriorityLevel.HIGH,
            max_speed_kmh=110.0,
            coaches=18,
            capacity=1260,
        ),
        Train(
            train_id="train_00002",
            train_number="TN-PA-0002",
            name="Jan Shatabdi Special",
            train_type=TrainType.PASSENGER,
            priority=PriorityLevel.MEDIUM,
            max_speed_kmh=70.0,
            coaches=14,
            capacity=980,
        ),
        Train(
            train_id="train_00003",
            train_number="TN-FR-0003",
            name="TN Goods Freight 01",
            train_type=TrainType.FREIGHT,
            priority=PriorityLevel.FREIGHT,
            max_speed_kmh=45.0,
            coaches=30,
            capacity=0,
        ),
    ]


@pytest.fixture()
def sample_route(sample_trains) -> TrainRoute:
    return TrainRoute(
        assignment_id="ra_00001",
        train_id=sample_trains[0].train_id,
        route_id="route_00001",
        source_id="node_A",
        target_id="node_C",
        station_ids=("node_A", "node_B", "node_C"),
        station_names=("Station A", "Station B", "Station C"),
        distance_m=50000.0,
        distance_km=50.0,
        estimated_travel_time_minutes=27.27,
        algorithm="dijkstra",
        node_count=3,
        edge_count=2,
    )


@pytest.fixture()
def sample_timetable_entries(sample_trains) -> list[TimetableEntry]:
    return [
        TimetableEntry(
            entry_id="tte_000001",
            train_id=sample_trains[0].train_id,
            station_id="node_A",
            station_name="Station A",
            arrival_time=None,
            departure_time="06:00",
            platform=1,
            halt_duration_minutes=0,
            stop_sequence=0,
        ),
        TimetableEntry(
            entry_id="tte_000002",
            train_id=sample_trains[0].train_id,
            station_id="node_B",
            station_name="Station B",
            arrival_time="06:30",
            departure_time="06:35",
            platform=2,
            halt_duration_minutes=5,
            stop_sequence=1,
        ),
        TimetableEntry(
            entry_id="tte_000003",
            train_id=sample_trains[0].train_id,
            station_id="node_C",
            station_name="Station C",
            arrival_time="07:00",
            departure_time=None,
            platform=3,
            halt_duration_minutes=0,
            stop_sequence=2,
        ),
    ]
