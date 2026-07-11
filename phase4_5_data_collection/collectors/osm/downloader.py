"""
collectors/osm/downloader.py
Overpass API query executor for OSM railway data.

All Overpass query templates are loaded from config/osm_queries.json.
No queries are hardcoded here.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from common.logger import get_logger

_log = get_logger("osm.downloader", "osm.log")

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
DEFAULT_TIMEOUT = 180


def run_overpass_query(
    query: str,
    endpoint: str = OVERPASS_ENDPOINT,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 3,
) -> dict[str, Any]:
    """
    Execute an Overpass QL query and return the parsed JSON response.

    Parameters
    ----------
    query:
        Full Overpass QL query string.
    endpoint:
        Overpass API URL.
    timeout:
        HTTP request timeout in seconds.
    retries:
        Number of retry attempts on transient errors.

    Returns
    -------
    dict
        Parsed Overpass JSON (``{"elements": [...], ...}``).

    Raises
    ------
    RuntimeError
        If all retries are exhausted.
    """
    headers = {
        "User-Agent": "RailwayDataCollectionHub/4.5.1",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    for attempt in range(1, retries + 1):
        _log.debug("Overpass query attempt %d/%d", attempt, retries)
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            element_count = len(data.get("elements", []))
            _log.info("Overpass returned %d elements", element_count)
            return data
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            _log.warning("HTTP %s on attempt %d – retrying…", status, attempt)
        except (requests.RequestException, ValueError) as exc:
            _log.warning("Error on attempt %d: %s – retrying…", attempt, exc)

        if attempt < retries:
            backoff = 2 ** attempt
            _log.debug("Backing off %d s…", backoff)
            time.sleep(backoff)

    raise RuntimeError(
        f"Overpass query failed after {retries} attempts.\nQuery:\n{query}"
    )


def build_railway_query(
    tag: str,
    element_type: str = "nwr",
    area_id: int | None = None,
    bbox: str = "8.0,68.0,37.0,97.5",
    out_body: str = "body",
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Build a simple single-tag Overpass QL query for a railway tag.

    For multi-tag queries use ``collectors.osm.utils.build_multi_tag_query``.

    Parameters
    ----------
    tag:
        OSM tag filter, e.g. ``"railway=station"`` or ``"bridge=yes"``.
    element_type:
        Overpass element types: ``"node"``, ``"way"``, ``"relation"``, or ``"nwr"``.
    area_id:
        If provided, restrict query to this Overpass area ID.
    bbox:
        Fallback bounding box string ``"south,west,north,east"``.
    out_body:
        Output verbosity: ``"body"`` or ``"geom"``.
    timeout:
        Overpass server-side timeout in seconds.

    Returns
    -------
    str
        Overpass QL query string.
    """
    key, _, value = tag.partition("=")
    tag_filter = f'["{key}"="{value}"]' if value and value != "*" else f'["{key}"]'

    if area_id:
        area_clause = f"area({area_id + 3_600_000_000})->.searchArea;\n  "
        spatial = "(area.searchArea)"
    else:
        area_clause = ""
        spatial = f"({bbox})"

    return (
        f"[out:json][timeout:{timeout}];\n"
        f"{area_clause}"
        f"{element_type}{tag_filter}{spatial};\n"
        f"out {out_body};\n"
        f">;\n"
        f"out skel qt;"
    )
