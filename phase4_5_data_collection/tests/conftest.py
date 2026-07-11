"""
tests/conftest.py
Shared pytest fixtures for the Railway Data Collection Hub test suite.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture()
def tmp_raw(tmp_path: Path) -> Path:
    """Return a temporary raw data directory."""
    d = tmp_path / "raw"
    d.mkdir()
    return d


@pytest.fixture()
def sample_osm_json(tmp_path: Path) -> Path:
    """Write a minimal OSM-style JSON file and return its path."""
    data = {
        "meta": {"dataset": "stations", "collected_at": "2024-01-01T00:00:00+00:00", "record_count": 2},
        "elements": [
            {"id": 1, "type": "node", "lat": 28.6, "lon": 77.2, "tags": {"railway": "station", "name": "New Delhi"}},
            {"id": 2, "type": "node", "lat": 19.0, "lon": 72.8, "tags": {"railway": "station", "name": "Mumbai Central"}},
        ],
    }
    path = tmp_path / "stations.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def sample_records() -> list[dict]:
    return [
        {"id": "1", "name": "Record A", "code": "RA"},
        {"id": "2", "name": "Record B", "code": "RB"},
        {"id": "3", "name": "Record C", "code": "RC"},
    ]


@pytest.fixture()
def project_root() -> Path:
    return _ROOT
