"""
operations.timetable_loader
---------------------------
Creates :class:`~operations.models.TimetableEntry` objects for every train.

Responsibilities
~~~~~~~~~~~~~~~~
* For each train / route assignment produce one TimetableEntry per stop.
* Compute arrival and departure times incrementally from a base departure.
* Record platform, halt duration, and stop sequence.
* Return an immutable tuple of entries.
"""

from __future__ import annotations

import logging
from typing import Sequence

from operations.models import TimetableEntry, Train, TrainRoute

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Halt duration by train type (minutes)
# ---------------------------------------------------------------------------

_HALT_MINUTES: dict[str, int] = {
    "Express": 5,
    "Passenger": 10,
    "Freight": 15,
}


def _format_time(total_minutes: int) -> str:
    """Convert total elapsed minutes to HH:MM string (wraps at 24 h)."""
    total_minutes = total_minutes % (24 * 60)
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


def _travel_minutes_per_segment(train_route: TrainRoute, speed_kmh: float) -> float:
    """Travel time for a single inter-station segment."""
    if train_route.edge_count == 0:
        return 0.0
    segment_km = train_route.distance_km / max(train_route.edge_count, 1)
    return (segment_km / speed_kmh) * 60.0


def create_timetables(
    trains: Sequence[Train],
    route_assignments: Sequence[TrainRoute],
    base_departure_hour: int = 5,
    schedule_gap_minutes: int = 20,
) -> tuple[TimetableEntry, ...]:
    """
    Build a timetable for every train.

    Parameters
    ----------
    trains:
        Ordered sequence of Train objects.
    route_assignments:
        One TrainRoute per train (same order as *trains*).
    base_departure_hour:
        Hour (0-23) at which the first train departs.
    schedule_gap_minutes:
        Minutes between successive trains' departure times.

    Returns
    -------
    tuple[TimetableEntry, ...]
        Flat immutable sequence of all timetable entries.
    """
    train_by_id: dict[str, Train] = {t.train_id: t for t in trains}
    route_by_train: dict[str, TrainRoute] = {r.train_id: r for r in route_assignments}

    all_entries: list[TimetableEntry] = []
    entry_counter = 0

    for train_index, train in enumerate(trains):
        route = route_by_train.get(train.train_id)
        if route is None:
            logger.warning("No route found for train %s – skipping timetable.", train.train_id)
            continue

        halt = _HALT_MINUTES.get(train.train_type.value, 10)
        travel_per_seg = _travel_minutes_per_segment(route, train.max_speed_kmh)

        # Base departure offset for this train
        base_minutes = base_departure_hour * 60 + train_index * schedule_gap_minutes
        current_minutes = base_minutes

        stations = list(zip(route.station_ids, route.station_names))
        total_stops = len(stations)

        for seq, (station_id, station_name) in enumerate(stations):
            is_origin = seq == 0
            is_terminus = seq == total_stops - 1

            arrival_time: str | None
            departure_time: str | None

            if is_origin:
                arrival_time = None
                departure_time = _format_time(current_minutes)
            elif is_terminus:
                current_minutes += int(travel_per_seg)
                arrival_time = _format_time(current_minutes)
                departure_time = None
            else:
                current_minutes += int(travel_per_seg)
                arrival_time = _format_time(current_minutes)
                current_minutes += halt
                departure_time = _format_time(current_minutes)

            platform = (train_index + seq) % 6 + 1  # platforms 1-6

            entry_counter += 1
            entry = TimetableEntry(
                entry_id=f"tte_{entry_counter:06d}",
                train_id=train.train_id,
                station_id=station_id,
                station_name=station_name,
                arrival_time=arrival_time,
                departure_time=departure_time,
                platform=platform,
                halt_duration_minutes=0 if is_origin or is_terminus else halt,
                stop_sequence=seq,
            )
            all_entries.append(entry)

    logger.info("Created %d timetable entries for %d trains.", len(all_entries), len(trains))
    return tuple(all_entries)
