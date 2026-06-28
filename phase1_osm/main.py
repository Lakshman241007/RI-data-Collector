"""
main.py
=======

Phase 1 pipeline entry point for the Railway Data Collection platform.

    Load configuration
        -> Overpass health check
        -> Download GeoFabrik extract if needed
        -> Read PBF / extract railway objects
        -> Fetch latest railway updates from Overpass
        -> Merge datasets
        -> Validate dataset
        -> Generate outputs
        -> Generate statistics
        -> Finish

Run with:

    python main.py
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from extractor.config import load_config
from extractor.geofabrik import GeofabrikDownloader, GeofabrikError
from extractor.logging_utils import setup_logging
from extractor.merger import merge_datasets
from extractor.overpass import OverpassClient, OverpassError, parse_elements
from extractor.pbf_reader import extract_railway_objects
from extractor.validator import validate_dataset

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "settings.json"

logger = logging.getLogger("pipeline")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    logger.info("Wrote %s", path)


def run_pipeline() -> None:
    start_time = time.time()

    config = load_config(CONFIG_PATH)
    setup_logging(BASE_DIR / config.logging.log_dir, config.logging.level)

    logger.info("=== Railway Data Collection Pipeline — Phase 1 (Tamil Nadu) ===")

    output_dir = BASE_DIR / config.output.output_dir
    download_dir = BASE_DIR / config.geofabrik.download_dir

    # ------------------------------------------------------------------
    # 1. Overpass: health check + fetch latest railway edits
    # ------------------------------------------------------------------
    overpass_client = OverpassClient(config.overpass)
    overpass_raw = overpass_client.run(output_dir / config.output.raw_overpass_file)
    overpass_objects = parse_elements(overpass_raw)
    logger.info("Parsed %s railway objects from Overpass", len(overpass_objects))

    # ------------------------------------------------------------------
    # 2. GeoFabrik: download India extract if missing/incomplete
    # ------------------------------------------------------------------
    geofabrik_config = config.geofabrik
    # Resolve the download directory relative to the project root.
    resolved_geofabrik_config = geofabrik_config.__class__(
        url=geofabrik_config.url,
        download_dir=str(download_dir),
        filename=geofabrik_config.filename,
        chunk_size=geofabrik_config.chunk_size,
    )
    geofabrik_downloader = GeofabrikDownloader(resolved_geofabrik_config)
    pbf_path = geofabrik_downloader.download()

    # ------------------------------------------------------------------
    # 3. Read PBF and extract railway=* objects
    # ------------------------------------------------------------------
    geofabrik_objects = extract_railway_objects(pbf_path)
    logger.info("Extracted %s railway objects from GeoFabrik PBF", len(geofabrik_objects))
    _write_json(
        output_dir / config.output.raw_geofabrik_file,
        [obj.to_dict() for obj in geofabrik_objects],
    )

    # ------------------------------------------------------------------
    # 4. Merge GeoFabrik (bulk) + Overpass (latest)
    # ------------------------------------------------------------------
    merged_objects, duplicate_count = merge_datasets(geofabrik_objects, overpass_objects)
    _write_json(
        output_dir / config.output.master_dataset_file,
        [obj.to_dict() for obj in merged_objects],
    )

    # ------------------------------------------------------------------
    # 5. Validate the merged dataset
    # ------------------------------------------------------------------
    validation_report = validate_dataset(merged_objects)
    _write_json(output_dir / config.output.validation_file, validation_report.to_dict())

    # ------------------------------------------------------------------
    # 6. Statistics
    # ------------------------------------------------------------------
    elapsed_seconds = round(time.time() - start_time, 2)
    statistics = {
        "geofabrik_object_count": len(geofabrik_objects),
        "overpass_object_count": len(overpass_objects),
        "merged_object_count": len(merged_objects),
        "duplicate_count": duplicate_count,
        "validation_errors": len(validation_report.issues),
        "execution_time_seconds": elapsed_seconds,
    }
    _write_json(output_dir / config.output.statistics_file, statistics)

    logger.info("Pipeline finished in %s seconds", elapsed_seconds)
    logger.info("Outputs written to %s", output_dir)


if __name__ == "__main__":
    try:
        run_pipeline()
    except (OverpassError, GeofabrikError) as exc:
        logger.error("Pipeline aborted: %s", exc)
        raise
