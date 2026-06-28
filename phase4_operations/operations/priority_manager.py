"""
operations.priority_manager
---------------------------
Maps trains to priority levels and provides ordering utilities.

Responsibilities
~~~~~~~~~~~~~~~~
* Accept a sequence of :class:`~operations.models.Train` objects.
* Return a priority index: ``{priority_level: [train_ids]}``.
* Provide a sorted list of trains ordered by operational priority.
* Support High / Medium / Low / Emergency / Freight.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Sequence

from operations.models import PriorityLevel, Train

logger = logging.getLogger(__name__)

# Lower number = higher urgency
_PRIORITY_ORDER: dict[PriorityLevel, int] = {
    PriorityLevel.EMERGENCY: 0,
    PriorityLevel.HIGH: 1,
    PriorityLevel.MEDIUM: 2,
    PriorityLevel.FREIGHT: 3,
    PriorityLevel.LOW: 4,
}


def build_priority_index(trains: Sequence[Train]) -> dict[str, list[str]]:
    """
    Build a mapping from priority level name to list of train IDs.

    Parameters
    ----------
    trains:
        Full train catalogue.

    Returns
    -------
    dict[str, list[str]]
        Keys are :class:`~operations.models.PriorityLevel` value strings.
    """
    index: dict[str, list[str]] = defaultdict(list)
    for train in trains:
        index[train.priority.value].append(train.train_id)
    result = dict(index)
    logger.info(
        "Priority index built: %s",
        {k: len(v) for k, v in result.items()},
    )
    return result


def sorted_by_priority(trains: Sequence[Train]) -> tuple[Train, ...]:
    """
    Return trains sorted from highest to lowest priority.

    Emergency < High < Medium < Freight < Low.
    """
    return tuple(
        sorted(trains, key=lambda t: _PRIORITY_ORDER.get(t.priority, 99))
    )


def priority_distribution(trains: Sequence[Train]) -> dict[str, int]:
    """Count of trains per priority level."""
    dist: dict[str, int] = defaultdict(int)
    for train in trains:
        dist[train.priority.value] += 1
    return dict(dist)
