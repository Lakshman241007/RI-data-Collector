"""
extractor.overpass
===================

Client for the OpenStreetMap Overpass API.

Responsibilities (Phase 1 only):

* health-check the configured endpoint
* fetch every ``railway=*`` node/way/relation for Tamil Nadu, with retry
  and timeout handling
* persist the raw API response to ``raw_overpass.json``
* parse the raw response into ``RailwayObject`` instances for the
  merge stage
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from extractor.config import OverpassConfig
from extractor.models import RailwayObject

logger = logging.getLogger("overpass")

# "out body geom;" returns full tags plus coordinate geometry for ways
# and relation members, so no second lookup pass is required.
_RAILWAY_QUERY_TEMPLATE = """\
[out:json][timeout:{timeout}];
area["name"="{region}"]["boundary"="administrative"]->.searchArea;
(
  node["railway"](area.searchArea);
  way["railway"](area.searchArea);
  relation["railway"](area.searchArea);
);
out body geom;
"""

_HEALTH_CHECK_QUERY = """
[out:json][timeout:10];
node(1);
out;
"""


class OverpassError(Exception):
    """Raised when the Overpass API cannot be reached or parsed."""


class OverpassClient:
    def __init__(self, config: OverpassConfig, session: Optional[requests.Session] = None):
        self.config = config
        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        """Lightweight request to confirm the endpoint is reachable."""
        try:
            response = self.session.post(
                self.config.endpoint,
                data=_HEALTH_CHECK_QUERY,
                headers={
                    "Content-Type": "text/plain",
                    "User-Agent": self.config.user_agent,
                    },
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Overpass health check passed (status=%s)", response.status_code)
            return True
        except requests.RequestException as exc:
            logger.error("Overpass health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------
    def build_query(self) -> str:
        return _RAILWAY_QUERY_TEMPLATE.format(
            timeout=self.config.timeout,
            region=self.config.region,
        )

    # ------------------------------------------------------------------
    # Fetch with retry + timeout
    # ------------------------------------------------------------------
    def fetch_railway_data(self) -> Dict[str, Any]:
        query = self.build_query()
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.config.retries + 1):
            try:
                logger.info(
                    "Requesting railway data from Overpass (attempt %s/%s)",
                    attempt, self.config.retries,
                )
                response = self.session.post(
                    self.config.endpoint,
                    data=query,
                    headers={
                        "Content-Type": "text/plain",
                        "User-Agent": self.config.user_agent,
                        },
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Overpass returned %s elements", len(data.get("elements", []))
                )
                return data
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                logger.warning("Overpass attempt %s failed: %s", attempt, exc)
                if attempt < self.config.retries:
                    sleep_seconds = self.config.retry_backoff * attempt
                    logger.info("Retrying Overpass request in %s seconds", sleep_seconds)
                    time.sleep(sleep_seconds)

        logger.error("Overpass request failed after %s attempts", self.config.retries)
        raise OverpassError(
            f"Overpass request failed after {self.config.retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    @staticmethod
    def save_raw(data: Dict[str, Any], output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        logger.info("Saved raw Overpass response to %s", output_path)

    # ------------------------------------------------------------------
    # Convenience entry point
    # ------------------------------------------------------------------
    def run(self, output_path: Path) -> Dict[str, Any]:
            logger.info("Skipping health check, requesting railway data directly.")

            data = self.fetch_railway_data()
            self.save_raw(data, output_path)
            return data


def parse_elements(data: Dict[str, Any]) -> List[RailwayObject]:
    """Convert a raw Overpass JSON payload into ``RailwayObject`` instances."""
    objects: List[RailwayObject] = []

    for element in data.get("elements", []):
        tags = element.get("tags", {}) or {}
        if "railway" not in tags:
            continue

        osm_type = element.get("type")
        osm_id = element.get("id")
        geometry = None

        if osm_type == "node":
            lon, lat = element.get("lon"), element.get("lat")
            geometry = [lon, lat] if lon is not None and lat is not None else None
        elif osm_type == "way":
            geometry = [
                [point.get("lon"), point.get("lat")]
                for point in element.get("geometry", []) or []
            ]
        elif osm_type == "relation":
            geometry = [
                {"type": m.get("type"), "ref": m.get("ref"), "role": m.get("role")}
                for m in element.get("members", []) or []
            ]
        else:
            logger.debug("Skipping unsupported element type: %s", osm_type)
            continue

        objects.append(
            RailwayObject(
                osm_id=osm_id,
                osm_type=osm_type,
                tags=tags,
                geometry=geometry,
                source="overpass",
                version=element.get("version"),
                timestamp=element.get("timestamp"),
            )
        )

    return objects
