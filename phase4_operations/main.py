"""
main.py – Phase 4 Railway Operations Engine
============================================
Orchestrates the full pipeline:

  1. Load configuration
  2. Load Phase 3 routes
  3. Load / validate trains
  4. Assign routes
  5. Generate timetables
  6. Generate schedules
  7. Assign platforms & detect conflicts
  8. Build operation states
  9. Compute statistics
  10. Validate everything
  11. Export all artefacts

Usage
-----
  python main.py

Outputs (in output/)
---------------------
  trains.json, timetables.json, operations.json,
  statistics.json, validation.json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap logging before importing project modules
# ---------------------------------------------------------------------------

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "phase4_operations.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Project imports (after logging is configured)
# ---------------------------------------------------------------------------

from operations.delay_manager import build_operation_states
from operations.exporter import (
    export_operations,
    export_statistics,
    export_timetables,
    export_trains,
    export_validation,
)
from operations.operations_validator import validate_all
from operations.platform_manager import assign_platforms, platform_utilization
from operations.priority_manager import build_priority_index
from operations.route_assigner import assign_routes
from operations.scheduler import generate_schedules
from operations.statistics import compute_statistics
from operations.timetable_loader import create_timetables
from operations.train_loader import load_trains


def _load_config(config_path: Path) -> dict:
    with config_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_route_ids(routes_path: Path) -> list[str]:
    with routes_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return [
        r["route_id"]
        for r in data.get("routes", [])
        if r.get("success", False)
    ]


def main() -> int:
    logger.info("=" * 60)
    logger.info("Phase 4 – Railway Operations Engine")
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 1. Configuration
    # ------------------------------------------------------------------
    config_path = Path("config/operations_settings.json")
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1

    cfg = _load_config(config_path)
    logger.info("Configuration loaded from %s", config_path)

    routes_path = Path(cfg["routes_input"])
    output_dir = Path(cfg["output_dir"])
    train_count: int = cfg["train_count"]
    base_dep_hour: int = cfg["base_departure_hour"]
    schedule_gap: int = cfg["schedule_gap_minutes"]
    platform_count: int = cfg["platform_count"]

    output_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # 2. Load Phase 3 route IDs
    # ------------------------------------------------------------------
    route_ids = _load_route_ids(routes_path)
    logger.info("Found %d successful Phase 3 routes.", len(route_ids))

    # ------------------------------------------------------------------
    # 3. Load trains
    # ------------------------------------------------------------------
    trains = load_trains(route_ids, train_count)
    logger.info("Trains loaded: %d", len(trains))

    # ------------------------------------------------------------------
    # 4. Assign routes
    # ------------------------------------------------------------------
    train_routes, route_assignments = assign_routes(trains, routes_path)

    # ------------------------------------------------------------------
    # 5. Generate timetables
    # ------------------------------------------------------------------
    timetable_entries = create_timetables(
        trains, train_routes,
        base_departure_hour=base_dep_hour,
        schedule_gap_minutes=schedule_gap,
    )

    # ------------------------------------------------------------------
    # 6. Generate schedules
    # ------------------------------------------------------------------
    schedules = generate_schedules(trains)

    # ------------------------------------------------------------------
    # 7. Assign platforms & detect conflicts
    # ------------------------------------------------------------------
    platform_assignments, platform_conflicts = assign_platforms(
        timetable_entries, platform_count=platform_count
    )

    # ------------------------------------------------------------------
    # 8. Build operation states
    # ------------------------------------------------------------------
    op_states = build_operation_states(
        trains, train_routes, timetable_entries, schedules
    )

    # ------------------------------------------------------------------
    # 9. Priority index (logged; not exported separately)
    # ------------------------------------------------------------------
    priority_index = build_priority_index(trains)
    logger.info("Priority index: %s", {k: len(v) for k, v in priority_index.items()})

    # ------------------------------------------------------------------
    # 10. Compute statistics
    # ------------------------------------------------------------------
    stats = compute_statistics(
        trains, train_routes, timetable_entries,
        platform_assignments, schedules, platform_count,
    )

    # ------------------------------------------------------------------
    # 11. Validate
    # ------------------------------------------------------------------
    validation_report = validate_all(
        trains, train_routes, timetable_entries, schedules, platform_conflicts
    )

    # ------------------------------------------------------------------
    # 12. Export all artefacts
    # ------------------------------------------------------------------
    export_trains(trains, output_dir)
    export_timetables(timetable_entries, output_dir)
    export_operations(train_routes, op_states, platform_assignments, schedules, output_dir)
    export_statistics(stats, output_dir)
    export_validation(validation_report, output_dir)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("Phase 4 Operations Engine complete.")
    logger.info("  Trains            : %d", len(trains))
    logger.info("  Timetable entries : %d", len(timetable_entries))
    logger.info("  Route assignments : %d", len(train_routes))
    logger.info("  Platform assigns  : %d", len(platform_assignments))
    logger.info("  Platform conflicts: %d", len(platform_conflicts))
    logger.info("  Validation passed : %s", validation_report.passed)
    logger.info("  Output dir        : %s/", output_dir)
    logger.info("=" * 60)

    return 0 if validation_report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
