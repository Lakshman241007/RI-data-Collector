"""
common/manifest.py
Manifest generation for each collector's dataset archive.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from common.checksum import sha256_file
from common.file_utils import file_size_bytes, timestamp_utc
from common.json_utils import save_json
from common.logger import get_logger

_log = get_logger("manifest")

MANIFESTS_DIR = Path(__file__).resolve().parents[1] / "manifests"
MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DatasetEntry:
    """Manifest entry for a single dataset file."""

    name: str
    file_path: str
    checksum_sha256: str
    file_size_bytes: int
    record_count: int
    format: str
    validation_passed: bool
    notes: str = ""


@dataclass
class CollectorManifest:
    """Top-level manifest for one collector run."""

    collector_name: str
    collector_version: str
    source_name: str
    license: str
    download_timestamp: str = field(default_factory=timestamp_utc)
    dataset_version: str = "unknown"
    datasets: list[DatasetEntry] = field(default_factory=list)
    validation_summary: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def add_file(
        self,
        path: Path,
        *,
        record_count: int = 0,
        validation_passed: bool = True,
        notes: str = "",
    ) -> None:
        """
        Add *path* to the manifest, computing its checksum and size
        automatically.

        Parameters
        ----------
        path:
            Absolute or relative path to the archived file.
        record_count:
            Number of records in the dataset (if known).
        validation_passed:
            Whether validation succeeded.
        notes:
            Free-text annotation.
        """
        if not path.exists():
            _log.warning("Manifest: file not found, skipping – %s", path)
            return

        entry = DatasetEntry(
            name=path.stem,
            file_path=str(path),
            checksum_sha256=sha256_file(path),
            file_size_bytes=file_size_bytes(path),
            record_count=record_count,
            format=path.suffix.lstrip("."),
            validation_passed=validation_passed,
            notes=notes,
        )
        self.datasets.append(entry)
        _log.debug("Manifest: added entry for %s", path.name)

    def set_validation_summary(
        self,
        passed: int,
        failed: int,
        warnings: int,
    ) -> None:
        self.validation_summary = {
            "total_datasets": passed + failed,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
        }

    def total_records(self) -> int:
        return sum(e.record_count for e in self.datasets)

    def total_size_bytes(self) -> int:
        return sum(e.file_size_bytes for e in self.datasets)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total_records"] = self.total_records()
        d["total_size_bytes"] = self.total_size_bytes()
        return d

    def save(self, filename: Optional[str] = None) -> Path:
        """
        Write the manifest to ``manifests/<filename>``.

        Parameters
        ----------
        filename:
            Defaults to ``<collector_name>_manifest.json``.

        Returns
        -------
        Path
            Path of the written manifest file.
        """
        if filename is None:
            filename = f"{self.collector_name}_manifest.json"
        dest = MANIFESTS_DIR / filename
        save_json(self.to_dict(), dest)
        _log.info("Manifest saved → %s", dest)
        return dest


def load_manifest(collector_name: str) -> Optional[dict[str, Any]]:
    """Load and return an existing manifest as a plain dict, or None."""
    from common.json_utils import safe_load_json

    path = MANIFESTS_DIR / f"{collector_name}_manifest.json"
    return safe_load_json(path)
