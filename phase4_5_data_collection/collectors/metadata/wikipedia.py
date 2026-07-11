"""
collectors/metadata/wikipedia.py
Collects Wikipedia article extracts for major Indian railway stations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from collectors.metadata.downloader import (
    SEED_STATION_ARTICLES,
    WIKIPEDIA_API,
    fetch_wikipedia_extracts,
)
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult

_log = get_logger("metadata.wikipedia", "metadata.log")
DATASET_NAME = "wikipedia"


def collect(
    raw_dir: Path,
    *,
    api_url: str = WIKIPEDIA_API,
    timeout: int = 60,
    overwrite: bool = False,
    **_: Any,
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """
    Fetch Wikipedia extracts for seed station articles.

    Returns
    -------
    tuple[list[dict], ValidationResult]
    """
    dest = raw_dir / f"{DATASET_NAME}.json"
    validator = DatasetValidator("metadata")
    _log.info("Fetching Wikipedia extracts for %d articles…", len(SEED_STATION_ARTICLES))
    try:
        records = fetch_wikipedia_extracts(
            SEED_STATION_ARTICLES,
            dest,
            api_url=api_url,
            timeout=timeout,
            overwrite=overwrite,
        )
    except Exception as exc:
        _log.error("Wikipedia collection failed: %s", exc)
        from common.json_utils import save_json
        from common.file_utils import timestamp_utc
        records = []
        save_json({"articles": [], "error": str(exc), "collected_at": timestamp_utc()}, dest)

    result = validator.validate_records(records, DATASET_NAME, ["pageid", "title"]) if records else validator.validate_file(dest, DATASET_NAME)
    return records, result
