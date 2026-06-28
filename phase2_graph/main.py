"""
main.py
-------
Phase 2.1 pipeline entry point.

Pipeline
--------
1. Load master_railway_dataset.json  →  list[RailwayObject]
2. Extract stations                  →  list[Station]
3. Extract tracks                    →  list[Track]
4. Compute statistics                →  statistics.json
5. Export stations                   →  output/stations.json
6. Export tracks                     →  output/tracks.json
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: configure logging before importing any graph module so that
# every module's module-level logger is already configured.
# ---------------------------------------------------------------------------

def _setup_logging(settings: dict) -> None:
    log_cfg = settings.get("logging", {})
    log_dir = Path(log_cfg.get("directory", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = log_dir / log_cfg.get("filename", "phase2_graph.log")

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (rotating, max 10 MB, 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def _load_settings(config_path: Path) -> dict:
    with config_path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(settings: dict) -> None:
    from graph import (
        compute_statistics,
        export_stations,
        export_tracks,
        extract_stations,
        extract_tracks,
        load_dataset,
    )

    logger = logging.getLogger("pipeline")
    t_start = time.perf_counter()

    # ── Resolve paths ────────────────────────────────────────────────────
    base = Path(__file__).parent
    input_path = base / settings["input"]["master_dataset_path"]
    out_dir = base / settings["output"]["directory"]
    out_dir.mkdir(parents=True, exist_ok=True)

    stations_path = out_dir / settings["output"]["stations_file"]
    tracks_path = out_dir / settings["output"]["tracks_file"]
    stats_path = out_dir / settings["output"]["statistics_file"]

    # ── Step 1: Load ─────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1 — Loading dataset")
    railway_objects = load_dataset(input_path)
    logger.info("Loaded %d RailwayObjects", len(railway_objects))

    # ── Step 2: Extract stations ─────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2 — Extracting stations")
    stations = extract_stations(railway_objects)
    logger.info("Extracted %d stations", len(stations))

    # ── Step 3: Extract tracks ───────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 3 — Extracting tracks")
    tracks = extract_tracks(railway_objects)
    logger.info("Extracted %d tracks", len(tracks))

    # ── Step 4: Statistics ───────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4 — Computing statistics")
    stats = compute_statistics(stations, tracks, stats_path)
    _log_stats_summary(logger, stats)

    # ── Step 5: Export stations ──────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 5 — Exporting stations")
    export_stations(stations, stations_path)

    # ── Step 6: Export tracks ────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 6 — Exporting tracks")
    export_tracks(tracks, tracks_path)

    # ── Step 7: Build railway graph (Phase 2.2) ──────────────────────────
    # Phase 2.2 is a separate stage that consumes the Phase 2.1 outputs
    # written above exactly as they are; it does not reuse or alter any
    # Phase 2.1 in-memory objects or logic.
    logger.info("=" * 60)
    logger.info("STEP 7 — Building railway graph (Phase 2.2)")
    from graph.graph_builder import run_graph_pipeline

    graph_settings_path = base / "config" / "graph_settings.json"
    graph_settings = _load_settings(graph_settings_path)
    graph_stats = run_graph_pipeline(graph_settings, base)
    _log_graph_stats_summary(logger, graph_stats)

    elapsed = time.perf_counter() - t_start
    logger.info("=" * 60)
    logger.info("Pipeline complete in %.2f s", elapsed)
    logger.info("Output directory: %s", out_dir.resolve())


def _log_stats_summary(logger: logging.Logger, stats: dict) -> None:
    s = stats.get("stations", {})
    t = stats.get("tracks", {})
    logger.info(
        "Stations — total=%d  (station=%d  halt=%d  junction=%d  "
        "platform=%d  stop=%d)",
        s.get("total", 0),
        s.get("total_stations", 0),
        s.get("total_halts", 0),
        s.get("total_junctions", 0),
        s.get("total_platforms", 0),
        s.get("total_stops", 0),
    )
    logger.info(
        "Tracks  — total=%d  length=%.1f km  electrified=%d",
        t.get("total", 0),
        t.get("total_length_km", 0.0),
        t.get("electrified_count", 0),
    )


def _log_graph_stats_summary(logger: logging.Logger, stats: dict) -> None:
    """Phase 2.2 — log a one-line summary of the built railway graph."""
    logger.info(
        "Graph — nodes=%d  edges=%d  avg_degree=%.2f  components=%d  "
        "isolated=%d  length=%.1f km",
        stats.get("node_count", 0),
        stats.get("edge_count", 0),
        stats.get("average_node_degree", 0.0),
        stats.get("connected_components", 0),
        stats.get("isolated_stations", 0),
        stats.get("total_track_length_km", 0.0),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config_path = Path(__file__).parent / "config" / "settings.json"
    settings = _load_settings(config_path)
    _setup_logging(settings)
    run_pipeline(settings)
