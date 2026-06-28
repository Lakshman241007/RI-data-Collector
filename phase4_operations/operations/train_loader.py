"""
operations.train_loader
-----------------------
Generates and validates Train definitions from configuration.

Responsibilities
~~~~~~~~~~~~~~~~
* Produce a deterministic catalogue of trains seeded from ``routes.json``
  (one train per successful route, capped at ``train_count`` in settings).
* Assign unique, human-readable IDs and train numbers.
* Validate that no duplicate train numbers exist.
* Return an immutable tuple of :class:`~operations.models.Train` objects.
"""

from __future__ import annotations

import logging
from typing import Sequence

from operations.models import PriorityLevel, Train, TrainType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal lookup tables (deterministic, no global mutable state)
# ---------------------------------------------------------------------------

_TRAIN_TYPE_CYCLE: tuple[TrainType, ...] = (
    TrainType.EXPRESS,
    TrainType.PASSENGER,
    TrainType.PASSENGER,
    TrainType.FREIGHT,
    TrainType.EXPRESS,
)

_PRIORITY_MAP: dict[TrainType, PriorityLevel] = {
    TrainType.EXPRESS: PriorityLevel.HIGH,
    TrainType.PASSENGER: PriorityLevel.MEDIUM,
    TrainType.FREIGHT: PriorityLevel.FREIGHT,
}

_SPEED_MAP: dict[TrainType, float] = {
    TrainType.EXPRESS: 110.0,
    TrainType.PASSENGER: 70.0,
    TrainType.FREIGHT: 45.0,
}

_COACHES_MAP: dict[TrainType, int] = {
    TrainType.EXPRESS: 18,
    TrainType.PASSENGER: 14,
    TrainType.FREIGHT: 30,
}

_CAPACITY_MAP: dict[TrainType, int] = {
    TrainType.EXPRESS: 1260,
    TrainType.PASSENGER: 980,
    TrainType.FREIGHT: 0,
}

_NAME_PREFIXES: dict[TrainType, tuple[str, ...]] = {
    TrainType.EXPRESS: (
        "Shatabdi", "Rajdhani", "Duronto", "Vande Bharat", "Tejas",
        "Gatimaan", "Humsafar", "Antyodaya", "Kavi Guru", "Mahamana",
    ),
    TrainType.PASSENGER: (
        "Jan Shatabdi", "Intercity", "Sampark Kranti", "Garib Rath",
        "Namma Train", "Uday", "Amrit Bharat", "Demu", "Memu", "Superfast",
    ),
    TrainType.FREIGHT: (
        "Goods", "Container", "Coal", "Cement", "Steel",
        "Ore", "Auto Carrier", "Tank", "Parcel", "Double Stack",
    ),
}


def _train_name(train_type: TrainType, sequence: int) -> str:
    prefixes = _NAME_PREFIXES[train_type]
    prefix = prefixes[sequence % len(prefixes)]
    suffix_num = (sequence // len(prefixes)) + 1
    return f"{prefix} Express" if train_type == TrainType.EXPRESS else (
        f"{prefix} Special" if train_type == TrainType.PASSENGER else
        f"TN {prefix} Freight {suffix_num:02d}"
    )


def load_trains(route_ids: Sequence[str], count: int) -> tuple[Train, ...]:
    """
    Build *count* unique :class:`~operations.models.Train` objects.

    Parameters
    ----------
    route_ids:
        Ordered list of successful Phase 3 route IDs – used only for
        deterministic sequencing.
    count:
        Maximum number of trains to create (capped at ``len(route_ids)``).

    Returns
    -------
    tuple[Train, ...]
        Immutable sequence of validated Train objects.

    Raises
    ------
    ValueError
        If duplicate train numbers are detected.
    """
    actual = min(count, len(route_ids))
    logger.info("Loading %d trains from %d available routes.", actual, len(route_ids))

    trains: list[Train] = []
    seen_numbers: set[str] = set()

    for i in range(actual):
        train_type = _TRAIN_TYPE_CYCLE[i % len(_TRAIN_TYPE_CYCLE)]

        # Train number: type prefix + zero-padded index
        prefix = {"Express": "EX", "Passenger": "PA", "Freight": "FR"}[train_type.value]
        train_number = f"TN-{prefix}-{i + 1:04d}"

        if train_number in seen_numbers:
            raise ValueError(f"Duplicate train number detected: {train_number}")
        seen_numbers.add(train_number)

        # Emergency override for every 10th train
        priority = PriorityLevel.EMERGENCY if (i % 10 == 9) else _PRIORITY_MAP[train_type]

        train = Train(
            train_id=f"train_{i + 1:05d}",
            train_number=train_number,
            name=_train_name(train_type, i),
            train_type=train_type,
            priority=priority,
            max_speed_kmh=_SPEED_MAP[train_type],
            coaches=_COACHES_MAP[train_type],
            capacity=_CAPACITY_MAP[train_type],
        )
        trains.append(train)

    _validate_uniqueness(trains)
    logger.info("Loaded %d trains successfully.", len(trains))
    return tuple(trains)


def _validate_uniqueness(trains: list[Train]) -> None:
    """Raise ValueError on any duplicate train_id or train_number."""
    ids: list[str] = [t.train_id for t in trains]
    numbers: list[str] = [t.train_number for t in trains]

    dup_ids = {x for x in ids if ids.count(x) > 1}
    dup_nums = {x for x in numbers if numbers.count(x) > 1}

    if dup_ids:
        raise ValueError(f"Duplicate train IDs: {dup_ids}")
    if dup_nums:
        raise ValueError(f"Duplicate train numbers: {dup_nums}")
