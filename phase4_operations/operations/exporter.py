"""
operations.exporter
-------------------
Writes all operational artefacts to disk as JSON files.

Outputs
~~~~~~~
* ``trains.json``      – full train catalogue
* ``timetables.json``  – all timetable entries
* ``operations.json``  – operation states + route assignments + schedules
* ``statistics.json``  – aggregated statistics
* ``validation.json``  – validation report

All output is written to the configured output directory.
Phase 3 files are never touched.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from operations.models import (
    OperationState,
    PlatformAssignment,
    TimetableEntry,
    Train,
    TrainRoute,
    ValidationReport,
)

logger = logging.getLogger(__name__)

_INDENT = 2


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=_INDENT, ensure_ascii=False)
    logger.info("Wrote %s (%d bytes)", path, path.stat().st_size)


# ---------------------------------------------------------------------------
# Individual serialisers
# ---------------------------------------------------------------------------


def _serialise_train(train: Train) -> dict:
    d = asdict(train)
    d["train_type"] = train.train_type.value
    d["priority"] = train.priority.value
    return d


def _serialise_tte(entry: TimetableEntry) -> dict:
    return asdict(entry)


def _serialise_train_route(tr: TrainRoute) -> dict:
    d = asdict(tr)
    d["station_ids"] = list(tr.station_ids)
    d["station_names"] = list(tr.station_names)
    return d


def _serialise_op_state(state: OperationState) -> dict:
    d = asdict(state)
    d["schedule_type"] = state.schedule_type.value
    d["status"] = state.status.value
    return d


def _serialise_platform(pa: PlatformAssignment) -> dict:
    return asdict(pa)


# ---------------------------------------------------------------------------
# Public export functions
# ---------------------------------------------------------------------------


def export_trains(trains: Sequence[Train], output_dir: Path) -> None:
    """Write trains.json."""
    payload = {
        "generated_at": _now_iso(),
        "train_count": len(trains),
        "trains": [_serialise_train(t) for t in trains],
    }
    _write(output_dir / "trains.json", payload)


def export_timetables(
    entries: Sequence[TimetableEntry],
    output_dir: Path,
) -> None:
    """Write timetables.json."""
    payload = {
        "generated_at": _now_iso(),
        "entry_count": len(entries),
        "timetables": [_serialise_tte(e) for e in entries],
    }
    _write(output_dir / "timetables.json", payload)


def export_operations(
    train_routes: Sequence[TrainRoute],
    op_states: Sequence[OperationState],
    platform_assignments: Sequence[PlatformAssignment],
    schedules: Sequence[dict],
    output_dir: Path,
) -> None:
    """Write operations.json."""
    payload = {
        "generated_at": _now_iso(),
        "route_assignment_count": len(train_routes),
        "operation_state_count": len(op_states),
        "platform_assignment_count": len(platform_assignments),
        "schedule_count": len(schedules),
        "route_assignments": [_serialise_train_route(tr) for tr in train_routes],
        "operation_states": [_serialise_op_state(s) for s in op_states],
        "platform_assignments": [_serialise_platform(pa) for pa in platform_assignments],
        "schedules": list(schedules),
    }
    _write(output_dir / "operations.json", payload)


def export_statistics(stats: dict, output_dir: Path) -> None:
    """Write statistics.json."""
    payload = {"generated_at": _now_iso(), **stats}
    _write(output_dir / "statistics.json", payload)


def export_validation(report: ValidationReport, output_dir: Path) -> None:
    """Write validation.json."""
    payload = {
        "generated_at": _now_iso(),
        "passed": report.passed,
        "total_issues": report.total_issues,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "issues": [
            {
                "issue_id": i.issue_id,
                "severity": i.severity.value,
                "category": i.category,
                "message": i.message,
                "affected_id": i.affected_id,
            }
            for i in report.issues
        ],
    }
    _write(output_dir / "validation.json", payload)
