"""
routing.statistics
--------------------
Computes aggregate statistics over the built routes: average/longest/
shortest route, and per-algorithm routing timings. Exported as
``statistics.json``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

from routing.models import AlgorithmType, RouteResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AlgorithmTiming:
    algorithm: str
    route_count: int = 0
    success_count: int = 0
    total_time_ms: float = 0.0
    average_time_ms: float = 0.0
    min_time_ms: float = 0.0
    max_time_ms: float = 0.0


@dataclass(slots=True)
class RouteStatistics:
    total_routes: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    average_route_length_m: float = 0.0
    average_node_count: float = 0.0
    longest_route: dict | None = None
    shortest_route: dict | None = None
    timings_by_algorithm: dict[str, AlgorithmTiming] = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["timings_by_algorithm"] = {
            name: asdict(timing) for name, timing in self.timings_by_algorithm.items()
        }
        return d


def _route_summary(route: RouteResult) -> dict:
    return {
        "route_id": route.route_id,
        "algorithm": route.algorithm.value,
        "source_id": route.source_id,
        "target_id": route.target_id,
        "distance_m": route.distance_m,
        "node_count": route.node_count,
        "edge_count": route.edge_count,
    }


def compute_route_statistics(routes: list[RouteResult]) -> RouteStatistics:
    """Compute the full ``RouteStatistics`` summary for ``routes``."""
    stats = RouteStatistics(total_routes=len(routes))

    successful = [r for r in routes if r.success]
    stats.successful_routes = len(successful)
    stats.failed_routes = stats.total_routes - stats.successful_routes

    if successful:
        stats.average_route_length_m = round(
            sum(r.distance_m for r in successful) / len(successful), 2
        )
        stats.average_node_count = round(
            sum(r.node_count for r in successful) / len(successful), 2
        )

        longest = max(successful, key=lambda r: r.distance_m)
        shortest = min(successful, key=lambda r: r.distance_m)
        stats.longest_route = _route_summary(longest)
        stats.shortest_route = _route_summary(shortest)

    # -- Per-algorithm timings (computed across *all* attempts, success or not) --
    by_algorithm: dict[AlgorithmType, list[RouteResult]] = {}
    for route in routes:
        by_algorithm.setdefault(route.algorithm, []).append(route)

    timings: dict[str, AlgorithmTiming] = {}
    for algorithm, algo_routes in by_algorithm.items():
        times = [r.computation_time_ms for r in algo_routes]
        timing = AlgorithmTiming(
            algorithm=algorithm.value,
            route_count=len(algo_routes),
            success_count=sum(1 for r in algo_routes if r.success),
            total_time_ms=round(sum(times), 4),
            average_time_ms=round(sum(times) / len(times), 4) if times else 0.0,
            min_time_ms=round(min(times), 4) if times else 0.0,
            max_time_ms=round(max(times), 4) if times else 0.0,
        )
        timings[algorithm.value] = timing

    stats.timings_by_algorithm = timings

    logger.info(
        "Statistics — total=%d successful=%d failed=%d avg_length_m=%.1f",
        stats.total_routes,
        stats.successful_routes,
        stats.failed_routes,
        stats.average_route_length_m,
    )

    return stats
