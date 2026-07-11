"""
collectors/osm/facilities.py
Collects OSM railway facilities data via Overpass API.

Includes yards, depots, engine sheds, workshops, roundhouses, turntables,
buffer stops, signal boxes, sidings, refuelling and wash facilities.

Queries are loaded from config/osm_queries.json – no hardcoded Overpass QL.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from collectors.osm._base import collect_dataset
from common.validator import ValidationResult

DATASET_NAME = "facilities"


def collect(
    raw_dir: Path,
    *,
    area_id: int | None = None,
    bbox: str = "8.0,68.0,37.0,97.5",
    timeout: int = 180,
    overwrite: bool = False,
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """
    Collect OSM railway facilities dataset (yards, depots, sheds, etc.).

    Parameters
    ----------
    raw_dir:
        Base OSM raw directory (e.g. ``raw/osm``).
    area_id:
        Overpass area ID for spatial restriction.
    bbox:
        Fallback bounding box ``"south,west,north,east"``.
    timeout:
        Overpass server-side timeout in seconds.
    overwrite:
        Force re-download even if cached data exists.

    Returns
    -------
    tuple[list[dict], ValidationResult]
    """
    return collect_dataset(
        DATASET_NAME,
        raw_dir,
        area_id=area_id,
        bbox=bbox,
        timeout=timeout,
        overwrite=overwrite,
    )
