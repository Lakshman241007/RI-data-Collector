"""
common/logger.py
Centralised logging factory for the Railway Data Collection Hub.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Return a named logger that writes to both the console and an optional
    dedicated file inside logs/.

    Parameters
    ----------
    name:
        Logger name – typically the collector or module name.
    log_file:
        Filename (not path) for the dedicated log file, e.g. ``"osm.log"``.
        If *None* only the console handler is attached (plus any pre-existing
        handlers on the root logger).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured – return cached logger.
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # --- Console handler (INFO and above) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_FORMATTER)
    logger.addHandler(console_handler)

    # --- File handler (DEBUG and above) ---
    if log_file:
        file_path = LOG_DIR / log_file
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_FORMATTER)
        logger.addHandler(file_handler)

    return logger


def get_pipeline_logger() -> logging.Logger:
    """Return the top-level pipeline logger (writes to pipeline.log)."""
    return get_logger("pipeline", "pipeline.log")
