"""
collectors – base class and registry for all Railway Data collectors.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common.logger import get_logger
from common.manifest import CollectorManifest
from common.validator import ValidationResult


@dataclass
class CollectorResult:
    """Summary of a single collector run."""

    collector_name: str
    success: bool = True
    datasets_collected: int = 0
    total_records: int = 0
    validation_results: list[ValidationResult] = field(default_factory=list)
    manifest_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.success = False
        self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collector_name": self.collector_name,
            "success": self.success,
            "datasets_collected": self.datasets_collected,
            "total_records": self.total_records,
            "validation_results": [v.to_dict() for v in self.validation_results],
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "errors": self.errors,
        }


class BaseCollector(ABC):
    """
    Abstract base class that every collector must extend.

    Subclasses must implement :meth:`collect`.
    """

    #: Override in each subclass
    COLLECTOR_NAME: str = "base"
    COLLECTOR_VERSION: str = "4.5.1"

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._log = get_logger(
            self.COLLECTOR_NAME,
            config.get("log_file", f"{self.COLLECTOR_NAME}.log"),
        )
        self._root = Path(__file__).resolve().parents[1]
        self._raw_dir = self._root / "raw" / self.COLLECTOR_NAME
        self._processed_dir = self._root / "processed" / self.COLLECTOR_NAME
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._processed_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def collect(self) -> CollectorResult:
        """
        Execute the full collection pipeline for this collector.

        Must:
        1. Download data.
        2. Validate data.
        3. Archive raw files.
        4. Generate manifest.
        5. Write logs.

        Returns
        -------
        CollectorResult
        """

    # ------------------------------------------------------------------
    # Shared helpers available to all subclasses
    # ------------------------------------------------------------------

    def _new_manifest(
        self,
        source_name: str,
        license_str: str,
        dataset_version: str = "unknown",
    ) -> CollectorManifest:
        return CollectorManifest(
            collector_name=self.COLLECTOR_NAME,
            collector_version=self.COLLECTOR_VERSION,
            source_name=source_name,
            license=license_str,
            dataset_version=dataset_version,
        )

    def _new_result(self) -> CollectorResult:
        return CollectorResult(collector_name=self.COLLECTOR_NAME)
