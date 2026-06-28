"""
operations.delay_manager
------------------------
Maintains delay state for each train.

Responsibilities
~~~~~~~~~~~~~~~~
* Compute expected arrival / departure times given a base timetable entry
  and a delay in minutes.
* Determine :class:`~operations.models.DelayStatus` from delay minutes.
* Return an immutable tuple of :class:`~operations.models.OperationState`.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from operations.models import (
    DelayStatus,
    OperationState,
    ScheduleType,
    TimetableEntry,
    Train,
    TrainRoute,
)

logger = logging.getLogger(__name__)

_DELAY_THRESHOLD_MINUTES = 5.0   # below this → On Time
_EARLY_THRESHOLD_MINUTES = -2.0  # below zero → Early


def _classify_status(delay_minutes: float) -> DelayStatus:
    if delay_minutes <= _EARLY_THRESHOLD_MINUTES:
        return DelayStatus.EARLY
    if delay_minutes < _DELAY_THRESHOLD_MINUTES:
        return DelayStatus.ON_TIME
    return DelayStatus.DELAYED


def _add_minutes(time_str: Optional[str], delta: float) -> Optional[str]:
    """Add *delta* minutes to an HH:MM string; return None if input is None."""
    if time_str is None:
        return None
    hh, mm = map(int, time_str.split(":"))
    total = hh * 60 + mm + int(delta)
    total = total % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def build_operation_states(
    trains: Sequence[Train],
    route_assignments: Sequence[TrainRoute],
    timetable_entries: Sequence[TimetableEntry],
    schedules: Sequence[dict],
) -> tuple[OperationState, ...]:
    """
    Build one :class:`~operations.models.OperationState` per train.

    Initial delay is 0 for all trains (simulation-ready baseline state).

    Parameters
    ----------
    trains:
        Full train catalogue.
    route_assignments:
        One TrainRoute per train.
    timetable_entries:
        All timetable entries (for deriving current/next station).
    schedules:
        Schedule records from :mod:`operations.scheduler`.

    Returns
    -------
    tuple[OperationState, ...]
    """
    # Index timetable entries by train_id
    tte_by_train: dict[str, list[TimetableEntry]] = {}
    for entry in timetable_entries:
        tte_by_train.setdefault(entry.train_id, []).append(entry)
    for entries in tte_by_train.values():
        entries.sort(key=lambda e: e.stop_sequence)

    route_by_train: dict[str, TrainRoute] = {r.train_id: r for r in route_assignments}
    schedule_by_train: dict[str, dict] = {s["train_id"]: s for s in schedules}

    states: list[OperationState] = []

    for idx, train in enumerate(trains):
        delay_minutes = 0.0
        status = DelayStatus.ON_TIME

        entries = tte_by_train.get(train.train_id, [])
        current_station = entries[0].station_id if entries else None
        next_station = entries[1].station_id if len(entries) > 1 else None

        sched = schedule_by_train.get(train.train_id, {})
        raw_stype = sched.get("schedule_type", "Daily")
        schedule_type = ScheduleType(raw_stype) if raw_stype in ScheduleType._value2member_map_ else ScheduleType.DAILY

        state = OperationState(
            state_id=f"ops_{idx + 1:05d}",
            train_id=train.train_id,
            schedule_type=schedule_type,
            is_active=True,
            current_station_id=current_station,
            next_station_id=next_station,
            delay_minutes=delay_minutes,
            status=status,
        )
        states.append(state)

    logger.info("Built %d operation states.", len(states))
    return tuple(states)


def compute_expected_times(
    departure_time: Optional[str],
    arrival_time: Optional[str],
    delay_minutes: float,
) -> tuple[Optional[str], Optional[str]]:
    """
    Adjust raw timetable times by *delay_minutes*.

    Returns
    -------
    (expected_departure, expected_arrival)
    """
    return (
        _add_minutes(departure_time, delay_minutes),
        _add_minutes(arrival_time, delay_minutes),
    )
