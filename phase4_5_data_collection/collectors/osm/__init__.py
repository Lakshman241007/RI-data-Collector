"""
collectors/osm – OSM Railway Infrastructure Collector.

Collects railway infrastructure data from OpenStreetMap via the Overpass API.
Each dataset module is completely independent and produces its own subdirectory
with raw JSON, report, manifest and validation files.

Stage 2 additions:
- Multi-tag collection per dataset (loaded from config/osm_queries.json)
- Railway facilities dataset
- Per-dataset subdirectory outputs
- Download cache (cache/osm/)
- JSON schema validation (schemas/osm/)
- statistics/osm_statistics.json
- quality/osm_quality.json
- reports/osm_report.json
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from collectors import BaseCollector, CollectorResult
from collectors.osm import (
    bridges,
    crossings,
    discovery,
    electrification,
    facilities,
    platforms,
    signals,
    stations,
    tracks,
    tunnels,
)
from common.file_utils import timestamp_utc, ensure_dir
from common.json_utils import save_json
from common.logger import get_logger

_log = get_logger("osm", "osm.log")

SOURCE_CONFIG_KEY = "osm"

_MODULE_MAP = {
    "stations": stations,
    "tracks": tracks,
    "platforms": platforms,
    "signals": signals,
    "crossings": crossings,
    "bridges": bridges,
    "tunnels": tunnels,
    "electrification": electrification,
    "facilities": facilities,
}


class OSMCollector(BaseCollector):
    """OpenStreetMap Railway Infrastructure Collector."""

    COLLECTOR_NAME = "osm"

    def __init__(self, config: dict[str, Any], sources: dict[str, Any]) -> None:
        super().__init__(config)
        self._sources = sources.get(SOURCE_CONFIG_KEY, {})

    def collect(self) -> CollectorResult:
        pipeline_start = time.monotonic()
        result = self._new_result()
        manifest = self._new_manifest(
            source_name=self._sources.get("name", "OpenStreetMap"),
            license_str=self._sources.get("license", "ODbL 1.0"),
        )

        timeout = self._config.get("timeout_seconds", 180)
        overwrite = self._config.get("overwrite_existing", False)
        area_id = self._sources.get("area_id")
        bbox = self._sources.get("bbox", "8.0,68.0,37.0,97.5")
        datasets_cfg = self._sources.get("datasets", {})

        passed = failed = warnings_total = 0
        all_records: dict[str, list[dict[str, Any]]] = {}

        for name, module in _MODULE_MAP.items():
            ds_cfg = datasets_cfg.get(name, {})
            if not ds_cfg.get("enabled", True):
                _log.info("Dataset '%s' is disabled – skipping.", name)
                continue

            _log.info("=== Collecting OSM dataset: %s ===", name)
            try:
                records, validation = module.collect(
                    self._raw_dir,
                    area_id=area_id,
                    bbox=bbox,
                    timeout=timeout,
                    overwrite=overwrite,
                )
                all_records[name] = records
                result.validation_results.append(validation)

                ds_dir = self._raw_dir / name
                dest = ds_dir / f"{name}.json"

                if validation.passed:
                    passed += 1
                else:
                    failed += 1
                    for err in validation.errors:
                        result.add_error(f"[{name}] {err}")

                warnings_total += len(validation.warnings)
                result.datasets_collected += 1
                result.total_records += len(records)

                if dest.exists():
                    manifest.add_file(
                        dest,
                        record_count=len(records),
                        validation_passed=validation.passed,
                    )

            except Exception as exc:  # noqa: BLE001
                _log.error("Failed to collect '%s': %s", name, exc, exc_info=True)
                result.add_error(f"[{name}] Exception: {exc}")
                failed += 1
                all_records[name] = []

        manifest.set_validation_summary(passed, failed, warnings_total)
        result.manifest_path = manifest.save()

        pipeline_elapsed = time.monotonic() - pipeline_start

        # --- Stage 2 final enhancement: railway tag discovery & coverage audit ---
        discovery_result = self._run_discovery(area_id, bbox, timeout, overwrite)

        self._write_statistics(all_records, pipeline_elapsed, discovery_result)
        self._write_quality_report(all_records, discovery_result)
        self._write_collector_report(result, passed, failed, pipeline_elapsed)

        _log.info(
            "OSM collection complete – datasets=%d records=%d passed=%d failed=%d elapsed=%.1fs",
            result.datasets_collected,
            result.total_records,
            passed,
            failed,
            pipeline_elapsed,
        )
        return result

    def _run_discovery(
        self,
        area_id: int | None,
        bbox: str,
        timeout: int,
        overwrite: bool,
    ) -> discovery.DiscoveryResult | None:
        """
        Run the railway tag discovery engine and write its three reports.

        This step is purely additive to Stage 2 and must never abort the
        pipeline: any failure is logged and ``None`` is returned, in which
        case statistics/quality writers simply omit the discovery section.
        """
        try:
            discovery_result = discovery.run_discovery(
                self._raw_dir,
                area_id=area_id,
                bbox=bbox,
                timeout=timeout,
                overwrite=overwrite,
                retries=self._config.get("retries", 3),
                region=self._sources.get("region", "unknown"),
            )
            known_tags = discovery.load_reference_tags()
            coverage = discovery.compute_coverage(discovery_result, known_tags)

            _log.info("Tags discovered: %d", len(discovery_result.discovered_tags))
            _log.info("Unsupported tags: %s", ", ".join(coverage["unsupported_tags"]) or "none")
            _log.info("Coverage percentage: %.2f%%", coverage["coverage_percentage"])
            _log.info("Discovery runtime: %.3fs", discovery_result.elapsed_seconds)

            reports_dir = self._root / "reports"
            coverage_dir = self._root / "coverage"
            implemented_categories = set(_MODULE_MAP.keys())

            discovery.write_discovery_report(
                discovery_result, known_tags, reports_dir, self.COLLECTOR_VERSION,
            )
            discovery.write_coverage_report(
                discovery_result, known_tags, coverage_dir, self.COLLECTOR_VERSION,
            )
            discovery.write_capability_matrix(
                discovery_result, known_tags, implemented_categories,
                reports_dir, self.COLLECTOR_VERSION,
            )
            return discovery_result
        except Exception as exc:  # noqa: BLE001 - discovery must never fail the pipeline
            _log.error("Discovery engine failed unexpectedly: %s", exc, exc_info=True)
            return None

    def _write_statistics(
        self,
        all_records: dict[str, list[dict[str, Any]]],
        elapsed: float,
        discovery_result: discovery.DiscoveryResult | None = None,
    ) -> None:
        stats_dir = self._root / "statistics"
        ensure_dir(stats_dir)

        def _count_types(records: list[dict]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for r in records:
                t = r.get("type", "unknown")
                counts[t] = counts.get(t, 0) + 1
            return counts

        def _avg_tags(records: list[dict]) -> float:
            if not records:
                return 0.0
            return round(sum(len(r.get("tags") or {}) for r in records) / len(records), 2)

        all_elements = [r for recs in all_records.values() for r in recs]
        statistics = {
            "dataset": "OSM Railway Infrastructure",
            "collector": "osm",
            "collector_version": self.COLLECTOR_VERSION,
            "generated_at": timestamp_utc(),
            "region": self._sources.get("region", "unknown"),
            "download_time_seconds": round(elapsed, 3),
            "total_railway_objects": len(all_elements),
            "by_element_type": _count_types(all_elements),
            "by_dataset": {
                name: {"count": len(recs), "types": _count_types(recs), "avg_tags": _avg_tags(recs)}
                for name, recs in all_records.items()
            },
            "stations": len(all_records.get("stations", [])),
            "tracks": len(all_records.get("tracks", [])),
            "signals": len(all_records.get("signals", [])),
            "platforms": len(all_records.get("platforms", [])),
            "crossings": len(all_records.get("crossings", [])),
            "bridges": len(all_records.get("bridges", [])),
            "tunnels": len(all_records.get("tunnels", [])),
            "facilities": len(all_records.get("facilities", [])),
            "average_tags_per_element": _avg_tags(all_elements),
        }
        if discovery_result is not None:
            statistics.update(discovery.discovery_statistics_fields(discovery_result))
        save_json(statistics, stats_dir / "osm_statistics.json")
        _log.info("Written statistics → statistics/osm_statistics.json")

    def _write_quality_report(
        self,
        all_records: dict[str, list[dict[str, Any]]],
        discovery_result: discovery.DiscoveryResult | None = None,
    ) -> None:
        quality_dir = self._root / "quality"
        ensure_dir(quality_dir)

        all_elements = [r for recs in all_records.values() for r in recs]
        ids = [r.get("id") for r in all_elements if "id" in r]
        duplicate_ids = list({i for i in ids if ids.count(i) > 1})

        missing_coords = [
            r.get("id") for r in all_elements
            if r.get("type") == "node" and ("lat" not in r or "lon" not in r)
        ]
        station_records = all_records.get("stations", [])
        missing_names = [r.get("id") for r in station_records if not (r.get("tags") or {}).get("name")]
        broken_geometry = [
            r.get("id") for r in all_elements
            if r.get("type") in ("way", "relation")
            and not r.get("geometry") and not r.get("nodes") and not r.get("members")
        ]
        unnamed_stations = [
            {"id": r.get("id"), "tags": r.get("tags")}
            for r in station_records if not (r.get("tags") or {}).get("name")
        ][:20]
        platform_records = all_records.get("platforms", [])
        orphan_platforms = [
            r.get("id") for r in platform_records
            if not (r.get("tags") or {}).get("name") and not (r.get("tags") or {}).get("ref")
        ]
        valid_railway_values = {
            "station", "halt", "stop", "junction", "terminal",
            "rail", "light_rail", "narrow_gauge", "construction", "disused",
            "abandoned", "proposed", "platform", "signal", "semaphore",
            "level_crossing", "crossing", "yard", "depot", "engine_shed",
            "maintenance", "workshop", "roundhouse", "refuelling", "wash",
            "turntable", "buffer_stop", "signal_box", "siding",
        }
        invalid_railway_tags = [
            {"id": r.get("id"), "railway": (r.get("tags") or {}).get("railway")}
            for r in all_elements
            if (r.get("tags") or {}).get("railway", "") not in valid_railway_values
            and (r.get("tags") or {}).get("railway", "")
        ]
        geometry_errors = [
            r.get("id") for r in all_records.get("tracks", [])
            if isinstance(r.get("nodes"), list) and 0 < len(r["nodes"]) < 2
        ]

        total = max(len(all_elements), 1)
        penalty = (
            len(duplicate_ids) * 2 + len(missing_coords) + len(missing_names)
            + len(broken_geometry) + len(invalid_railway_tags)
            + len(orphan_platforms) + len(geometry_errors)
        )
        score = max(0.0, round(100 - (penalty / total) * 100, 1))

        quality = {
            "dataset": "OSM Railway Infrastructure",
            "collector": "osm",
            "generated_at": timestamp_utc(),
            "region": self._sources.get("region", "unknown"),
            "total_elements": len(all_elements),
            "duplicate_ids": duplicate_ids[:50],
            "duplicate_count": len(duplicate_ids),
            "missing_coordinates": missing_coords[:50],
            "missing_coordinates_count": len(missing_coords),
            "missing_names": missing_names[:50],
            "missing_names_count": len(missing_names),
            "broken_geometry": broken_geometry[:50],
            "broken_geometry_count": len(broken_geometry),
            "unnamed_stations": unnamed_stations,
            "unnamed_stations_count": len(unnamed_stations),
            "orphan_platforms": orphan_platforms[:50],
            "orphan_platforms_count": len(orphan_platforms),
            "invalid_railway_tags": invalid_railway_tags[:50],
            "invalid_railway_tags_count": len(invalid_railway_tags),
            "geometry_errors": geometry_errors[:50],
            "geometry_errors_count": len(geometry_errors),
            "overall_quality_score": score,
        }
        if discovery_result is not None:
            quality.update(discovery.discovery_quality_fields(discovery_result))
        save_json(quality, quality_dir / "osm_quality.json")
        _log.info("Written quality report → quality/osm_quality.json (score=%.1f)", score)

    def _write_collector_report(
        self,
        result: CollectorResult,
        passed: int,
        failed: int,
        elapsed: float,
    ) -> None:
        reports_dir = self._root / "reports"
        ensure_dir(reports_dir)

        total = passed + failed
        coverage_pct = round((passed / total * 100) if total else 0, 1)

        quality_score: float = 0.0
        quality_path = self._root / "quality" / "osm_quality.json"
        if quality_path.exists():
            try:
                from common.json_utils import load_json
                q = load_json(quality_path)
                quality_score = q.get("overall_quality_score", 0.0)
            except Exception:
                pass

        collector_report = {
            "collector": "osm",
            "collector_version": self.COLLECTOR_VERSION,
            "generated_at": timestamp_utc(),
            "region": self._sources.get("region", "unknown"),
            "runtime_seconds": round(elapsed, 3),
            "datasets_collected": result.datasets_collected,
            "records_collected": result.total_records,
            "datasets_passed": passed,
            "datasets_failed": failed,
            "validation_status": "passed" if result.success else "failed",
            "coverage_percentage": coverage_pct,
            "quality_score": quality_score,
            "errors": result.errors,
            "manifest_path": str(result.manifest_path) if result.manifest_path else None,
            "validation_results": [v.to_dict() for v in result.validation_results],
        }
        save_json(collector_report, reports_dir / "osm_report.json")
        _log.info(
            "Written collector report → reports/osm_report.json (coverage=%.1f%% quality=%.1f)",
            coverage_pct, quality_score,
        )
