"""
tests/test_validation.py
Extended unit tests for the validation module.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.validator import DatasetValidator, ValidationResult


class TestValidationResult:
    def test_initial_state(self) -> None:
        r = ValidationResult(collector="c", dataset="d")
        assert r.passed is True
        assert r.errors == []
        assert r.warnings == []

    def test_fail_sets_passed_false(self) -> None:
        r = ValidationResult(collector="c", dataset="d")
        r.fail("Something went wrong")
        assert r.passed is False
        assert "Something went wrong" in r.errors

    def test_warn_preserves_passed(self) -> None:
        r = ValidationResult(collector="c", dataset="d")
        r.warn("Potential issue")
        assert r.passed is True
        assert "Potential issue" in r.warnings

    def test_to_dict(self) -> None:
        r = ValidationResult(collector="osm", dataset="stations")
        r.fail("Error 1")
        r.warn("Warning 1")
        d = r.to_dict()
        assert d["collector"] == "osm"
        assert d["dataset"] == "stations"
        assert d["passed"] is False
        assert "Error 1" in d["errors"]
        assert "Warning 1" in d["warnings"]


class TestDatasetValidatorEdgeCases:
    def test_valid_json_list(self, tmp_path: Path) -> None:
        f = tmp_path / "list.json"
        f.write_text(json.dumps([{"id": 1}, {"id": 2}]))
        v = DatasetValidator("test")
        result = v.validate_file(f, "list_dataset")
        assert result.passed

    def test_null_json(self, tmp_path: Path) -> None:
        f = tmp_path / "null.json"
        f.write_text("null")
        v = DatasetValidator("test")
        result = v.validate_file(f, "null_dataset")
        assert not result.passed

    def test_empty_json_object(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.json"
        f.write_text("{}")
        v = DatasetValidator("test")
        result = v.validate_file(f, "empty_obj")
        # Empty dict → warning but not necessarily fail
        assert len(result.warnings) > 0 or not result.passed

    def test_duplicate_ids_warns(self) -> None:
        v = DatasetValidator("test")
        records = [{"id": "1", "name": "A"}, {"id": "1", "name": "B"}]
        result = v.validate_records(records, "dupes", ["id"])
        assert any("Duplicate" in w for w in result.warnings)

    def test_many_missing_keys_truncates(self) -> None:
        v = DatasetValidator("test")
        records = [{"id": str(i)} for i in range(20)]  # all missing "name"
        result = v.validate_records(records, "many", ["id", "name"])
        # Should note "more records" rather than listing all 20
        combined = " ".join(result.warnings)
        assert "more" in combined

    def test_non_json_file_skips_json_check(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3")
        v = DatasetValidator("test")
        result = v.validate_file(f, "csv_data")
        # CSV file with content should pass basic checks
        assert result.passed
