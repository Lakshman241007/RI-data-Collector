"""
collectors/official – Official Indian Railways Metadata Collector.

Downloads station master, codes, zones, divisions and train master
from Indian Railways official open-data sources.
"""
from __future__ import annotations

from typing import Any

from collectors import BaseCollector, CollectorResult
from collectors.official import (
    railway_divisions,
    railway_zones,
    station_codes,
    station_master,
    train_master,
)
from common.logger import get_logger

_log = get_logger("official", "official.log")


class OfficialCollector(BaseCollector):
    """Official Indian Railways Metadata Collector."""

    COLLECTOR_NAME = "official"

    def __init__(self, config: dict[str, Any], sources: dict[str, Any]) -> None:
        super().__init__(config)
        self._sources = sources.get("official", {})

    def collect(self) -> CollectorResult:
        result = self._new_result()
        manifest = self._new_manifest(
            source_name=self._sources.get("name", "Indian Railways Official Data"),
            license_str=self._sources.get("license", "Government Open Data License – India"),
        )

        timeout = self._config.get("timeout_seconds", 60)
        overwrite = self._config.get("overwrite_existing", False)
        datasets_cfg = self._sources.get("datasets", {})

        _modules = {
            "station_master": station_master,
            "station_codes": station_codes,
            "railway_zones": railway_zones,
            "railway_divisions": railway_divisions,
            "train_master": train_master,
        }

        passed = failed = warnings = 0

        for name, module in _modules.items():
            ds_cfg = datasets_cfg.get(name, {})
            if not ds_cfg.get("enabled", True):
                _log.info("Dataset '%s' is disabled – skipping.", name)
                continue

            source_url = ds_cfg.get("url", "")
            if not source_url:
                _log.warning("No URL configured for '%s' – skipping.", name)
                continue

            _log.info("=== Collecting official dataset: %s ===", name)
            try:
                records, validation = module.collect(
                    self._raw_dir,
                    source_url=source_url,
                    timeout=timeout,
                    overwrite=overwrite,
                )
                result.validation_results.append(validation)
                dest = self._raw_dir / f"{name}.json"

                if validation.passed:
                    passed += 1
                else:
                    failed += 1
                    for err in validation.errors:
                        result.add_error(f"[{name}] {err}")

                warnings += len(validation.warnings)
                result.datasets_collected += 1
                result.total_records += len(records)

                manifest.add_file(
                    dest,
                    record_count=len(records),
                    validation_passed=validation.passed,
                )

            except Exception as exc:  # noqa: BLE001
                _log.error("Failed to collect '%s': %s", name, exc, exc_info=True)
                result.add_error(f"[{name}] Exception: {exc}")
                failed += 1

        manifest.set_validation_summary(passed, failed, warnings)
        result.manifest_path = manifest.save()

        _log.info(
            "Official collection complete – datasets=%d records=%d passed=%d failed=%d",
            result.datasets_collected, result.total_records, passed, failed,
        )
        return result
