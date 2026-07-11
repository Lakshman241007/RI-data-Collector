"""
common/validator.py
Dataset validation utilities for the Railway Data Collection Hub.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common.checksum import sha256_file
from common.logger import get_logger

_log = get_logger("validator")


@dataclass
class ValidationResult:
    """Structured outcome of a single validation run."""

    collector: str
    dataset: str
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.passed = False
        self.errors.append(message)
        _log.error("[%s/%s] FAIL – %s", self.collector, self.dataset, message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        _log.warning("[%s/%s] WARN – %s", self.collector, self.dataset, message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collector": self.collector,
            "dataset": self.dataset,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class DatasetValidator:
    """Validate a downloaded dataset file."""

    def __init__(self, collector: str) -> None:
        self._collector = collector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_file(
        self,
        path: Path,
        dataset: str,
        *,
        expected_checksum: str | None = None,
        min_size_bytes: int = 1,
    ) -> ValidationResult:
        """
        Run a battery of checks on *path*.

        Parameters
        ----------
        path:
            File to validate.
        dataset:
            Human-readable dataset name used in the result.
        expected_checksum:
            If provided, the SHA-256 of *path* must match this value.
        min_size_bytes:
            Minimum acceptable file size (default 1 byte – no empty files).

        Returns
        -------
        ValidationResult
        """
        result = ValidationResult(collector=self._collector, dataset=dataset)

        # 1. Existence
        if not path.exists():
            result.fail(f"File not found: {path}")
            return result

        # 2. Minimum size / not empty
        size = path.stat().st_size
        if size < min_size_bytes:
            result.fail(f"File is empty or too small ({size} bytes): {path}")

        # 3. Checksum (optional)
        if expected_checksum:
            actual = sha256_file(path)
            if actual.lower() != expected_checksum.lower():
                result.fail(
                    f"Checksum mismatch for {path.name}: "
                    f"expected={expected_checksum} actual={actual}"
                )

        # 4. JSON structural validity (only for .json files)
        if path.suffix == ".json":
            self._validate_json(path, result)

        return result

    def validate_records(
        self,
        records: list[Any],
        dataset: str,
        required_keys: list[str] | None = None,
    ) -> ValidationResult:
        """
        Validate a list of record dicts.

        Parameters
        ----------
        records:
            List of dicts to validate.
        dataset:
            Human-readable dataset name.
        required_keys:
            If provided, every record must contain all these keys.

        Returns
        -------
        ValidationResult
        """
        result = ValidationResult(collector=self._collector, dataset=dataset)

        if not records:
            result.fail(f"Dataset '{dataset}' contains zero records.")
            return result

        if required_keys:
            missing_count = 0
            for i, record in enumerate(records):
                for key in required_keys:
                    if key not in record:
                        missing_count += 1
                        if missing_count <= 5:
                            result.warn(
                                f"Record {i} missing key '{key}': {record}"
                            )
            if missing_count > 5:
                result.warn(
                    f"…and {missing_count - 5} more records with missing keys."
                )

        # Duplicate detection (by id if present)
        ids = [r.get("id") for r in records if isinstance(r, dict) and "id" in r]
        if ids and len(ids) != len(set(ids)):
            result.warn(f"Duplicate 'id' values detected in dataset '{dataset}'.")

        _log.info(
            "[%s/%s] Validated %d records – passed=%s",
            self._collector,
            dataset,
            len(records),
            result.passed,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_json(self, path: Path, result: ValidationResult) -> None:
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            result.fail(f"Invalid JSON in {path.name}: {exc}")
            return

        if data is None:
            result.fail(f"JSON file {path.name} parsed as null.")
        elif isinstance(data, (list, dict)) and len(data) == 0:
            result.warn(f"JSON file {path.name} contains an empty collection.")
