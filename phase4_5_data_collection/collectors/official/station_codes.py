"""collectors/official/station_codes.py – collects official IR station codes data."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from collectors.official.downloader import fetch_url_json
from common.file_utils import timestamp_utc
from common.json_utils import save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult
import json

_log = get_logger("official.station_codes", "official.log")
DATASET_NAME = "station_codes"

def collect(raw_dir: Path, *, source_url: str, timeout: int = 60, overwrite: bool = False) -> tuple[list[dict[str, Any]], ValidationResult]:
    """Download station codes and return (records, ValidationResult)."""
    dest = raw_dir / f"{DATASET_NAME}.json"
    validator = DatasetValidator("official")
    _log.info("Collecting official dataset: %s", DATASET_NAME)
    try:
        data = fetch_url_json(source_url, dest, timeout=timeout, overwrite=overwrite)
    except Exception as exc:
        _log.error("Failed to fetch station_codes: %s", exc)
        # Produce empty stub so pipeline continues
        data = {"records": [], "error": str(exc), "collected_at": timestamp_utc()}
        save_json(data, dest)
    records = data if isinstance(data, list) else data.get("records", data.get("features", []))
    if not isinstance(records, list):
        records = [records] if records else []
    result = validator.validate_records(records, DATASET_NAME) if records else validator.validate_file(dest, DATASET_NAME)
    return records, result
