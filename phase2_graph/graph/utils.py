"""
graph/utils.py
--------------
Shared utility functions used across all graph modules.

No module inside this package should duplicate these helpers.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geodesic distance
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0  # metres


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Return the great-circle distance in metres between two WGS-84 points.

    Parameters
    ----------
    lat1, lon1 : float
        Origin in decimal degrees.
    lat2, lon2 : float
        Destination in decimal degrees.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def polyline_length_m(coords: list[list[float]]) -> float:
    """
    Compute the total length of a polyline in metres.

    Parameters
    ----------
    coords : list of [lon, lat] pairs  (GeoJSON order)
    """
    if len(coords) < 2:
        return 0.0

    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        total += haversine_distance(lat1, lon1, lat2, lon2)
    return total


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    """Load and return a JSON file; raises FileNotFoundError / ValueError."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(data: Any, path: Path, *, indent: int = 2) -> None:
    """Serialise *data* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=indent)
    logger.debug("Wrote %s", path)


# ---------------------------------------------------------------------------
# Tag extraction helpers
# ---------------------------------------------------------------------------

def get_tag(tags: dict[str, Any], key: str) -> str | None:
    """Return tags[key] as a stripped string, or None if absent/empty."""
    value = tags.get(key)
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def safe_float(value: Any) -> float | None:
    """Convert *value* to float, returning None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
