"""
tests/test_loader.py
--------------------
Unit tests for graph.dataset_loader.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from graph.dataset_loader import load_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_dataset(tmp_path: Path, records: list) -> Path:
    p = tmp_path / "dataset.json"
    p.write_text(json.dumps(records), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadDataset:
    def test_list_root_format(self, tmp_path):
        records = [
            {
                "id": "100",
                "type": "node",
                "lat": 13.08,
                "lon": 80.27,
                "tags": {"railway": "station", "name": "Chennai Central"},
            }
        ]
        path = _write_dataset(tmp_path, records)
        result = load_dataset(path)
        assert len(result) == 1
        assert result[0].osm_id == "100"
        assert result[0].railway == "station"

    def test_elements_root_format(self, tmp_path):
        records = {
            "elements": [
                {
                    "id": "200",
                    "type": "way",
                    "tags": {"railway": "rail"},
                    "geometry": [{"lat": 13.08, "lon": 80.27}, {"lat": 13.09, "lon": 80.28}],
                }
            ]
        }
        p = tmp_path / "dataset.json"
        p.write_text(json.dumps(records), encoding="utf-8")
        result = load_dataset(p)
        assert len(result) == 1
        assert result[0].railway == "rail"

    def test_record_without_railway_tag_is_skipped(self, tmp_path):
        records = [
            {"id": "300", "type": "node", "lat": 0.0, "lon": 0.0, "tags": {"amenity": "cafe"}}
        ]
        path = _write_dataset(tmp_path, records)
        result = load_dataset(path)
        assert result == []

    def test_non_dict_record_is_skipped(self, tmp_path):
        records = [
            {"id": "1", "type": "node", "lat": 13.0, "lon": 80.0, "tags": {"railway": "station"}},
            "not-a-dict",
        ]
        path = _write_dataset(tmp_path, records)
        result = load_dataset(path)
        assert len(result) == 1

    def test_geometry_normalisation_from_dicts(self, tmp_path):
        records = [
            {
                "id": "400",
                "type": "way",
                "tags": {"railway": "rail"},
                "geometry": [
                    {"lat": 13.0, "lon": 80.0},
                    {"lat": 13.1, "lon": 80.1},
                ],
            }
        ]
        path = _write_dataset(tmp_path, records)
        result = load_dataset(path)
        assert len(result) == 1
        assert result[0].geometry == [[80.0, 13.0], [80.1, 13.1]]

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_dataset(Path("/nonexistent/path/dataset.json"))

    def test_osm_id_coerced_to_string(self, tmp_path):
        records = [
            {"id": 9999, "type": "node", "lat": 1.0, "lon": 1.0, "tags": {"railway": "halt"}}
        ]
        path = _write_dataset(tmp_path, records)
        result = load_dataset(path)
        assert result[0].osm_id == "9999"
        assert isinstance(result[0].osm_id, str)

    def test_empty_list_returns_empty(self, tmp_path):
        path = _write_dataset(tmp_path, [])
        result = load_dataset(path)
        assert result == []
