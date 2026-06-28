"""
extractor.logging_utils
=======================

Configures Python logging so that:

* every log record (from any module) is written to ``logs/pipeline.log``
  and echoed to the console, and
* the ``overpass`` and ``geofabrik`` loggers additionally write their
  own records to dedicated ``logs/overpass.log`` and
  ``logs/geofabrik.log`` files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(log_dir: Union[str, Path], level: str = "INFO") -> None:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Avoid duplicate handlers if setup_logging is called more than once
    # (e.g. across repeated test runs within the same process).
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    pipeline_handler = logging.FileHandler(log_path / "pipeline.log", encoding="utf-8")
    pipeline_handler.setFormatter(formatter)
    root_logger.addHandler(pipeline_handler)

    _attach_component_log(log_path / "overpass.log", "overpass", log_level, formatter)
    _attach_component_log(log_path / "geofabrik.log", "geofabrik", log_level, formatter)


def _attach_component_log(
    path: Path, logger_name: str, level: int, formatter: logging.Formatter
) -> None:
    component_logger = logging.getLogger(logger_name)
    component_logger.setLevel(level)
    component_logger.handlers.clear()

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(formatter)
    component_logger.addHandler(handler)
    # propagate=True (default) so messages also land in pipeline.log via root
