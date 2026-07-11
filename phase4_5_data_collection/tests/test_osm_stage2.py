"""
tests/test_osm_stage2.py
Comprehensive tests for Phase 4.5.1 Stage 2 – OSM Railway Infrastructure Collector.

Tests cover:
- Query loading from config/osm_queries.json
- Multi-tag Overpass query builder
- Cache (save / load / checksum / invalidate)
- Per-dataset output writers (report, manifest, validation)
- Schema validation
- OSM collector with mocked Overpass
- Statistics generation
- Quality report generation
- Collector report generation
- Facilities module
- All dataset modules
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_NODES = [
    {
        "id": i,
        "type": "node",
        "lat": 11.0 + i * 0.1,
        "lon": 77.0 + i * 0.1,
        "tags": {"railway": "station", "name": f"Station {i}"},
    }
    for i in range(5)
]

FAKE_WAYS = [
    {
        "id": 100 + i,
        "type": "way",
        "nodes": [1000 + i, 1001 + i, 1002 + i],
        "tags": {"railway": "rail"},
    }
    for i in range(3)
]

FAKE_OVERPASS_RESPONSE: dict[str, Any] = {
    "version": 0.6,
    "generator": "Overpass API",
    "elements": FAKE_NODES,
}

OSM_CFG = {
    "enabled": True,
    "timeout_seconds": 60,
    "retries": 1,
    "log_file": "osm.log",
    "overwrite_existing": True,
}

SOURCES: dict[str, Any] = {
    "osm": {
        "name": "OpenStreetMap",
        "license": "ODbL",
        "area_id": None,
        "bbox": "8.0,76.2,13.6,80.4",
        "region": "Tamil Nadu",
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
    }
}


# ---------------------------------------------------------------------------
# 1. Query config loading
# ---------------------------------------------------------------------------

class TestQueryConfig:
    def test_load_stations_config(self):
        from collectors.osm.utils import load_query_config
        cfg = load_query_config("stations")
        assert "tags" in cfg
        assert "railway=station" in cfg["tags"]
        assert "element_types" in cfg

    def test_load_tracks_config(self):
        from collectors.osm.utils import load_query_config
        cfg = load_query_config("tracks")
        assert "railway=rail" in cfg["tags"]

    def test_load_facilities_config(self):
        from collectors.osm.utils import load_query_config
        cfg = load_query_config("facilities")
        assert "tags" in cfg
        assert len(cfg["tags"]) > 0

    def test_missing_dataset_raises(self):
        from collectors.osm.utils import load_query_config
        with pytest.raises(KeyError, match="nonexistent"):
            load_query_config("nonexistent")

    @pytest.mark.parametrize("dataset", [
        "stations", "tracks", "platforms", "signals",
        "crossings", "bridges", "tunnels", "electrification", "facilities",
    ])
    def test_all_datasets_have_config(self, dataset):
        from collectors.osm.utils import load_query_config
        cfg = load_query_config(dataset)
        assert isinstance(cfg["tags"], list)
        assert len(cfg["tags"]) > 0
        assert isinstance(cfg["element_types"], list)


# ---------------------------------------------------------------------------
# 2. Multi-tag query builder
# ---------------------------------------------------------------------------

class TestMultiTagQueryBuilder:
    def test_basic_query_contains_tags(self):
        from collectors.osm.utils import build_multi_tag_query
        q = build_multi_tag_query(
            tags=["railway=station", "railway=halt"],
            element_types=["node"],
            area_id=None,
            bbox="8.0,76.0,13.0,80.0",
            timeout=60,
        )
        assert "[out:json]" in q
        assert '"railway"="station"' in q
        assert '"railway"="halt"' in q
        assert "8.0,76.0,13.0,80.0" in q

    def test_wildcard_tag(self):
        from collectors.osm.utils import build_multi_tag_query
        q = build_multi_tag_query(
            tags=["electrified=*"],
            element_types=["way"],
            area_id=None,
            bbox="8.0,76.0,13.0,80.0",
            timeout=60,
        )
        assert '["electrified"]' in q

    def test_area_id_included(self):
        from collectors.osm.utils import build_multi_tag_query
        q = build_multi_tag_query(
            tags=["railway=station"],
            element_types=["node"],
            area_id=184640,
            timeout=60,
        )
        assert "searchArea" in q
        assert "area(" in q

    def test_filter_railway(self):
        from collectors.osm.utils import build_multi_tag_query
        q = build_multi_tag_query(
            tags=["bridge=yes"],
            element_types=["way"],
            area_id=None,
            bbox="8.0,76.0,13.0,80.0",
            filter_railway=True,
            timeout=60,
        )
        assert "[railway]" in q

    def test_multiple_element_types(self):
        from collectors.osm.utils import build_multi_tag_query
        q = build_multi_tag_query(
            tags=["railway=platform"],
            element_types=["node", "way", "relation"],
            area_id=None,
            bbox="8.0,76.0,13.0,80.0",
            timeout=60,
        )
        assert "node" in q
        assert "way" in q
        assert "relation" in q

    def test_timeout_in_query(self):
        from collectors.osm.utils import build_multi_tag_query
        q = build_multi_tag_query(
            tags=["railway=rail"],
            element_types=["way"],
            area_id=None,
            bbox="8.0,76.0,13.0,80.0",
            timeout=120,
        )
        assert "[timeout:120]" in q


# ---------------------------------------------------------------------------
# 3. Cache
# ---------------------------------------------------------------------------

class TestCache:
    def test_save_and_load(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path)

        payload = {"elements": FAKE_NODES, "meta": {}}
        checksum = u.save_to_cache("test_ds", payload)
        assert checksum  # non-empty

        result = u.load_from_cache("test_ds")
        assert result is not None
        records, loaded_checksum = result
        assert len(records) == len(FAKE_NODES)
        assert loaded_checksum == checksum

    def test_cache_miss_returns_none(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path)
        assert u.load_from_cache("never_cached") is None

    def test_checksum_mismatch_invalidates(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path)

        payload = {"elements": FAKE_NODES}
        u.save_to_cache("corrupt_ds", payload)

        # Corrupt the data file
        data_path = tmp_path / "corrupt_ds.json"
        data_path.write_text("CORRUPTED DATA")

        result = u.load_from_cache("corrupt_ds")
        assert result is None  # invalidated due to checksum mismatch

    def test_cache_empty_dataset(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path)

        payload = {"elements": []}
        u.save_to_cache("empty_ds", payload)
        result = u.load_from_cache("empty_ds")
        assert result is not None
        records, _ = result
        assert records == []


# ---------------------------------------------------------------------------
# 4. Per-dataset output writers
# ---------------------------------------------------------------------------

class TestDatasetOutputs:
    def test_writes_three_files(self, tmp_path):
        from collectors.osm.utils import write_dataset_outputs, DatasetReport
        report = DatasetReport(
            dataset="stations",
            record_count=5,
            validation_passed=True,
        )
        write_dataset_outputs(
            dataset="stations",
            records=FAKE_NODES,
            report=report,
            raw_dir=tmp_path,
            checksum="abc123",
        )
        ds_dir = tmp_path / "stations"
        assert (ds_dir / "report.json").exists()
        assert (ds_dir / "manifest.json").exists()
        assert (ds_dir / "validation.json").exists()

    def test_validation_json_content(self, tmp_path):
        from collectors.osm.utils import write_dataset_outputs, DatasetReport
        # Include a duplicate id
        records = FAKE_NODES + [FAKE_NODES[0]]
        report = DatasetReport(dataset="stations", record_count=len(records))
        write_dataset_outputs(dataset="stations", records=records, report=report, raw_dir=tmp_path)

        val = json.loads((tmp_path / "stations" / "validation.json").read_text())
        assert val["duplicate_count"] > 0
        assert "record_count" in val
        assert "passed" in val

    def test_manifest_json_content(self, tmp_path):
        from collectors.osm.utils import write_dataset_outputs, DatasetReport
        report = DatasetReport(dataset="tracks", record_count=3, validation_passed=True)
        write_dataset_outputs(dataset="tracks", records=FAKE_WAYS, report=report, raw_dir=tmp_path, checksum="sha256hex")

        mf = json.loads((tmp_path / "tracks" / "manifest.json").read_text())
        assert mf["dataset"] == "tracks"
        assert mf["record_count"] == 3
        assert mf["checksum_sha256"] == "sha256hex"
        assert mf["validation_passed"] is True

    def test_report_json_content(self, tmp_path):
        from collectors.osm.utils import write_dataset_outputs, DatasetReport
        report = DatasetReport(
            dataset="signals",
            record_count=10,
            download_duration_seconds=2.5,
            coverage_summary={"by_type": {"node": 10}},
        )
        write_dataset_outputs(dataset="signals", records=FAKE_NODES, report=report, raw_dir=tmp_path)

        rpt = json.loads((tmp_path / "signals" / "report.json").read_text())
        assert rpt["dataset"] == "signals"
        assert rpt["record_count"] == 10
        assert rpt["download_duration_seconds"] == 2.5


# ---------------------------------------------------------------------------
# 5. Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_valid_station_passes(self):
        from collectors.osm.utils import validate_against_schema
        errors = validate_against_schema("stations", FAKE_NODES)
        assert errors == []  # All nodes have id and type

    def test_unknown_dataset_no_error(self):
        from collectors.osm.utils import validate_against_schema
        errors = validate_against_schema("nonexistent_dataset", FAKE_NODES)
        assert errors == []  # No schema → no errors

    def test_invalid_record_caught(self):
        from collectors.osm.utils import validate_against_schema
        bad_records = [{"lat": 11.0, "lon": 77.0, "tags": {}}]  # missing id, type
        errors = validate_against_schema("stations", bad_records)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# 6. Individual collector modules
# ---------------------------------------------------------------------------

MOCK_TARGET = "collectors.osm._base.run_overpass_query"


def _mock_overpass(elements: list[dict] | None = None) -> MagicMock:
    response = {"elements": elements if elements is not None else FAKE_NODES}
    return MagicMock(return_value=response)


class TestStationsModule:
    def test_collect_returns_records_and_validation(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import stations
            records, validation = stations.collect(tmp_path, overwrite=True)
        assert len(records) == 5
        assert validation.passed

    def test_creates_subdirectory(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import stations
            stations.collect(tmp_path, overwrite=True)
        assert (tmp_path / "stations" / "stations.json").exists()


class TestTracksModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass(FAKE_WAYS)):
            from collectors.osm import tracks
            records, validation = tracks.collect(tmp_path, overwrite=True)
        assert len(records) == 3


class TestPlatformsModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import platforms
            records, _ = platforms.collect(tmp_path, overwrite=True)
        assert len(records) > 0


class TestSignalsModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import signals
            records, _ = signals.collect(tmp_path, overwrite=True)
        assert isinstance(records, list)


class TestCrossingsModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import crossings
            records, _ = crossings.collect(tmp_path, overwrite=True)
        assert isinstance(records, list)


class TestBridgesModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass(FAKE_WAYS)):
            from collectors.osm import bridges
            records, _ = bridges.collect(tmp_path, overwrite=True)
        assert isinstance(records, list)


class TestTunnelsModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass(FAKE_WAYS)):
            from collectors.osm import tunnels
            records, _ = tunnels.collect(tmp_path, overwrite=True)
        assert isinstance(records, list)


class TestElectrificationModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import electrification
            records, _ = electrification.collect(tmp_path, overwrite=True)
        assert isinstance(records, list)


class TestFacilitiesModule:
    def test_collect(self, tmp_path):
        with patch(MOCK_TARGET, _mock_overpass()):
            from collectors.osm import facilities
            records, _ = facilities.collect(tmp_path, overwrite=True)
        assert isinstance(records, list)

    def test_facilities_dataset_name(self):
        from collectors.osm import facilities
        assert facilities.DATASET_NAME == "facilities"


# ---------------------------------------------------------------------------
# 7. OSM Collector (integration)
# ---------------------------------------------------------------------------

class TestOSMCollector:
    def _make_collector(self, tmp_path: Path):
        from collectors.osm import OSMCollector
        c = OSMCollector(OSM_CFG, SOURCES)
        c._raw_dir = tmp_path / "raw" / "osm"
        c._processed_dir = tmp_path / "processed" / "osm"
        c._root = tmp_path
        c._raw_dir.mkdir(parents=True, exist_ok=True)
        c._processed_dir.mkdir(parents=True, exist_ok=True)
        return c

    def test_collect_returns_result(self, tmp_path):
        from collectors import CollectorResult
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            result = c.collect()
        assert isinstance(result, CollectorResult)
        assert result.collector_name == "osm"

    def test_collect_all_nine_datasets(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            result = c.collect()
        assert result.datasets_collected == 9

    def test_statistics_file_created(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        assert (tmp_path / "statistics" / "osm_statistics.json").exists()

    def test_quality_file_created(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        assert (tmp_path / "quality" / "osm_quality.json").exists()

    def test_collector_report_created(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        assert (tmp_path / "reports" / "osm_report.json").exists()

    def test_statistics_content(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        stats = json.loads((tmp_path / "statistics" / "osm_statistics.json").read_text())
        assert "total_railway_objects" in stats
        assert "stations" in stats
        assert "tracks" in stats
        assert "by_dataset" in stats
        assert stats["region"] == "Tamil Nadu"

    def test_quality_report_content(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        q = json.loads((tmp_path / "quality" / "osm_quality.json").read_text())
        assert "overall_quality_score" in q
        assert "duplicate_count" in q
        assert "missing_coordinates_count" in q
        assert isinstance(q["overall_quality_score"], float)

    def test_collector_report_content(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        rpt = json.loads((tmp_path / "reports" / "osm_report.json").read_text())
        assert "collector_version" in rpt
        assert "runtime_seconds" in rpt
        assert "coverage_percentage" in rpt
        assert "quality_score" in rpt
        assert rpt["region"] == "Tamil Nadu"

    def test_disabled_dataset_skipped(self, tmp_path):
        sources = {
            "osm": {
                **SOURCES["osm"],
                "datasets": {
                    **SOURCES["osm"]["datasets"],
                    "facilities": {"enabled": False},
                },
            }
        }
        from collectors.osm import OSMCollector
        c = OSMCollector(OSM_CFG, sources)
        c._raw_dir = tmp_path / "raw" / "osm"
        c._processed_dir = tmp_path / "processed" / "osm"
        c._root = tmp_path
        c._raw_dir.mkdir(parents=True, exist_ok=True)
        c._processed_dir.mkdir(parents=True, exist_ok=True)

        with patch(MOCK_TARGET, _mock_overpass()):
            result = c.collect()
        assert result.datasets_collected == 8  # facilities skipped

    def test_overpass_failure_handled(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, side_effect=RuntimeError("Overpass down")):
            result = c.collect()
        # Should not raise, but should have errors
        assert len(result.errors) > 0

    def test_per_dataset_subdirs_created(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        for ds in ["stations", "tracks", "platforms", "signals",
                   "crossings", "bridges", "tunnels", "electrification", "facilities"]:
            ds_dir = tmp_path / "raw" / "osm" / ds
            assert ds_dir.exists(), f"Missing subdir for {ds}"

    def test_per_dataset_json_created(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        for ds in ["stations", "tracks"]:
            assert (tmp_path / "raw" / "osm" / ds / f"{ds}.json").exists()

    def test_record_count_matches(self, tmp_path):
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass(FAKE_NODES)):
            result = c.collect()
        # 5 nodes × 9 datasets
        assert result.total_records == 5 * 9


# ---------------------------------------------------------------------------
# 8. Downloader (unit)
# ---------------------------------------------------------------------------

class TestDownloader:
    def test_build_railway_query_basic(self):
        from collectors.osm.downloader import build_railway_query
        q = build_railway_query("railway=station", element_type="node", timeout=60)
        assert '"railway"="station"' in q
        assert "[out:json]" in q
        assert "node" in q

    def test_build_railway_query_wildcard(self):
        from collectors.osm.downloader import build_railway_query
        q = build_railway_query("electrified=*", element_type="nwr", timeout=60)
        assert '["electrified"]' in q

    def test_build_railway_query_area_id(self):
        from collectors.osm.downloader import build_railway_query
        q = build_railway_query("railway=station", area_id=184640, timeout=60)
        assert "searchArea" in q

    def test_run_overpass_query_success(self):
        from collectors.osm.downloader import run_overpass_query
        fake_resp = MagicMock()
        fake_resp.json.return_value = FAKE_OVERPASS_RESPONSE
        fake_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=fake_resp):
            data = run_overpass_query("dummy query", timeout=10, retries=1)
        assert "elements" in data
        assert len(data["elements"]) == 5

    def test_run_overpass_query_retries_and_fails(self):
        from collectors.osm.downloader import run_overpass_query
        import requests
        with patch("requests.post", side_effect=requests.RequestException("timeout")):
            with pytest.raises(RuntimeError, match="failed after"):
                run_overpass_query("query", timeout=1, retries=2)


# ---------------------------------------------------------------------------
# 9. Railway tags reference
# ---------------------------------------------------------------------------

class TestRailwayTagsReference:
    def test_reference_file_exists(self):
        from pathlib import Path
        ref = Path(__file__).resolve().parents[1] / "reference" / "railway_tags.json"
        assert ref.exists()

    def test_reference_has_categories(self):
        from pathlib import Path
        import json
        ref = Path(__file__).resolve().parents[1] / "reference" / "railway_tags.json"
        data = json.loads(ref.read_text())
        for cat in ["stations", "tracks", "platforms", "signals", "crossings", "bridges", "tunnels", "electrification", "facilities"]:
            assert cat in data, f"Missing category: {cat}"

    def test_reference_tags_are_strings(self):
        from pathlib import Path
        import json
        ref = Path(__file__).resolve().parents[1] / "reference" / "railway_tags.json"
        data = json.loads(ref.read_text())
        for cat, block in data.items():
            if cat.startswith("_"):
                continue
            assert "tags" in block, f"Category '{cat}' missing 'tags'"
            for k, v in block["tags"].items():
                assert isinstance(k, str) and isinstance(v, str)


# ---------------------------------------------------------------------------
# 10. JSON Schemas
# ---------------------------------------------------------------------------

class TestSchemas:
    @pytest.mark.parametrize("schema_file", [
        "station_schema.json",
        "track_schema.json",
        "platform_schema.json",
        "signal_schema.json",
        "crossing_schema.json",
        "bridge_schema.json",
        "tunnel_schema.json",
        "facility_schema.json",
    ])
    def test_schema_file_exists(self, schema_file):
        from pathlib import Path
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "osm" / schema_file
        assert schema_path.exists(), f"Schema file missing: {schema_file}"

    @pytest.mark.parametrize("schema_file", [
        "station_schema.json",
        "track_schema.json",
    ])
    def test_schema_is_valid_json(self, schema_file):
        from pathlib import Path
        import json
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "osm" / schema_file
        data = json.loads(schema_path.read_text())
        assert "$schema" in data or "type" in data

    def test_station_schema_validates_node(self):
        pytest.importorskip("jsonschema")
        import jsonschema
        from pathlib import Path
        import json
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "osm" / "station_schema.json"
        schema = json.loads(schema_path.read_text())
        record = {"id": 1, "type": "node", "lat": 11.0, "lon": 77.0, "tags": {"railway": "station"}}
        jsonschema.validate(instance=record, schema=schema)  # should not raise


# ---------------------------------------------------------------------------
# 11. Cache directory
# ---------------------------------------------------------------------------

class TestCacheDirectory:
    def test_cache_dir_created_automatically(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        cache_dir = tmp_path / "cache" / "osm"
        monkeypatch.setattr(u, "_CACHE_DIR", cache_dir)
        # The directory is created on save
        u.save_to_cache("auto_dir_test", {"elements": []})
        assert cache_dir.exists()

    def test_cache_meta_saved(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path)
        u.save_to_cache("meta_test", {"elements": FAKE_NODES[:2]})
        meta_path = tmp_path / "meta_test.cache.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["record_count"] == 2
        assert "checksum" in meta
        assert "cached_at" in meta


# ---------------------------------------------------------------------------
# 12. Region configurability
# ---------------------------------------------------------------------------

class TestRegionConfig:
    def test_region_not_hardcoded_in_collector(self, tmp_path):
        """Collector must read region from config, not hardcode Tamil Nadu."""
        kerala_sources = {
            "osm": {
                "name": "OpenStreetMap",
                "license": "ODbL",
                "area_id": None,
                "bbox": "8.0,74.0,12.5,77.5",
                "region": "Kerala",
                "datasets": {
                    "stations": {"enabled": True},
                },
            }
        }
        from collectors.osm import OSMCollector
        c = OSMCollector(OSM_CFG, kerala_sources)
        c._raw_dir = tmp_path / "raw" / "osm"
        c._processed_dir = tmp_path / "processed" / "osm"
        c._root = tmp_path
        c._raw_dir.mkdir(parents=True, exist_ok=True)
        c._processed_dir.mkdir(parents=True, exist_ok=True)

        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()

        stats = json.loads((tmp_path / "statistics" / "osm_statistics.json").read_text())
        assert stats["region"] == "Kerala"

    def test_bbox_passed_to_query(self):
        from collectors.osm.utils import build_multi_tag_query
        kerala_bbox = "8.0,74.0,12.5,77.5"
        q = build_multi_tag_query(
            tags=["railway=station"],
            element_types=["node"],
            area_id=None,
            bbox=kerala_bbox,
            timeout=60,
        )
        assert kerala_bbox in q
