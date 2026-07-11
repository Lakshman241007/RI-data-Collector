"""
collectors/public/downloader.py
HTTP downloader for public open railway datasets (GitHub, etc.).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.downloader import Downloader, DownloadError
from common.logger import get_logger

_log = get_logger("public.downloader", "public.log")


def fetch_json_dataset(
    url: str,
    dest: Path,
    *,
    timeout: int = 60,
    overwrite: bool = False,
) -> Any:
    """
    Download a JSON dataset from *url* and cache at *dest*.

    Returns the parsed JSON content (list or dict).

    Raises
    ------
    DownloadError
        On network or HTTP failure.
    """
    if not overwrite and dest.exists() and dest.stat().st_size > 0:
        _log.info("Cache hit – %s", dest.name)
        with dest.open(encoding="utf-8") as fh:
            return json.load(fh)

    downloader = Downloader(timeout=timeout)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        downloader.download_file(url, dest, overwrite=overwrite)
        with dest.open(encoding="utf-8") as fh:
            return json.load(fh)
    except DownloadError:
        raise
    except json.JSONDecodeError as exc:
        raise DownloadError(f"Invalid JSON from {url}: {exc}") from exc
    finally:
        downloader.close()
