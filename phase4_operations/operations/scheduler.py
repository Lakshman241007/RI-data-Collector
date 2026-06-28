"""
operations.scheduler
--------------------
Generates train schedules from the loaded train catalogue.

Responsibilities
~~~~~~~~~~~~~~~~
* Map every train to a :class:`~operations.models.ScheduleType` based on
  its train type and index.
* Produce an ordered list of ``(train_id, schedule_type)`` records.
* Support Daily / Weekdays / Weekends × Express / Passenger / Freight.
* Return an immutable tuple of plain dicts (lightweight schedule records).
"""

from __future__ import annotations

import logging
from typing import Sequence

from operations.models import ScheduleType, Train, TrainType

logger = logging.getLogger(__name__)

# Deterministic schedule assignment matrix
_SCHEDULE_MATRIX: dict[TrainType, tuple[ScheduleType, ...]] = {
    TrainType.EXPRESS: (ScheduleType.DAILY, ScheduleType.WEEKDAYS, ScheduleType.DAILY),
    TrainType.PASSENGER: (ScheduleType.DAILY, ScheduleType.WEEKDAYS, ScheduleType.WEEKENDS),
    TrainType.FREIGHT: (ScheduleType.WEEKDAYS, ScheduleType.DAILY, ScheduleType.WEEKDAYS),
}


def _assign_schedule(train: Train, index: int) -> ScheduleType:
    """Deterministically pick a ScheduleType for a given train."""
    cycle = _SCHEDULE_MATRIX[train.train_type]
    return cycle[index % len(cycle)]


def generate_schedules(trains: Sequence[Train]) -> tuple[dict, ...]:
    """
    Produce a schedule record for every train.

    Parameters
    ----------
    trains:
        Full catalogue of :class:`~operations.models.Train` objects.

    Returns
    -------
    tuple[dict, ...]
        Immutable sequence of schedule dicts with keys:
        ``schedule_id``, ``train_id``, ``train_number``, ``train_type``,
        ``schedule_type``, ``priority``.
    """
    schedules: list[dict] = []

    for idx, train in enumerate(trains):
        schedule_type = _assign_schedule(train, idx)
        schedules.append(
            {
                "schedule_id": f"sched_{idx + 1:05d}",
                "train_id": train.train_id,
                "train_number": train.train_number,
                "train_type": train.train_type.value,
                "schedule_type": schedule_type.value,
                "priority": train.priority.value,
            }
        )

    logger.info("Generated %d train schedules.", len(schedules))
    return tuple(schedules)
