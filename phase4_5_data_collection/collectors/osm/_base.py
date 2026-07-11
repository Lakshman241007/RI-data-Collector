"""
collectors/osm/_base.py
Shared collection logic for all OSM dataset modules.

Each dataset module (stations.py, tracks.py, …) calls ``collect_dataset``
from here to avoid duplicating the cache/validate/report logic.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from collectors.osm.downloader import run_overpass_query, OVERPASS_ENDPOINT, DEFAULT_TIMEOUT
from collectors.osm.utils import (
    load_query_config,
    build_multi_tag_query,
    load_from_cache,
    save_to_cache,
    write_dataset_outputs,
    validate_against_schema,
    DatasetReport,
)
from common.file_utils import timestamp_utc, ensure_dir
from common.json_utils import save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult

_log = get_logger("osm.base", "osm.log")


def collect_dataset(
    dataset: str,
    raw_dir: Path,
    *,
    area_id: int | None = None,
    bbox: str = "8.0,68.0,37.0,97.5",
    timeout: int = DEFAULT_TIMEOUT,
    overwrite: bool = False,
    endpoint: str = OVERPASS_ENDPOINT,
    retries: int = 3,
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """
    Generic collect function shared by all OSM dataset modules.

    1. Loads query config from ``config/osm_queries.json``.
    2. Checks disk cache (unless overwrite=True).
    3. Queries Overpass and caches the result.
    4. Saves raw data to ``raw_dir/<dataset>/<dataset>.json``.
    5. Validates records.
    6. Writes per-dataset report.json, manifest.json, validation.json.
    7. Validates against JSON schema.

    Parameters
    ----------
    dataset:
        Dataset key matching a key in ``config/osm_queries.json``.
    raw_dir:
        Base OSM raw directory (e.g. ``raw/osm``).
    area_id:
        Overpass area ID (e.g. Tamil Nadu = 3600184640). None = use bbox.
    bbox:
        Fallback bounding box ``"south,west,north,east"``.
    timeout:
        Overpass server-side timeout in seconds.
    overwrite:
        Force re-download even if a cache exists.
    endpoint:
        Overpass API endpoint URL.
    retries:
        HTTP retry count.

    Returns
    -------
    tuple[list[dict], ValidationResult]
    """
    ds_dir = raw_dir / dataset
    ensure_dir(ds_dir)
    dest = ds_dir / f"{dataset}.json"

    # Load query config
    try:
        query_cfg = load_query_config(dataset)
    except KeyError as exc:
        _log.error("Query config missing: %s", exc)
        result = ValidationResult(collector="osm", dataset=dataset)
        result.fail(str(exc))
        return [], result

    tags: list[str] = query_cfg["tags"]
    element_types: list[str] = query_cfg["element_types"]
    out_body: str = query_cfg.get("out_body", "body")
    filter_railway: bool = query_cfg.get("filter_railway", False)
    required_fields: list[str] = query_cfg.get("required_fields", ["id", "type"])

    records: list[dict[str, Any]] = []
    checksum = ""
    download_duration = 0.0

    # ----- Cache check -----
    if not overwrite:
        cached = load_from_cache(dataset)
        if cached is not None:
            records, checksum = cached
            _log.info("Loaded '%s' from cache (%d records)", dataset, len(records))
        elif dest.exists() and dest.stat().st_size > 0:
            # Fall back to raw dir if cache meta is absent
            _log.info("Cache meta absent; loading '%s' from raw dir", dataset)
            try:
                with dest.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                records = data.get("elements", [])
            except (json.JSONDecodeError, OSError) as exc:
                _log.warning("Failed to load raw file: %s – redownloading.", exc)
                records = []

    # ----- Download if needed -----
    if not records and (overwrite or not dest.exists() or dest.stat().st_size == 0):
        query = build_multi_tag_query(
            tags=tags,
            element_types=element_types,
            area_id=area_id,
            bbox=bbox,
            out_body=out_body,
            timeout=timeout,
            filter_railway=filter_railway,
        )
        _log.info("Querying Overpass for dataset '%s' (%d tags)…", dataset, len(tags))
        _log.debug("Query:\n%s", query)

        t0 = time.monotonic()
        try:
            data = run_overpass_query(query, endpoint=endpoint, timeout=timeout + 30, retries=retries)
            download_duration = time.monotonic() - t0
            records = data.get("elements", [])
            _log.info("Overpass returned %d elements for '%s' in %.1fs", len(records), dataset, download_duration)
        except RuntimeError as exc:
            _log.error("Overpass query failed for '%s': %s", dataset, exc)
            result = ValidationResult(collector="osm", dataset=dataset)
            result.fail(str(exc))
            return [], result

        # Save raw data
        payload: dict[str, Any] = {
            "meta": {
                "dataset": dataset,
                "tags": tags,
                "collected_at": timestamp_utc(),
                "record_count": len(records),
                "download_duration_seconds": round(download_duration, 3),
                "area_id": area_id,
                "bbox": bbox,
            },
            "elements": records,
        }
        save_json(payload, dest)
        checksum = save_to_cache(dataset, payload)
        _log.info("Saved %d records → %s", len(records), dest)

    # ----- Validation -----
    validator = DatasetValidator("osm")
    result = validator.validate_records(records, dataset, required_fields)
    file_result = validator.validate_file(dest, dataset)
    if not file_result.passed:
        result.errors.extend(file_result.errors)
        result.passed = False

    # Schema validation
    schema_errors = validate_against_schema(dataset, records)
    for err in schema_errors:
        result.warn(f"Schema: {err}")

    # ----- Compute report stats -----
    ids = [r.get("id") for r in records if isinstance(r, dict) and "id" in r]
    dup_ids = [i for i in ids if ids.count(i) > 1]
    missing_fields_count = sum(
        1 for r in records if isinstance(r, dict)
        for k in required_fields if k not in r
    )
    # Coverage summary: type breakdown
    type_counts: dict[str, int] = {}
    for r in records:
        t = r.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    report = DatasetReport(
        dataset=dataset,
        record_count=len(records),
        download_duration_seconds=round(download_duration, 3),
        validation_passed=result.passed,
        duplicate_count=len(set(dup_ids)),
        missing_field_count=missing_fields_count,
        errors=result.errors.copy(),
        warnings=result.warnings.copy(),
        coverage_summary={"by_type": type_counts, "total": len(records)},
        tags_collected=tags,
    )

    # ----- Write per-dataset outputs -----
    write_dataset_outputs(
        dataset=dataset,
        records=records,
        report=report,
        raw_dir=raw_dir,
        checksum=checksum,
    )

    return records, result
