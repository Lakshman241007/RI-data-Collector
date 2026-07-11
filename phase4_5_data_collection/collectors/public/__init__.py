"""
collectors/public – Public Railway Dataset Collector.

Downloads trains, timetables, facilities and elevation data from
publicly available repositories.
"""
from __future__ import annotations

from typing import Any

from collectors import BaseCollector, CollectorResult
from collectors.public import elevations, facilities, timetables, trains
from common.logger import get_logger

_log = get_logger("public", "public.log")


class PublicCollector(BaseCollector):
    """Public Railway Dataset Collector."""

    COLLECTOR_NAME = "public"

    def __init__(self, config: dict[str, Any], sources: dict[str, Any]) -> None:
        super().__init__(config)
        self._sources = sources.get("public", {})

    def collect(self) -> CollectorResult:
        result = self._new_result()
        manifest = self._new_manifest(
            source_name=self._sources.get("name", "Public Railway Datasets"),
            license_str=self._sources.get("license", "Public Domain / CC0"),
        )

        timeout = self._config.get("timeout_seconds", 60)
        overwrite = self._config.get("overwrite_existing", False)
        datasets_cfg = self._sources.get("datasets", {})

        _modules = {
            "trains": trains,
            "timetables": timetables,
            "facilities": facilities,
            "elevations": elevations,
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

            _log.info("=== Collecting public dataset: %s ===", name)
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
            "Public collection complete – datasets=%d records=%d passed=%d failed=%d",
            result.datasets_collected, result.total_records, passed, failed,
        )
        return result
