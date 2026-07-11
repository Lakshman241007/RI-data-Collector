"""
collectors/official/downloader.py
HTTP downloader tailored for official Indian Railways open-data endpoints.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.downloader import Downloader, DownloadError
from common.logger import get_logger

_log = get_logger("official.downloader", "official.log")

# data.gov.in JSON API base
_GOVDATA_API = "https://api.data.gov.in/resource"
_API_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"


def fetch_govdata(
    resource_id: str,
    dest: Path,
    *,
    limit: int = 10_000,
    timeout: int = 60,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Fetch a data.gov.in resource (all records) and save as JSON.

    Parameters
    ----------
    resource_id:
        The resource UUID from data.gov.in.
    dest:
        Local destination JSON file.
    limit:
        Records per page (max allowed by API).
    timeout:
        HTTP timeout in seconds.
    overwrite:
        Re-download even if cached.

    Returns
    -------
    dict
        Full API response including ``records``.
    """
    import json

    if not overwrite and dest.exists() and dest.stat().st_size > 0:
        _log.info("Cache hit – %s", dest.name)
        with dest.open(encoding="utf-8") as fh:
            return json.load(fh)

    url = f"{_GOVDATA_API}/{resource_id}"
    params: dict[str, Any] = {
        "api-key": _API_KEY,
        "format": "json",
        "limit": limit,
        "offset": 0,
    }

    downloader = Downloader(timeout=timeout)
    all_records: list[dict[str, Any]] = []
    total: int | None = None
    offset = 0

    try:
        while True:
            params["offset"] = offset
            _log.debug("Fetching %s offset=%d", resource_id, offset)
            resp = downloader.get_json(url, params=params)

            records = resp.get("records", [])
            all_records.extend(records)

            if total is None:
                total = int(resp.get("total", len(records)))
            offset += len(records)

            _log.debug("Progress: %d / %d", offset, total)
            if not records or offset >= total:
                break

    except DownloadError as exc:
        _log.error("Download failed for resource %s: %s", resource_id, exc)
        raise
    finally:
        downloader.close()

    payload = {
        "resource_id": resource_id,
        "total": total,
        "records": all_records,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    _log.info("Saved %d records → %s", len(all_records), dest)
    return payload


def fetch_url_json(
    url: str,
    dest: Path,
    *,
    timeout: int = 60,
    overwrite: bool = False,
) -> Any:
    """Fetch a plain JSON URL and cache it."""
    import json

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
    finally:
        downloader.close()
