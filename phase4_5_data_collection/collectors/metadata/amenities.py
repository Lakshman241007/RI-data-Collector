"""
collectors/metadata/amenities.py
Collects amenity information for major Indian railway stations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.file_utils import timestamp_utc
from common.json_utils import save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult

_log = get_logger("metadata.amenities", "metadata.log")
DATASET_NAME = "amenities"

STATION_AMENITIES: list[dict[str, Any]] = [
    {
        "station_code": "NDLS",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "cloak_room", "medical", "pharmacy", "taxi", "metro_connectivity"],
    },
    {
        "station_code": "BCT",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "taxi", "ac_waiting_hall"],
    },
    {
        "station_code": "MAS",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "cloak_room", "medical", "taxi"],
    },
    {
        "station_code": "HWH",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "cloak_room", "medical", "taxi", "ac_waiting_hall"],
    },
    {
        "station_code": "SBC",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "taxi", "metro_connectivity"],
    },
    {
        "station_code": "SC",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "taxi"],
    },
    {
        "station_code": "PUNE",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "cloak_room", "taxi"],
    },
    {
        "station_code": "ADI",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "taxi"],
    },
    {
        "station_code": "JP",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "taxi"],
    },
    {
        "station_code": "LKO",
        "amenities": ["wifi", "atm", "food_court", "retiring_rooms", "cloak_room", "taxi"],
    },
]


def collect(
    raw_dir: Path,
    *,
    overwrite: bool = False,
    **_: Any,
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """Generate amenities dataset from curated seed list."""
    dest = raw_dir / f"{DATASET_NAME}.json"
    validator = DatasetValidator("metadata")

    if not overwrite and dest.exists() and dest.stat().st_size > 0:
        import json
        _log.info("Cache hit – loading %s from disk", DATASET_NAME)
        with dest.open(encoding="utf-8") as fh:
            data = json.load(fh)
        records = data.get("records", [])
    else:
        records = STATION_AMENITIES
        save_json(
            {"meta": {"dataset": DATASET_NAME, "collected_at": timestamp_utc(), "record_count": len(records)},
             "records": records},
            dest,
        )
        _log.info("Saved %d amenity records → %s", len(records), dest)

    result = validator.validate_records(records, DATASET_NAME, ["station_code", "amenities"])
    return records, result
