"""
main.py
Phase 4.5.1 – Railway Data Collection Hub – Main Pipeline Entry Point.

Usage:
    python main.py [--config config/settings.json] [--dry-run]

The pipeline:
  1. Loads configuration.
  2. Runs each enabled collector sequentially.
  3. Validates all outputs.
  4. Generates manifests (done within each collector).
  5. Generates pipeline-level statistics.
  6. Prints an execution summary.
  7. Exits with code 0 on success, 1 on any failure.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when running as script
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from collectors import CollectorResult
from collectors.metadata import MetadataCollector
from collectors.official import OfficialCollector
from collectors.osm import OSMCollector
from collectors.public import PublicCollector
from common.file_utils import timestamp_utc, ensure_dir
from common.json_utils import load_json, save_json
from common.logger import get_pipeline_logger

_log = get_pipeline_logger()


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

def load_config(settings_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load settings.json and sources.json. Return (settings, sources)."""
    settings = load_json(settings_path)
    sources_path = settings_path.parent / "sources.json"
    sources = load_json(sources_path)
    return settings, sources


# ---------------------------------------------------------------------------
# Statistics generator
# ---------------------------------------------------------------------------

def build_statistics(
    results: list[CollectorResult],
    elapsed: float,
    settings: dict[str, Any],
) -> dict[str, Any]:
    total_datasets = sum(r.datasets_collected for r in results)
    total_records = sum(r.total_records for r in results)
    total_errors = sum(len(r.errors) for r in results)
    all_passed = all(r.success for r in results)

    return {
        "project": settings.get("project", "Railway Data Collection Hub"),
        "version": settings.get("version", "4.5.1"),
        "pipeline_run_at": timestamp_utc(),
        "elapsed_seconds": round(elapsed, 3),
        "overall_success": all_passed,
        "collectors": [
            {
                "name": r.collector_name,
                "success": r.success,
                "datasets_collected": r.datasets_collected,
                "total_records": r.total_records,
                "errors": r.errors,
                "manifest_path": str(r.manifest_path) if r.manifest_path else None,
            }
            for r in results
        ],
        "totals": {
            "datasets": total_datasets,
            "records": total_records,
            "errors": total_errors,
        },
    }


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(stats: dict[str, Any]) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  {stats['project']}  v{stats['version']}")
    print(f"  Pipeline completed at {stats['pipeline_run_at']}")
    print(f"  Elapsed: {stats['elapsed_seconds']:.1f} s")
    print(sep)
    for c in stats["collectors"]:
        status = "✓ PASS" if c["success"] else "✗ FAIL"
        print(
            f"  {status}  {c['name']:<12} "
            f"datasets={c['datasets_collected']:>3}  "
            f"records={c['total_records']:>8,}"
        )
        for err in c["errors"]:
            print(f"            ↳ ERROR: {err}")
    print(sep)
    t = stats["totals"]
    overall = "SUCCESS" if stats["overall_success"] else "FAILURE"
    print(
        f"  OVERALL: {overall}  "
        f"| datasets={t['datasets']:>3}  "
        f"| records={t['records']:>8,}  "
        f"| errors={t['errors']:>3}"
    )
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(settings_path: Path, dry_run: bool = False) -> bool:
    """
    Execute the full collection pipeline.

    Parameters
    ----------
    settings_path:
        Path to config/settings.json.
    dry_run:
        If True, skip actual downloads (useful for CI smoke tests).

    Returns
    -------
    bool
        True if all collectors succeeded, False otherwise.
    """
    _log.info("=" * 72)
    _log.info("Phase 4.5.1 – Railway Data Collection Hub – pipeline start")
    _log.info("Settings: %s", settings_path)
    _log.info("=" * 72)

    t0 = time.monotonic()

    # --- Load config ---
    try:
        settings, sources = load_config(settings_path)
    except Exception as exc:
        _log.critical("Failed to load configuration: %s", exc)
        return False

    collectors_cfg = settings.get("collectors", {})

    # --- Ensure output directories exist ---
    root = settings_path.parent.parent
    for d in ("raw/osm", "raw/official", "raw/public", "raw/metadata",
              "processed/osm", "processed/official", "processed/public", "processed/metadata",
              "manifests", "logs"):
        ensure_dir(root / d)

    # --- Build collector instances ---
    collectors = [
        OSMCollector(collectors_cfg.get("osm", {}), sources),
        OfficialCollector(collectors_cfg.get("official", {}), sources),
        PublicCollector(collectors_cfg.get("public", {}), sources),
        MetadataCollector(collectors_cfg.get("metadata", {}), sources),
    ]

    results: list[CollectorResult] = []

    for collector in collectors:
        name = collector.COLLECTOR_NAME
        cfg = collectors_cfg.get(name, {})

        if not cfg.get("enabled", True):
            _log.info("Collector '%s' is disabled – skipping.", name)
            continue

        _log.info(">>> Starting collector: %s", name.upper())

        if dry_run:
            _log.info("DRY RUN – skipping actual collection for '%s'", name)
            from collectors import CollectorResult as CR
            results.append(CR(collector_name=name, success=True))
            continue

        try:
            result = collector.collect()
            results.append(result)
            status = "SUCCESS" if result.success else "FAILURE"
            _log.info(
                "<<< Collector '%s' finished – %s  records=%d",
                name, status, result.total_records,
            )
        except Exception as exc:  # noqa: BLE001
            _log.error("Collector '%s' raised unhandled exception: %s", name, exc, exc_info=True)
            from collectors import CollectorResult as CR
            r = CR(collector_name=name)
            r.add_error(str(exc))
            results.append(r)

    # --- Generate statistics ---
    elapsed = time.monotonic() - t0
    stats = build_statistics(results, elapsed, settings)

    stats_path = root / settings.get("statistics_output", "statistics.json")
    save_json(stats, stats_path)
    _log.info("Statistics written → %s", stats_path)

    print_summary(stats)

    return stats["overall_success"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 4.5.1 Railway Data Collection Hub",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/settings.json"),
        help="Path to settings.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Skip actual downloads; test pipeline wiring only.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    success = run_pipeline(args.config, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
