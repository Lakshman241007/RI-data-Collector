"""
operations.route_assigner
-------------------------
Assigns every train to a valid Phase 3 route and computes derived metrics.

Responsibilities
~~~~~~~~~~~~~~~~
* Load the Phase 3 ``routes.json`` artefact.
* Filter for successful routes only.
* Assign one route per train (round-robin over the available pool).
* Compute distance_km and estimated_travel_time_minutes.
* Return both a flat tuple of :class:`~operations.models.TrainRoute` and
  a tuple of lightweight :class:`~operations.models.RouteAssignment`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Sequence

from operations.models import RouteAssignment, Train, TrainRoute

logger = logging.getLogger(__name__)

_METRES_PER_KM = 1000.0


def _load_successful_routes(routes_path: Path) -> list[dict]:
    """Read routes.json and return only successful route dicts."""
    with routes_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    routes = data.get("routes", [])
    successful = [r for r in routes if r.get("success", False)]
    logger.info(
        "Loaded %d routes (%d successful) from %s.",
        len(routes),
        len(successful),
        routes_path,
    )
    return successful


def _travel_time_minutes(distance_km: float, speed_kmh: float) -> float:
    """Estimate travel time; guard against zero speed."""
    if speed_kmh <= 0:
        return 0.0
    return (distance_km / speed_kmh) * 60.0


def assign_routes(
    trains: Sequence[Train],
    routes_path: Path,
) -> tuple[tuple[TrainRoute, ...], tuple[RouteAssignment, ...]]:
    """
    Assign one Phase 3 route to each train.

    Parameters
    ----------
    trains:
        Sequence of :class:`~operations.models.Train` objects.
    routes_path:
        Path to Phase 3 ``routes.json``.

    Returns
    -------
    (train_routes, route_assignments):
        * ``train_routes``  – full route metadata per train
        * ``route_assignments`` – lightweight mapping for downstream modules
    """
    successful = _load_successful_routes(routes_path)
    if not successful:
        raise RuntimeError("No successful routes found in routes.json.")

    train_routes: list[TrainRoute] = []
    route_assignments: list[RouteAssignment] = []

    for idx, train in enumerate(trains):
        raw = successful[idx % len(successful)]

        distance_m: float = raw.get("distance_m", 0.0)
        distance_km = distance_m / _METRES_PER_KM
        travel_time = _travel_time_minutes(distance_km, train.max_speed_kmh)

        assignment_id = f"ra_{idx + 1:05d}"

        tr = TrainRoute(
            assignment_id=assignment_id,
            train_id=train.train_id,
            route_id=raw["route_id"],
            source_id=raw["source_id"],
            target_id=raw["target_id"],
            station_ids=tuple(raw.get("station_ids", [])),
            station_names=tuple(raw.get("station_names", [])),
            distance_m=distance_m,
            distance_km=round(distance_km, 3),
            estimated_travel_time_minutes=round(travel_time, 2),
            algorithm=raw.get("algorithm", "unknown"),
            node_count=raw.get("node_count", 0),
            edge_count=raw.get("edge_count", 0),
        )
        train_routes.append(tr)

        ra = RouteAssignment(
            assignment_id=assignment_id,
            train_id=train.train_id,
            route_id=raw["route_id"],
            distance_km=tr.distance_km,
            estimated_travel_time_minutes=tr.estimated_travel_time_minutes,
        )
        route_assignments.append(ra)

    logger.info("Assigned routes to %d trains.", len(train_routes))
    return tuple(train_routes), tuple(route_assignments)
