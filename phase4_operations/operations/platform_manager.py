"""
operations.platform_manager
---------------------------
Assigns platforms to trains and detects scheduling conflicts.

Responsibilities
~~~~~~~~~~~~~~~~
* Accept timetable entries and a platform count.
* Produce one :class:`~operations.models.PlatformAssignment` per timetable entry.
* Detect platform conflicts: same station, same platform, overlapping times.
* Return assignments and a list of conflict descriptions.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from operations.models import PlatformAssignment, TimetableEntry

logger = logging.getLogger(__name__)


def _time_to_minutes(t: Optional[str]) -> Optional[int]:
    if t is None:
        return None
    hh, mm = map(int, t.split(":"))
    return hh * 60 + mm


def _times_overlap(
    arr1: Optional[int],
    dep1: Optional[int],
    arr2: Optional[int],
    dep2: Optional[int],
) -> bool:
    """Return True if two (arrival, departure) windows overlap."""
    start1 = arr1 if arr1 is not None else dep1
    end1 = dep1 if dep1 is not None else arr1
    start2 = arr2 if arr2 is not None else dep2
    end2 = dep2 if dep2 is not None else arr2

    if None in (start1, end1, start2, end2):
        return False
    # Overlap when one interval starts before the other ends
    return not (end1 <= start2 or end2 <= start1)  # type: ignore[operator]


def assign_platforms(
    timetable_entries: Sequence[TimetableEntry],
    platform_count: int = 6,
) -> tuple[tuple[PlatformAssignment, ...], list[str]]:
    """
    Assign platform slots and detect conflicts.

    Parameters
    ----------
    timetable_entries:
        All timetable entries across all trains.
    platform_count:
        Total number of platforms available at each station.

    Returns
    -------
    (assignments, conflicts):
        * ``assignments`` – immutable sequence of PlatformAssignment
        * ``conflicts``   – list of human-readable conflict messages
    """
    assignments: list[PlatformAssignment] = []
    # station_id -> list of (platform_number, arrival_minutes, departure_minutes, train_id)
    occupancy: dict[str, list[tuple[int, Optional[int], Optional[int], str]]] = {}

    conflicts: list[str] = []

    for idx, entry in enumerate(timetable_entries):
        platform = entry.platform
        arr_min = _time_to_minutes(entry.arrival_time)
        dep_min = _time_to_minutes(entry.departure_time)

        station_slots = occupancy.setdefault(entry.station_id, [])

        # Conflict detection
        for (occ_plat, occ_arr, occ_dep, occ_train) in station_slots:
            if occ_plat == platform and _times_overlap(arr_min, dep_min, occ_arr, occ_dep):
                msg = (
                    f"Platform conflict at station {entry.station_name!r}: "
                    f"platform {platform}, trains {occ_train} and {entry.train_id}"
                )
                conflicts.append(msg)
                logger.warning(msg)

        station_slots.append((platform, arr_min, dep_min, entry.train_id))

        pa = PlatformAssignment(
            assignment_id=f"pa_{idx + 1:06d}",
            train_id=entry.train_id,
            station_id=entry.station_id,
            station_name=entry.station_name,
            platform_number=platform,
            arrival_time=entry.arrival_time,
            departure_time=entry.departure_time,
        )
        assignments.append(pa)

    logger.info(
        "Platform assignment complete: %d assignments, %d conflicts.",
        len(assignments),
        len(conflicts),
    )
    return tuple(assignments), conflicts


def platform_utilization(
    assignments: Sequence[PlatformAssignment],
    platform_count: int = 6,
) -> dict[int, int]:
    """Count how many times each platform number is used across all stations."""
    util: dict[int, int] = {p: 0 for p in range(1, platform_count + 1)}
    for pa in assignments:
        util[pa.platform_number] = util.get(pa.platform_number, 0) + 1
    return util
