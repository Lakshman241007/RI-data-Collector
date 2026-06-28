"""
graph/exporter.py
-----------------
Serialises extracted Station and Track objects to JSON output files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from graph.models import Station, Track
from graph.utils import save_json

logger = logging.getLogger(__name__)


def export_stations(stations: list[Station], path: Path) -> None:
    """
    Write *stations* to *path* as a JSON array.

    Parameters
    ----------
    stations : list[Station]
    path     : destination file path (parent dirs are created if needed)
    """
    logger.info("Exporting %d stations → %s", len(stations), path)
    records = [s.to_dict() for s in stations]
    save_json(records, path)
    logger.info("stations.json written (%d records)", len(records))


def export_tracks(tracks: list[Track], path: Path) -> None:
    """
    Write *tracks* to *path* as a JSON array.

    Parameters
    ----------
    tracks : list[Track]
    path   : destination file path (parent dirs are created if needed)
    """
    logger.info("Exporting %d tracks → %s", len(tracks), path)
    records = [t.to_dict() for t in tracks]
    save_json(records, path)
    logger.info("tracks.json written (%d records)", len(records))
