"""
common/downloader.py
Generic HTTP downloader with retry, timeout and progress support.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common.logger import get_logger

_log = get_logger("downloader")


class DownloadError(RuntimeError):
    """Raised when a download fails after exhausting retries."""


def _build_session(
    retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "RailwayDataCollectionHub/4.5.1 "
                "(github.com/railway-data; contact: railway-data@example.com)"
            )
        }
    )
    return session


class Downloader:
    """
    Reusable HTTP downloader for collector modules.

    Parameters
    ----------
    timeout:
        Request timeout in seconds.
    retries:
        Maximum number of retry attempts.
    """

    def __init__(self, timeout: int = 60, retries: int = 3) -> None:
        self._timeout = timeout
        self._session = _build_session(retries=retries)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_file(
        self,
        url: str,
        dest: Path,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Download *url* and write the content to *dest*.

        Parameters
        ----------
        url:
            Remote URL.
        dest:
            Local destination path.
        params:
            Optional query-string parameters.
        headers:
            Optional extra request headers.
        overwrite:
            If ``False`` and *dest* already exists, return immediately without
            re-downloading (cache hit).

        Returns
        -------
        Path
            The destination path.

        Raises
        ------
        DownloadError
            On HTTP error or IO failure.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)

        if not overwrite and dest.exists() and dest.stat().st_size > 0:
            _log.info("Cache hit – skipping download: %s", dest.name)
            return dest

        _log.info("Downloading %s → %s", url, dest)
        t0 = time.monotonic()
        try:
            response = self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=self._timeout,
                stream=True,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise DownloadError(
                f"HTTP {exc.response.status_code} downloading {url}"
            ) from exc
        except requests.RequestException as exc:
            raise DownloadError(f"Network error downloading {url}: {exc}") from exc

        try:
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
        except OSError as exc:
            raise DownloadError(f"IO error writing {dest}: {exc}") from exc

        elapsed = time.monotonic() - t0
        size_kb = dest.stat().st_size / 1024
        _log.info(
            "Downloaded %s – %.1f KB in %.2f s", dest.name, size_kb, elapsed
        )
        return dest

    def post_json(
        self,
        url: str,
        payload: Any,
        *,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """
        POST *payload* as JSON and return the parsed response body.

        Raises
        ------
        DownloadError
            On HTTP or network error.
        """
        _log.debug("POST %s", url)
        try:
            response = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            raise DownloadError(
                f"HTTP {exc.response.status_code} POSTing to {url}"
            ) from exc
        except requests.RequestException as exc:
            raise DownloadError(f"Network error POSTing to {url}: {exc}") from exc

    def get_json(
        self,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """
        GET *url* and return parsed JSON.

        Raises
        ------
        DownloadError
            On HTTP or network error.
        """
        _log.debug("GET %s params=%s", url, params)
        try:
            response = self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            raise DownloadError(
                f"HTTP {exc.response.status_code} GETting {url}"
            ) from exc
        except requests.RequestException as exc:
            raise DownloadError(f"Network error GETting {url}: {exc}") from exc

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "Downloader":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
