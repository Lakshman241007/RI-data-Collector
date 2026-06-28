"""
routing.exporter
------------------
JSON export helpers for the three Phase 3.1 output artifacts:
``routes.json``, ``statistics.json``, ``validation.json``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from routing.models import RouteResult
from routing.statistics import RouteStatistics
from routing.validator import ValidationReport

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _route_to_dict(route: RouteResult) -> dict:
    d = asdict(route)
    d["algorithm"] = route.algorithm.value
    return d


def export_routes(routes: list[RouteResult], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": _now_iso(),
        "route_count": len(routes),
        "routes": [_route_to_dict(r) for r in routes],
    }

    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    logger.info("Exported %d routes to %s", len(routes), path)


def export_statistics(stats: RouteStatistics, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"generated_at": _now_iso(), **stats.as_dict()}

    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    logger.info("Exported statistics to %s", path)


def export_validation(report: ValidationReport, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"generated_at": _now_iso(), **report.as_dict()}

    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    logger.info("Exported validation report to %s", path)
