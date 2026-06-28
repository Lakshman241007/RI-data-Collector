"""
graph/statistics.py
-------------------
Computes summary statistics from extracted Station and Track objects
and writes statistics.json.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

from graph.models import Station, Track
from graph.utils import save_json

logger = logging.getLogger(__name__)


def compute_statistics(
    stations: list[Station],
    tracks: list[Track],
    output_path: Path,
) -> dict[str, Any]:
    """
    Compute and persist statistics for *stations* and *tracks*.

    Parameters
    ----------
    stations    : extracted Station list
    tracks      : extracted Track list
    output_path : destination path for statistics.json

    Returns
    -------
    dict containing all computed statistics
    """
    logger.info(
        "Computing statistics for %d stations and %d tracks",
        len(stations),
        len(tracks),
    )

    stats = {
        "stations": _station_stats(stations),
        "tracks": _track_stats(tracks),
    }

    save_json(stats, output_path)
    logger.info("statistics.json written → %s", output_path)
    return stats


# ---------------------------------------------------------------------------
# Station statistics
# ---------------------------------------------------------------------------

def _station_stats(stations: list[Station]) -> dict[str, Any]:
    type_counter: Counter[str] = Counter(s.railway for s in stations)

    return {
        "total": len(stations),
        "total_stations": type_counter.get("station", 0),
        "total_halts": type_counter.get("halt", 0),
        "total_junctions": type_counter.get("junction", 0),
        "total_platforms": type_counter.get("platform", 0),
        "total_stops": type_counter.get("stop", 0),
        "by_type": dict(type_counter),
    }


# ---------------------------------------------------------------------------
# Track statistics
# ---------------------------------------------------------------------------

def _track_stats(tracks: list[Track]) -> dict[str, Any]:
    type_counter: Counter[str] = Counter(t.railway for t in tracks)
    gauge_counter: Counter[str] = Counter(
        t.gauge for t in tracks if t.gauge is not None
    )
    electrified_counter: Counter[str] = Counter(
        t.electrified for t in tracks if t.electrified is not None
    )

    total_length_m = sum(
        t.length_m for t in tracks if t.length_m is not None
    )
    electrified_length_m = sum(
        t.length_m
        for t in tracks
        if t.length_m is not None and t.electrified not in (None, "no")
    )

    # Electrified tracks = those whose electrified tag is not None and not "no"
    electrified_count = sum(
        1
        for t in tracks
        if t.electrified is not None and t.electrified != "no"
    )

    return {
        "total": len(tracks),
        "total_length_m": round(total_length_m, 2),
        "total_length_km": round(total_length_m / 1000, 3),
        "electrified_count": electrified_count,
        "electrified_length_m": round(electrified_length_m, 2),
        "electrified_length_km": round(electrified_length_m / 1000, 3),
        "by_railway_type": dict(type_counter),
        "by_gauge": dict(gauge_counter),
        "by_electrified": dict(electrified_counter),
    }
