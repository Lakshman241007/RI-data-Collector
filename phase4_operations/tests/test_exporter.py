"""Tests for operations.exporter."""
from __future__ import annotations

import json
from pathlib import Path

from operations.exporter import (
    export_trains,
    export_timetables,
    export_operations,
    export_statistics,
    export_validation,
)
from operations.models import ValidationReport


class TestExportTrains:
    def test_file_created(self, tmp_path, sample_trains):
        export_trains(sample_trains, tmp_path)
        assert (tmp_path / "trains.json").exists()

    def test_content_correct(self, tmp_path, sample_trains):
        export_trains(sample_trains, tmp_path)
        data = json.loads((tmp_path / "trains.json").read_text())
        assert data["train_count"] == len(sample_trains)
        assert len(data["trains"]) == len(sample_trains)

    def test_has_generated_at(self, tmp_path, sample_trains):
        export_trains(sample_trains, tmp_path)
        data = json.loads((tmp_path / "trains.json").read_text())
        assert "generated_at" in data


class TestExportTimetables:
    def test_file_created(self, tmp_path, sample_timetable_entries):
        export_timetables(sample_timetable_entries, tmp_path)
        assert (tmp_path / "timetables.json").exists()

    def test_entry_count(self, tmp_path, sample_timetable_entries):
        export_timetables(sample_timetable_entries, tmp_path)
        data = json.loads((tmp_path / "timetables.json").read_text())
        assert data["entry_count"] == len(sample_timetable_entries)


class TestExportValidation:
    def test_passed_flag(self, tmp_path):
        report = ValidationReport(passed=True)
        export_validation(report, tmp_path)
        data = json.loads((tmp_path / "validation.json").read_text())
        assert data["passed"] is True

    def test_failed_flag(self, tmp_path):
        report = ValidationReport(passed=False, error_count=1, total_issues=1)
        export_validation(report, tmp_path)
        data = json.loads((tmp_path / "validation.json").read_text())
        assert data["passed"] is False
        assert data["error_count"] == 1


class TestExportStatistics:
    def test_file_created(self, tmp_path):
        export_statistics({"total_trains": 5}, tmp_path)
        assert (tmp_path / "statistics.json").exists()

    def test_stats_preserved(self, tmp_path):
        export_statistics({"total_trains": 42}, tmp_path)
        data = json.loads((tmp_path / "statistics.json").read_text())
        assert data["total_trains"] == 42
