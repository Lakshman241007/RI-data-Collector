"""
operations.statistics
---------------------
Derives summary statistics from the operational dataset.

Metrics generated
~~~~~~~~~~~~~~~~~
* Total train count
* Train type distribution
* Priority distribution
* Average / min / max travel time
* Longest timetable (most stops)
* Platform utilisation
* Schedule type distribution
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Sequence

from operations.models import PlatformAssignment, TimetableEntry, Train, TrainRoute

logger = logging.getLogger(__name__)


def compute_statistics(
    trains: Sequence[Train],
    routes: Sequence[TrainRoute],
    timetable_entries: Sequence[TimetableEntry],
    platform_assignments: Sequence[PlatformAssignment],
    schedules: Sequence[dict],
    platform_count: int = 6,
) -> dict:
    """
    Compute operational statistics.

    Returns
    -------
    dict
        Flat, JSON-serialisable statistics dictionary.
    """
    # Train counts
    total_trains = len(trains)
    type_counts = Counter(t.train_type.value for t in trains)
    priority_counts = Counter(t.priority.value for t in trains)

    # Travel time stats
    travel_times = [r.estimated_travel_time_minutes for r in routes]
    avg_travel = round(sum(travel_times) / len(travel_times), 2) if travel_times else 0.0
    min_travel = round(min(travel_times), 2) if travel_times else 0.0
    max_travel = round(max(travel_times), 2) if travel_times else 0.0

    # Distance stats (km)
    distances = [r.distance_km for r in routes]
    avg_distance = round(sum(distances) / len(distances), 3) if distances else 0.0
    total_distance = round(sum(distances), 3)

    # Longest timetable: train with the most timetable entries
    tte_per_train: Counter = Counter(e.train_id for e in timetable_entries)
    if tte_per_train:
        longest_train_id, longest_stops = tte_per_train.most_common(1)[0]
    else:
        longest_train_id, longest_stops = "N/A", 0

    # Platform utilisation
    platform_hits = Counter(pa.platform_number for pa in platform_assignments)
    platform_utilisation = {
        str(p): platform_hits.get(p, 0)
        for p in range(1, platform_count + 1)
    }
    total_platform_uses = sum(platform_utilisation.values())

    # Schedule type distribution
    schedule_counts = Counter(s.get("schedule_type") for s in schedules)

    stats = {
        "total_trains": total_trains,
        "train_type_counts": dict(type_counts),
        "priority_distribution": dict(priority_counts),
        "travel_time_minutes": {
            "average": avg_travel,
            "minimum": min_travel,
            "maximum": max_travel,
        },
        "distance_km": {
            "average": avg_distance,
            "total": total_distance,
        },
        "timetable": {
            "total_entries": len(timetable_entries),
            "longest_train_id": longest_train_id,
            "longest_train_stops": longest_stops,
        },
        "platform_utilisation": platform_utilisation,
        "total_platform_uses": total_platform_uses,
        "schedule_type_distribution": dict(schedule_counts),
    }

    logger.info("Statistics computed for %d trains.", total_trains)
    return stats
