"""
collectors/metadata/station_history.py
Collects historical metadata for major Indian railway stations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.file_utils import timestamp_utc
from common.json_utils import save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult

_log = get_logger("metadata.station_history", "metadata.log")
DATASET_NAME = "station_history"

# Curated historical records for seed stations
STATION_HISTORY: list[dict[str, Any]] = [
    {"station_code": "NDLS", "name": "New Delhi",         "opened_year": 1926, "zone": "NR",  "notes": "Opened as New Delhi station on the Delhi–Ambala line."},
    {"station_code": "BCT",  "name": "Mumbai Central",    "opened_year": 1930, "zone": "WR",  "notes": "Originally Bombay Central, renamed after city renaming."},
    {"station_code": "MAS",  "name": "Chennai Central",   "opened_year": 1873, "zone": "SR",  "notes": "Oldest major station in South India; terminus of the Madras Railway."},
    {"station_code": "HWH",  "name": "Howrah Junction",   "opened_year": 1854, "zone": "ER",  "notes": "India's oldest and largest railway complex."},
    {"station_code": "SBC",  "name": "Bangalore City Jn", "opened_year": 1864, "zone": "SWR", "notes": "Established by the Mysore State Railway."},
    {"station_code": "SC",   "name": "Secunderabad Jn",   "opened_year": 1874, "zone": "SCR", "notes": "Built during the Nizam's railway era."},
    {"station_code": "PUNE", "name": "Pune Junction",     "opened_year": 1858, "zone": "CR",  "notes": "One of the busiest junctions on the Central Railway."},
    {"station_code": "ADI",  "name": "Ahmedabad Jn",      "opened_year": 1864, "zone": "WR",  "notes": "Key hub for the Bombay-Baroda Railway."},
    {"station_code": "JP",   "name": "Jaipur Junction",   "opened_year": 1874, "zone": "NWR", "notes": "Gateway to Rajasthan's Pink City."},
    {"station_code": "LKO",  "name": "Lucknow Charbagh",  "opened_year": 1914, "zone": "NR",  "notes": "Famous Mughal-Rajput architectural terminus."},
]


def collect(
    raw_dir: Path,
    *,
    overwrite: bool = False,
    **_: Any,
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """Generate station history dataset from curated seed list."""
    dest = raw_dir / f"{DATASET_NAME}.json"
    validator = DatasetValidator("metadata")

    if not overwrite and dest.exists() and dest.stat().st_size > 0:
        import json
        _log.info("Cache hit – loading %s from disk", DATASET_NAME)
        with dest.open(encoding="utf-8") as fh:
            data = json.load(fh)
        records = data.get("records", [])
    else:
        records = STATION_HISTORY
        save_json(
            {"meta": {"dataset": DATASET_NAME, "collected_at": timestamp_utc(), "record_count": len(records)},
             "records": records},
            dest,
        )
        _log.info("Saved %d station history records → %s", len(records), dest)

    result = validator.validate_records(records, DATASET_NAME, ["station_code", "name", "opened_year"])
    return records, result
