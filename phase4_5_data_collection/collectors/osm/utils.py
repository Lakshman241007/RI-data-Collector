"""
collectors/osm/utils.py
Shared utilities for OSM Railway Infrastructure Collector.

Provides:
- Query loading from config/osm_queries.json
- Cache management (per-dataset, checksum-aware)
- Schema validation via jsonschema
- Per-dataset report, manifest and validation writers
- Multi-tag Overpass query builder
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from common.file_utils import timestamp_utc, ensure_dir
from common.json_utils import load_json, save_json, safe_load_json
from common.logger import get_logger

_log = get_logger("osm.utils", "osm.log")

# ---------------------------------------------------------------------------
# Project-root resolution
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_QUERIES_PATH = _PROJECT_ROOT / "config" / "osm_queries.json"
_SCHEMAS_DIR = _PROJECT_ROOT / "schemas" / "osm"
_CACHE_DIR = _PROJECT_ROOT / "cache" / "osm"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Query loading
# ---------------------------------------------------------------------------

def load_query_config(dataset: str) -> dict[str, Any]:
    """Return the query config block for *dataset* from osm_queries.json."""
    queries = load_json(_QUERIES_PATH)
    if dataset not in queries:
        raise KeyError(f"No query config for dataset '{dataset}' in {_QUERIES_PATH}")
    return queries[dataset]


# ---------------------------------------------------------------------------
# Multi-tag Overpass query builder
# ---------------------------------------------------------------------------

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
_DEFAULT_BBOX = "8.0,68.0,37.0,97.5"


def build_multi_tag_query(
    *,
    tags: list[str],
    element_types: list[str],
    area_id: int | None,
    bbox: str = _DEFAULT_BBOX,
    out_body: str = "body",
    timeout: int = 180,
    filter_railway: bool = False,
) -> str:
    """
    Build an Overpass QL union query that collects multiple tags in one request.

    Parameters
    ----------
    tags:
        List of OSM tag strings like ``["railway=station", "railway=halt"]``.
    element_types:
        Overpass element type specifiers: any of ``["node","way","relation"]``.
    area_id:
        Overpass area relation ID (e.g. Tamil Nadu = 3600184640).
    bbox:
        Fallback bounding box ``"south,west,north,east"`` if *area_id* is None.
    out_body:
        Output verbosity: ``"body"`` or ``"geom"``.
    timeout:
        Overpass server-side timeout in seconds.
    filter_railway:
        If True, also add ``[railway]`` filter to every clause so that only
        railway-related bridges/tunnels are returned.

    Returns
    -------
    str
        Complete Overpass QL query string.
    """
    if area_id:
        spatial = f"(area.searchArea)"
        area_header = f"area({area_id + 3_600_000_000})->.searchArea;\n"
    else:
        spatial = f"({bbox})"
        area_header = ""

    railway_filter = '[railway]' if filter_railway else ''

    clauses: list[str] = []
    for tag in tags:
        key, _, value = tag.partition("=")
        if value and value != "*":
            tag_filter = f'["{key}"="{value}"]'
        else:
            tag_filter = f'["{key}"]'

        for etype in element_types:
            clauses.append(f"  {etype}{tag_filter}{railway_filter}{spatial};")

    union_body = "\n".join(clauses)
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"{area_header}"
        f"(\n{union_body}\n);\n"
        f"out {out_body};\n"
        f">;\n"
        f"out skel qt;"
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_meta_path(dataset: str) -> Path:
    return _CACHE_DIR / f"{dataset}.cache.json"


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_from_cache(dataset: str) -> tuple[list[dict[str, Any]], str] | None:
    """
    Return (records, checksum) from disk cache, or None if not cached.

    Validates cache integrity by re-computing SHA-256 of the cached data file.
    """
    meta_path = _cache_meta_path(dataset)
    meta = safe_load_json(meta_path)
    if not meta:
        return None

    data_path = _CACHE_DIR / meta.get("data_file", "")
    if not data_path.exists():
        _log.warning("Cache meta found but data file missing: %s", data_path)
        return None

    stored_checksum = meta.get("checksum", "")
    raw_bytes = data_path.read_bytes()
    actual_checksum = _compute_checksum(raw_bytes)

    if actual_checksum != stored_checksum:
        _log.warning("Cache checksum mismatch for '%s' – invalidating.", dataset)
        return None

    try:
        data = json.loads(raw_bytes)
        records = data.get("elements", [])
        _log.info("Cache hit for '%s' – %d records (checksum OK)", dataset, len(records))
        return records, stored_checksum
    except json.JSONDecodeError as exc:
        _log.warning("Cache JSON decode error for '%s': %s", dataset, exc)
        return None


def save_to_cache(dataset: str, payload: dict[str, Any]) -> str:
    """
    Persist *payload* to the cache directory and return SHA-256 checksum.

    Parameters
    ----------
    dataset:
        Dataset name used as cache key.
    payload:
        Full Overpass response payload (with ``"elements"`` key).

    Returns
    -------
    str
        SHA-256 hex digest of the serialised payload.
    """
    ensure_dir(_CACHE_DIR)
    data_file = f"{dataset}.json"
    data_path = _CACHE_DIR / data_file
    raw_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    data_path.write_bytes(raw_bytes)
    checksum = _compute_checksum(raw_bytes)
    meta = {
        "dataset": dataset,
        "data_file": data_file,
        "checksum": checksum,
        "cached_at": timestamp_utc(),
        "record_count": len(payload.get("elements", [])),
    }
    save_json(meta, _cache_meta_path(dataset))
    _log.info("Cached '%s' → %s (checksum=%s)", dataset, data_path, checksum[:12])
    return checksum


# ---------------------------------------------------------------------------
# Per-dataset output writers
# ---------------------------------------------------------------------------

@dataclass
class DatasetReport:
    """Structured report for one dataset collection run."""
    dataset: str
    collector: str = "osm"
    record_count: int = 0
    download_duration_seconds: float = 0.0
    validation_passed: bool = True
    duplicate_count: int = 0
    missing_field_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage_summary: dict[str, Any] = field(default_factory=dict)
    tags_collected: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=timestamp_utc)


def write_dataset_outputs(
    *,
    dataset: str,
    records: list[dict[str, Any]],
    report: DatasetReport,
    raw_dir: Path,
    checksum: str = "",
) -> None:
    """
    Write report.json, manifest.json and validation.json into
    ``raw_dir/<dataset>/``.

    Parameters
    ----------
    dataset:
        Dataset name.
    records:
        Collected OSM element records.
    report:
        Pre-built report dataclass.
    raw_dir:
        The OSM raw directory (e.g. ``raw/osm``).
    checksum:
        SHA-256 of the raw data file (if available).
    """
    ds_dir = raw_dir / dataset
    ensure_dir(ds_dir)

    # --- report.json ---
    save_json(asdict(report), ds_dir / "report.json")

    # --- manifest.json ---
    manifest = {
        "dataset": dataset,
        "collector": "osm",
        "collector_version": "4.5.1",
        "generated_at": timestamp_utc(),
        "record_count": len(records),
        "data_file": f"{dataset}.json",
        "checksum_sha256": checksum,
        "validation_passed": report.validation_passed,
        "errors": report.errors,
        "warnings": report.warnings,
    }
    save_json(manifest, ds_dir / "manifest.json")

    # --- validation.json ---
    ids = [r.get("id") for r in records if isinstance(r, dict) and "id" in r]
    unique_ids = set(ids)
    duplicate_ids = [str(i) for i in ids if ids.count(i) > 1]

    missing_lat = sum(
        1 for r in records
        if r.get("type") == "node" and ("lat" not in r or "lon" not in r)
    )
    missing_geometry = sum(
        1 for r in records
        if r.get("type") in ("way", "relation") and not r.get("geometry") and not r.get("nodes")
    )
    missing_tags = sum(1 for r in records if not r.get("tags"))
    empty_dataset = len(records) == 0

    # Collect invalid railway tag values
    query_cfg = safe_load_json(_QUERIES_PATH) or {}
    valid_tags_raw: list[str] = []
    if dataset in query_cfg:
        valid_tags_raw = query_cfg[dataset].get("tags", [])
    valid_railway_values = {t.split("=", 1)[-1] for t in valid_tags_raw if "=" in t}

    invalid_railway = []
    for r in records:
        rv = (r.get("tags") or {}).get("railway", "")
        if rv and valid_railway_values and rv not in valid_railway_values:
            invalid_railway.append({"id": r.get("id"), "railway": rv})

    validation = {
        "dataset": dataset,
        "validated_at": timestamp_utc(),
        "record_count": len(records),
        "duplicate_ids": list(set(duplicate_ids)),
        "duplicate_count": len(set(duplicate_ids)),
        "missing_coordinates": missing_lat,
        "missing_geometry": missing_geometry,
        "missing_tags": missing_tags,
        "invalid_railway_values": invalid_railway[:20],
        "empty_dataset": empty_dataset,
        "passed": (
            not empty_dataset
            and len(set(duplicate_ids)) == 0
            and missing_lat == 0
        ),
    }
    save_json(validation, ds_dir / "validation.json")

    _log.info(
        "Written outputs for '%s': %d records, duplicates=%d, missing_coords=%d",
        dataset, len(records), len(set(duplicate_ids)), missing_lat,
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_against_schema(dataset: str, records: list[dict[str, Any]]) -> list[str]:
    """
    Validate *records* against ``schemas/osm/<dataset>_schema.json``.

    Returns a list of error strings (empty list means all valid).
    """
    schema_name = f"{dataset.rstrip('s')}_schema.json"
    schema_path = _SCHEMAS_DIR / schema_name
    if not schema_path.exists():
        # Try with trailing s removed (facilities → facility)
        alt_name = f"{dataset[:-3]}_schema.json" if dataset.endswith("ies") else schema_name
        schema_path = _SCHEMAS_DIR / alt_name
    if not schema_path.exists():
        _log.debug("No schema found for '%s' – skipping schema validation.", dataset)
        return []

    try:
        import jsonschema  # type: ignore
    except ImportError:
        _log.warning("jsonschema not installed – schema validation skipped.")
        return []

    try:
        schema = load_json(schema_path)
    except Exception as exc:
        return [f"Schema load error: {exc}"]

    errors: list[str] = []
    # Validate first 50 records for performance
    for i, record in enumerate(records[:50]):
        try:
            jsonschema.validate(instance=record, schema=schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"Record {i} (id={record.get('id')}): {exc.message}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Record {i}: unexpected validation error: {exc}")

    if errors:
        _log.warning("Schema validation for '%s' found %d error(s).", dataset, len(errors))
    else:
        _log.info("Schema validation passed for '%s' (%d records sampled).", dataset, min(50, len(records)))

    return errors
