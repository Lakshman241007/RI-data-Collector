"""
collectors/metadata/downloader.py
Wikipedia API client and generic URL fetcher for metadata collection.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.downloader import Downloader, DownloadError
from common.logger import get_logger

_log = get_logger("metadata.downloader", "metadata.log")

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# Sample railway station article titles used to bootstrap metadata
SEED_STATION_ARTICLES = [
    "New Delhi railway station",
    "Mumbai Central railway station",
    "Chennai Central railway station",
    "Howrah Junction railway station",
    "Bangalore City Junction railway station",
    "Secunderabad Junction railway station",
    "Pune Junction railway station",
    "Ahmedabad Junction railway station",
    "Jaipur Junction railway station",
    "Lucknow Charbagh railway station",
]


def fetch_wikipedia_extracts(
    titles: list[str],
    dest: Path,
    *,
    api_url: str = WIKIPEDIA_API,
    timeout: int = 60,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    """
    Fetch Wikipedia page extracts for a list of article *titles*.

    Returns a list of article dicts with keys: ``pageid``, ``title``,
    ``extract``.
    """
    if not overwrite and dest.exists() and dest.stat().st_size > 0:
        _log.info("Cache hit – %s", dest.name)
        with dest.open(encoding="utf-8") as fh:
            return json.load(fh).get("articles", [])

    downloader = Downloader(timeout=timeout)
    articles: list[dict[str, Any]] = []
    # Wikipedia API allows up to 50 titles per request
    chunk_size = 50
    try:
        for i in range(0, len(titles), chunk_size):
            batch = titles[i : i + chunk_size]
            params = {
                "action": "query",
                "format": "json",
                "titles": "|".join(batch),
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "inprop": "url",
            }
            _log.debug("Wikipedia query batch %d-%d", i, i + len(batch))
            resp = downloader.get_json(api_url, params=params)
            pages = resp.get("query", {}).get("pages", {})
            for page in pages.values():
                if page.get("pageid", -1) > 0:
                    articles.append(
                        {
                            "pageid": page["pageid"],
                            "title": page.get("title", ""),
                            "extract": page.get("extract", "")[:2000],
                            "fullurl": page.get("fullurl", ""),
                        }
                    )
    except DownloadError as exc:
        _log.error("Wikipedia fetch failed: %s", exc)
        raise
    finally:
        downloader.close()

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        json.dump({"articles": articles}, fh, indent=2, ensure_ascii=False)
    _log.info("Saved %d Wikipedia articles → %s", len(articles), dest)
    return articles
