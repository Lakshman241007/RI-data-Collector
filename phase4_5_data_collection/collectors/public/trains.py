"""collectors/public/trains.py – collects public IR trains dataset."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from collectors.public.downloader import fetch_json_dataset
from common.file_utils import timestamp_utc
from common.json_utils import save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult

_log = get_logger("public.trains", "public.log")
DATASET_NAME = "trains"

def collect(raw_dir: Path, *, source_url: str, timeout: int = 60, overwrite: bool = False) -> tuple[list[dict[str, Any]], ValidationResult]:
    dest = raw_dir / f"{DATASET_NAME}.json"
    validator = DatasetValidator("public")
    _log.info("Collecting public dataset: %s from %s", DATASET_NAME, source_url)
    try:
        data = fetch_json_dataset(source_url, dest, timeout=timeout, overwrite=overwrite)
    except Exception as exc:
        _log.error("Failed to fetch trains: %s", exc)
        data = {"records": [], "error": str(exc), "collected_at": timestamp_utc()}
        save_json(data, dest)
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("features", data.get("records", data.get("data", [])))
        if not isinstance(records, list):
            records = [data]
    else:
        records = []
    if records:
        result = validator.validate_records(records, DATASET_NAME)
    else:
        result = validator.validate_file(dest, DATASET_NAME, min_size_bytes=1)
    return records, result
