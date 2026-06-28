"""
graph package – Phase 2.1 railway data extraction.

Public surface area consumed by main.py and future phases:

    from graph import load_dataset, extract_stations, extract_tracks
    from graph import export_stations, export_tracks, compute_statistics
    from graph.models import RailwayObject, Station, Track
"""

from graph.dataset_loader import load_dataset
from graph.exporter import export_stations, export_tracks
from graph.models import RailwayObject, Station, Track
from graph.station_extractor import extract_stations
from graph.statistics import compute_statistics
from graph.track_extractor import extract_tracks

__all__ = [
    "load_dataset",
    "extract_stations",
    "extract_tracks",
    "export_stations",
    "export_tracks",
    "compute_statistics",
    "RailwayObject",
    "Station",
    "Track",
]
