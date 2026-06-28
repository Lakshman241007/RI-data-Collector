"""
extractor.geofabrik
====================

Downloads the GeoFabrik India OSM PBF extract.

GeoFabrik is a static file host, not an API: this module is responsible
only for getting ``india-latest.osm.pbf`` onto local disk efficiently
(skip if already complete, resume if partial), with a progress bar.
Parsing the file is handled by ``extractor.pbf_reader``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests
from tqdm import tqdm

from extractor.config import GeoFabrikConfig

logger = logging.getLogger("geofabrik")


class GeofabrikError(Exception):
    """Raised when the GeoFabrik extract cannot be downloaded."""


class GeofabrikDownloader:
    def __init__(self, config: GeoFabrikConfig):
        self.config = config

    @property
    def target_path(self) -> Path:
        return Path(self.config.download_dir) / self.config.filename

    # ------------------------------------------------------------------
    def _remote_size(self) -> int:
        """Best-effort lookup of the remote file size via HEAD request."""
        response = requests.head(self.config.url, allow_redirects=True, timeout=30)
        response.raise_for_status()
        return int(response.headers.get("Content-Length", 0))

    # ------------------------------------------------------------------
    def download(self, force: bool = False) -> Path:
        """Download the extract if missing/incomplete; skip if already done."""
        target = self.target_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists() and not force:
            local_size = target.stat().st_size
            remote_size = None
            try:
                remote_size = self._remote_size()
            except requests.RequestException as exc:
                logger.warning(
                    "Could not verify remote file size (%s); assuming local copy is complete", exc
                )

            if remote_size is None or local_size >= remote_size > 0:
                logger.info("GeoFabrik extract already present, skipping download: %s", target)
                return target

            logger.info(
                "Partial download detected (%s/%s bytes) — resuming", local_size, remote_size
            )
            return self._stream_download(target, resume_from=local_size)

        return self._stream_download(target, resume_from=0)

    # ------------------------------------------------------------------
    def _stream_download(self, target: Path, resume_from: int = 0) -> Path:
        headers = {}
        mode = "wb"
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
            mode = "ab"

        logger.info("Downloading GeoFabrik extract from %s", self.config.url)
        try:
            with requests.get(
                self.config.url, headers=headers, stream=True, timeout=60
            ) as response:
                if resume_from > 0 and response.status_code == 416:
                    logger.info("Range not satisfiable — file is already complete: %s", target)
                    return target

                response.raise_for_status()

                content_length = int(response.headers.get("Content-Length", 0))
                total = (content_length + resume_from) if content_length else None

                with target.open(mode) as handle, tqdm(
                    total=total,
                    initial=resume_from,
                    unit="B",
                    unit_scale=True,
                    desc=target.name,
                ) as progress:
                    for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                        if chunk:
                            handle.write(chunk)
                            progress.update(len(chunk))

        except requests.RequestException as exc:
            raise GeofabrikError(f"Failed to download GeoFabrik extract: {exc}") from exc

        logger.info("GeoFabrik download complete: %s", target)
        return target
