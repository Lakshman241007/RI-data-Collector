"""Tests for operations.timetable_loader."""
from __future__ import annotations

from operations.timetable_loader import create_timetables, _format_time, _travel_minutes_per_segment


class TestFormatTime:
    def test_basic(self):
        assert _format_time(60) == "01:00"
        assert _format_time(90) == "01:30"
        assert _format_time(0) == "00:00"

    def test_wrap_24h(self):
        assert _format_time(24 * 60) == "00:00"
        assert _format_time(25 * 60) == "01:00"


class TestCreateTimetables:
    def test_entry_count(self, sample_trains, sample_route):
        # sample_route has 3 stations; only first train has a route
        routes = [sample_route]
        trains = [sample_trains[0]]
        entries = create_timetables(trains, routes)
        assert len(entries) == 3  # one entry per station

    def test_origin_has_no_arrival(self, sample_trains, sample_route):
        entries = create_timetables([sample_trains[0]], [sample_route])
        origin = next(e for e in entries if e.stop_sequence == 0)
        assert origin.arrival_time is None
        assert origin.departure_time is not None

    def test_terminus_has_no_departure(self, sample_trains, sample_route):
        entries = create_timetables([sample_trains[0]], [sample_route])
        terminus = max(entries, key=lambda e: e.stop_sequence)
        assert terminus.departure_time is None
        assert terminus.arrival_time is not None

    def test_returns_tuple(self, sample_trains, sample_route):
        entries = create_timetables([sample_trains[0]], [sample_route])
        assert isinstance(entries, tuple)

    def test_platforms_in_range(self, sample_trains, sample_route):
        entries = create_timetables([sample_trains[0]], [sample_route])
        for e in entries:
            assert 1 <= e.platform <= 6

    def test_missing_route_skipped(self, sample_trains):
        # provide no routes → no entries
        entries = create_timetables(sample_trains[:1], [])
        assert len(entries) == 0
