"""
extractor.config
================

Loads ``config/settings.json`` into typed, immutable dataclasses so every
other module receives configuration through a single, well-defined
object instead of raw dictionaries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass(frozen=True)
class OverpassConfig:
    endpoint: str
    timeout: int
    retries: int
    retry_backoff: int
    region: str
    user_agent: str = "TamilNaduRailwayCollector/1.0"


@dataclass(frozen=True)
class GeoFabrikConfig:
    url: str
    download_dir: str
    filename: str
    chunk_size: int
    download_retries: int = 3


@dataclass(frozen=True)
class OutputConfig:
    output_dir: str
    raw_overpass_file: str
    raw_geofabrik_file: str
    master_dataset_file: str
    validation_file: str
    statistics_file: str


@dataclass(frozen=True)
class LoggingConfig:
    log_dir: str
    level: str
    
@dataclass(frozen=True)
class ValidationConfig:
    remove_duplicates: bool
    prefer_overpass: bool
    validate_geometry: bool


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool
    directory: str


@dataclass(frozen=True)
class AppConfig:
    overpass: OverpassConfig
    geofabrik: GeoFabrikConfig
    output: OutputConfig
    logging: LoggingConfig
    validation: ValidationConfig
    cache: CacheConfig


def load_config(path: Union[str, Path]) -> AppConfig:
    """Read and validate ``settings.json``, returning a typed ``AppConfig``."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    try:
        return AppConfig(
    overpass=OverpassConfig(**raw["overpass"]),
    geofabrik=GeoFabrikConfig(**raw["geofabrik"]),
    output=OutputConfig(**raw["output"]),
    logging=LoggingConfig(**raw["logging"]),
    validation=ValidationConfig(**raw["validation"]),
    cache=CacheConfig(**raw["cache"]),
)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid configuration file {config_path}: {exc}") from exc
