"""
collectors/metadata – Railway Descriptive Metadata Collector.

Collects alternate names, Wikipedia extracts, station history
and amenity data from public/curated sources.
"""
from __future__ import annotations

from typing import Any

from collectors import BaseCollector, CollectorResult
from collectors.metadata import aliases, amenities, station_history, wikipedia
from common.logger import get_logger

_log = get_logger("metadata", "metadata.log")


class MetadataCollector(BaseCollector):
    """Railway Descriptive Metadata Collector."""

    COLLECTOR_NAME = "metadata"

    def __init__(self, config: dict[str, Any], sources: dict[str, Any]) -> None:
        super().__init__(config)
        self._sources = sources.get("metadata", {})

    def collect(self) -> CollectorResult:
        result = self._new_result()
        manifest = self._new_manifest(
            source_name=self._sources.get("name", "Railway Descriptive Metadata"),
            license_str=self._sources.get("license", "CC BY-SA 4.0"),
        )

        timeout = self._config.get("timeout_seconds", 60)
        overwrite = self._config.get("overwrite_existing", False)
        datasets_cfg = self._sources.get("datasets", {})
        api_url = self._sources.get("datasets", {}).get("wikipedia", {}).get("api", "https://en.wikipedia.org/w/api.php")

        _modules: dict[str, Any] = {
            "aliases": (aliases, {}),
            "wikipedia": (wikipedia, {"api_url": api_url}),
            "station_history": (station_history, {}),
            "amenities": (amenities, {}),
        }

        passed = failed = warnings = 0

        for name, (module, extra_kwargs) in _modules.items():
            ds_cfg = datasets_cfg.get(name, {})
            if not ds_cfg.get("enabled", True):
                _log.info("Dataset '%s' is disabled – skipping.", name)
                continue

            _log.info("=== Collecting metadata dataset: %s ===", name)
            try:
                records, validation = module.collect(
                    self._raw_dir,
                    timeout=timeout,
                    overwrite=overwrite,
                    **extra_kwargs,
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
            "Metadata collection complete – datasets=%d records=%d passed=%d failed=%d",
            result.datasets_collected, result.total_records, passed, failed,
        )
        return result
