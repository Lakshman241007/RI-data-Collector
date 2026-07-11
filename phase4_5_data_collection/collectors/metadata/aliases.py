"""
collectors/metadata/aliases.py
Collects alternate/regional names for Indian railway stations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.file_utils import timestamp_utc
from common.json_utils import save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult

_log = get_logger("metadata.aliases", "metadata.log")
DATASET_NAME = "aliases"

# Curated seed dataset of well-known station aliases.
# In production this list would grow via enrichment phases.
STATION_ALIASES: list[dict[str, Any]] = [
    {"station_code": "NDLS", "official_name": "New Delhi",        "aliases": ["New Delhi", "Nai Dilli"]},
    {"station_code": "BCT",  "official_name": "Mumbai Central",   "aliases": ["Bombay Central", "Mumbai Central"]},
    {"station_code": "MAS",  "official_name": "Chennai Central",  "aliases": ["Madras Central", "Chennai Central"]},
    {"station_code": "HWH",  "official_name": "Howrah Junction",  "aliases": ["Howrah", "Howrah Jn"]},
    {"station_code": "SBC",  "official_name": "Bangalore City Jn","aliases": ["Bangalore City", "Bengaluru City Jn"]},
    {"station_code": "SC",   "official_name": "Secunderabad Jn",  "aliases": ["Secunderabad", "SC Junction"]},
    {"station_code": "PUNE", "official_name": "Pune Junction",    "aliases": ["Poona", "Pune Jn"]},
    {"station_code": "ADI",  "official_name": "Ahmedabad Jn",     "aliases": ["Ahmedabad", "Amdavad"]},
    {"station_code": "JP",   "official_name": "Jaipur Junction",  "aliases": ["Jaipur", "Jaipur Jn"]},
    {"station_code": "LKO",  "official_name": "Lucknow Charbagh", "aliases": ["Lucknow", "Lakhnau"]},
]


def collect(
    raw_dir: Path,
    *,
    overwrite: bool = False,
    **_: Any,
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """
    Generate the aliases dataset from the curated seed list.

    Returns
    -------
    tuple[list[dict], ValidationResult]
    """
    dest = raw_dir / f"{DATASET_NAME}.json"
    validator = DatasetValidator("metadata")

    if not overwrite and dest.exists() and dest.stat().st_size > 0:
        import json
        _log.info("Cache hit – loading %s from disk", DATASET_NAME)
        with dest.open(encoding="utf-8") as fh:
            data = json.load(fh)
        records = data.get("records", [])
    else:
        records = STATION_ALIASES
        save_json(
            {"meta": {"dataset": DATASET_NAME, "collected_at": timestamp_utc(), "record_count": len(records)},
             "records": records},
            dest,
        )
        _log.info("Saved %d alias records → %s", len(records), dest)

    result = validator.validate_records(records, DATASET_NAME, ["station_code", "aliases"])
    return records, result
