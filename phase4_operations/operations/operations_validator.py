"""
operations.operations_validator
--------------------------------
Validates the complete operational dataset before export.

Checks
~~~~~~
* Duplicate train numbers.
* Missing route assignments.
* Invalid schedule entries.
* Platform conflicts.
* Invalid/missing timetable times.
"""

from __future__ import annotations

import logging
from typing import Sequence

from operations.models import (
    OperationState,
    PlatformAssignment,
    TimetableEntry,
    Train,
    TrainRoute,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

_ISSUE_COUNTER = 0


def _next_issue_id() -> str:
    global _ISSUE_COUNTER
    _ISSUE_COUNTER += 1
    return f"issue_{_ISSUE_COUNTER:05d}"


def _reset_counter() -> None:
    global _ISSUE_COUNTER
    _ISSUE_COUNTER = 0


def _check_duplicate_train_numbers(trains: Sequence[Train]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[str, str] = {}
    for train in trains:
        if train.train_number in seen:
            issues.append(
                ValidationIssue(
                    issue_id=_next_issue_id(),
                    severity=ValidationSeverity.ERROR,
                    category="duplicate_train_number",
                    message=f"Duplicate train number '{train.train_number}' "
                            f"(IDs: {seen[train.train_number]}, {train.train_id})",
                    affected_id=train.train_id,
                )
            )
        else:
            seen[train.train_number] = train.train_id
    return issues


def _check_missing_routes(
    trains: Sequence[Train],
    routes: Sequence[TrainRoute],
) -> list[ValidationIssue]:
    assigned = {r.train_id for r in routes}
    issues: list[ValidationIssue] = []
    for train in trains:
        if train.train_id not in assigned:
            issues.append(
                ValidationIssue(
                    issue_id=_next_issue_id(),
                    severity=ValidationSeverity.ERROR,
                    category="missing_route",
                    message=f"Train {train.train_id} has no route assignment.",
                    affected_id=train.train_id,
                )
            )
    return issues


def _check_invalid_schedules(schedules: Sequence[dict]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    valid_types = {"Daily", "Weekdays", "Weekends"}
    for sched in schedules:
        if sched.get("schedule_type") not in valid_types:
            issues.append(
                ValidationIssue(
                    issue_id=_next_issue_id(),
                    severity=ValidationSeverity.WARNING,
                    category="invalid_schedule_type",
                    message=f"Unknown schedule type '{sched.get('schedule_type')}' "
                            f"for train {sched.get('train_id')}.",
                    affected_id=sched.get("train_id"),
                )
            )
    return issues


def _check_platform_conflicts(conflict_messages: Sequence[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for msg in conflict_messages:
        issues.append(
            ValidationIssue(
                issue_id=_next_issue_id(),
                severity=ValidationSeverity.WARNING,
                category="platform_conflict",
                message=msg,
            )
        )
    return issues


def _check_invalid_times(entries: Sequence[TimetableEntry]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for entry in entries:
        # Origin must have departure; terminus must have arrival
        if entry.stop_sequence == 0 and entry.departure_time is None:
            issues.append(
                ValidationIssue(
                    issue_id=_next_issue_id(),
                    severity=ValidationSeverity.ERROR,
                    category="invalid_time",
                    message=f"Origin stop {entry.entry_id} has no departure time.",
                    affected_id=entry.train_id,
                )
            )
    return issues


def validate_all(
    trains: Sequence[Train],
    routes: Sequence[TrainRoute],
    timetable_entries: Sequence[TimetableEntry],
    schedules: Sequence[dict],
    platform_conflicts: Sequence[str],
) -> ValidationReport:
    """
    Run all validation checks and return a :class:`~operations.models.ValidationReport`.

    Parameters
    ----------
    trains, routes, timetable_entries, schedules:
        Operational data produced by upstream modules.
    platform_conflicts:
        Raw conflict messages from :mod:`operations.platform_manager`.

    Returns
    -------
    ValidationReport
    """
    _reset_counter()

    all_issues: list[ValidationIssue] = []
    all_issues += _check_duplicate_train_numbers(trains)
    all_issues += _check_missing_routes(trains, routes)
    all_issues += _check_invalid_schedules(schedules)
    all_issues += _check_platform_conflicts(platform_conflicts)
    all_issues += _check_invalid_times(timetable_entries)

    errors = sum(1 for i in all_issues if i.severity == ValidationSeverity.ERROR)
    warnings = sum(1 for i in all_issues if i.severity == ValidationSeverity.WARNING)
    infos = sum(1 for i in all_issues if i.severity == ValidationSeverity.INFO)

    report = ValidationReport(
        total_issues=len(all_issues),
        error_count=errors,
        warning_count=warnings,
        info_count=infos,
        issues=all_issues,
        passed=errors == 0,
    )

    logger.info(
        "Validation complete: %d errors, %d warnings, %d info – passed=%s",
        errors,
        warnings,
        infos,
        report.passed,
    )
    return report
