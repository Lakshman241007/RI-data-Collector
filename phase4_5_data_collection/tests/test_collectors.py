"""
tests/test_collectors.py
Unit tests for all four collector implementations.
Uses mocking to avoid real network calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from collectors import CollectorResult
from collectors.osm import OSMCollector
from collectors.official import OfficialCollector
from collectors.public import PublicCollector
from collectors.metadata import MetadataCollector


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

OSM_CFG = {"enabled": True, "timeout_seconds": 60, "retries": 1, "log_file": "osm.log", "overwrite_existing": True}
OFF_CFG = {"enabled": True, "timeout_seconds": 60, "retries": 1, "log_file": "official.log", "overwrite_existing": True}
PUB_CFG = {"enabled": True, "timeout_seconds": 60, "retries": 1, "log_file": "public.log", "overwrite_existing": True}
META_CFG = {"enabled": True, "timeout_seconds": 60, "retries": 1, "log_file": "metadata.log", "overwrite_existing": True}

SOURCES: dict[str, Any] = {
    "osm": {
        "name": "OpenStreetMap",
        "license": "ODbL",
        "area_id": None,
        "datasets": {
            "stations":        {"enabled": True, "tag": "railway=station"},
            "tracks":          {"enabled": True, "tag": "railway=rail"},
            "platforms":       {"enabled": True, "tag": "railway=platform"},
            "signals":         {"enabled": True, "tag": "railway=signal"},
            "crossings":       {"enabled": True, "tag": "railway=crossing"},
            "bridges":         {"enabled": True, "tag": "bridge=yes"},
            "tunnels":         {"enabled": True, "tag": "tunnel=yes"},
            "electrification": {"enabled": True, "tag": "electrified=*"},
            "facilities":      {"enabled": True, "tag": "railway=yard"},
        },
    },
    "official": {
        "name": "IR Official",
        "license": "GODL-India",
        "datasets": {
            "station_master":   {"enabled": True, "url": "https://example.com/station_master.json"},
            "station_codes":    {"enabled": True, "url": "https://example.com/station_codes.json"},
            "railway_zones":    {"enabled": True, "url": "https://example.com/railway_zones.json"},
            "railway_divisions":{"enabled": True, "url": "https://example.com/railway_divisions.json"},
            "train_master":     {"enabled": True, "url": "https://example.com/train_master.json"},
        },
    },
    "public": {
        "name": "Public Datasets",
        "license": "CC0",
        "datasets": {
            "trains":      {"enabled": True, "url": "https://example.com/trains.json"},
            "timetables":  {"enabled": True, "url": "https://example.com/timetables.json"},
            "facilities":  {"enabled": True, "url": "https://example.com/facilities.json"},
            "elevations":  {"enabled": True, "url": "https://example.com/elevations.json"},
        },
    },
    "metadata": {
        "name": "Metadata",
        "license": "CC BY-SA 4.0",
        "datasets": {
            "aliases":         {"enabled": True},
            "wikipedia":       {"enabled": True, "api": "https://en.wikipedia.org/w/api.php"},
            "station_history": {"enabled": True},
            "amenities":       {"enabled": True},
        },
    },
}

_FAKE_OSM_DATA = {
    "elements": [
        {"id": i, "type": "node", "lat": 28.0 + i * 0.1, "lon": 77.0 + i * 0.1,
         "tags": {"railway": "station", "name": f"Station {i}"}}
        for i in range(5)
    ]
}

_FAKE_JSON_RECORDS = [
    {"id": str(i), "name": f"Record {i}", "code": f"C{i:03d}"}
    for i in range(3)
]


# ---------------------------------------------------------------------------
# OSM Collector
# ---------------------------------------------------------------------------

class TestOSMCollector:
    def _make_collector(self, tmp_path: Path) -> OSMCollector:
        c = OSMCollector(OSM_CFG, SOURCES)
        c._raw_dir = tmp_path / "raw" / "osm"
        c._raw_dir.mkdir(parents=True)
        c._processed_dir = tmp_path / "processed" / "osm"
        c._processed_dir.mkdir(parents=True)
        return c

    @patch("collectors.osm._base.run_overpass_query", return_value=_FAKE_OSM_DATA)
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/osm_manifest.json"))
    def test_collect_returns_result(self, mock_save, mock_query, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        result = collector.collect()
        assert isinstance(result, CollectorResult)
        assert result.collector_name == "osm"
        assert result.datasets_collected > 0

    @patch("collectors.osm._base.run_overpass_query", return_value=_FAKE_OSM_DATA)
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/osm_manifest.json"))
    def test_stations_saved_to_raw(self, mock_save, mock_query, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        collector.collect()
        # Stage 2: stations are saved in raw/osm/stations/stations.json
        stations_file = collector._raw_dir / "stations" / "stations.json"
        assert stations_file.exists()
        data = json.loads(stations_file.read_text())
        assert "elements" in data
        assert len(data["elements"]) == 5


# ---------------------------------------------------------------------------
# Official Collector
# ---------------------------------------------------------------------------

class TestOfficialCollector:
    def _make_collector(self, tmp_path: Path) -> OfficialCollector:
        c = OfficialCollector(OFF_CFG, SOURCES)
        c._raw_dir = tmp_path / "raw" / "official"
        c._raw_dir.mkdir(parents=True)
        c._processed_dir = tmp_path / "processed" / "official"
        c._processed_dir.mkdir(parents=True)
        return c

    @patch("collectors.official.downloader.fetch_url_json", return_value={"records": _FAKE_JSON_RECORDS})
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/official_manifest.json"))
    def test_collect_returns_result(self, mock_save, mock_fetch, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        result = collector.collect()
        assert isinstance(result, CollectorResult)
        assert result.collector_name == "official"
        assert result.datasets_collected == 5

    @patch("collectors.official.downloader.fetch_url_json", side_effect=Exception("Network error"))
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/official_manifest.json"))
    def test_collect_handles_download_failure(self, mock_save, mock_fetch, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        # Should not raise – errors are captured in result
        result = collector.collect()
        assert isinstance(result, CollectorResult)


# ---------------------------------------------------------------------------
# Public Collector
# ---------------------------------------------------------------------------

class TestPublicCollector:
    def _make_collector(self, tmp_path: Path) -> PublicCollector:
        c = PublicCollector(PUB_CFG, SOURCES)
        c._raw_dir = tmp_path / "raw" / "public"
        c._raw_dir.mkdir(parents=True)
        c._processed_dir = tmp_path / "processed" / "public"
        c._processed_dir.mkdir(parents=True)
        return c

    @patch("collectors.public.downloader.fetch_json_dataset", return_value=_FAKE_JSON_RECORDS)
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/public_manifest.json"))
    def test_collect_returns_result(self, mock_save, mock_fetch, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        result = collector.collect()
        assert isinstance(result, CollectorResult)
        assert result.collector_name == "public"
        assert result.datasets_collected == 4
        assert result.total_records == 4 * 3  # 4 datasets × 3 records each


# ---------------------------------------------------------------------------
# Metadata Collector
# ---------------------------------------------------------------------------

class TestMetadataCollector:
    def _make_collector(self, tmp_path: Path) -> MetadataCollector:
        c = MetadataCollector(META_CFG, SOURCES)
        c._raw_dir = tmp_path / "raw" / "metadata"
        c._raw_dir.mkdir(parents=True)
        c._processed_dir = tmp_path / "processed" / "metadata"
        c._processed_dir.mkdir(parents=True)
        return c

    @patch("collectors.metadata.wikipedia.fetch_wikipedia_extracts", return_value=[
        {"pageid": 1, "title": "New Delhi railway station", "extract": "A busy station.", "fullurl": ""}
    ])
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/metadata_manifest.json"))
    def test_collect_returns_result(self, mock_save, mock_wiki, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        result = collector.collect()
        assert isinstance(result, CollectorResult)
        assert result.collector_name == "metadata"
        assert result.datasets_collected == 4

    @patch("collectors.metadata.wikipedia.fetch_wikipedia_extracts", return_value=[
        {"pageid": 1, "title": "New Delhi railway station", "extract": ".", "fullurl": ""}
    ])
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/metadata_manifest.json"))
    def test_aliases_dataset_generated(self, mock_save, mock_wiki, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        collector.collect()
        aliases_file = collector._raw_dir / "aliases.json"
        assert aliases_file.exists()
        data = json.loads(aliases_file.read_text())
        assert "records" in data
        assert len(data["records"]) > 0

    @patch("collectors.metadata.wikipedia.fetch_wikipedia_extracts", return_value=[
        {"pageid": 1, "title": "New Delhi railway station", "extract": ".", "fullurl": ""}
    ])
    @patch("common.manifest.CollectorManifest.save", return_value=Path("/tmp/metadata_manifest.json"))
    def test_station_history_dataset_generated(self, mock_save, mock_wiki, tmp_path: Path) -> None:
        collector = self._make_collector(tmp_path)
        collector.collect()
        history_file = collector._raw_dir / "station_history.json"
        assert history_file.exists()
        data = json.loads(history_file.read_text())
        assert "records" in data
        assert any(r.get("station_code") == "NDLS" for r in data["records"])
