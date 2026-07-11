"""
tests/test_osm_discovery.py
Tests for Phase 4.5.1 Stage 2 final enhancement – Railway Tag Discovery Engine.

Covers:
- Tag discovery / parsing
- Coverage calculation
- Unknown ("future") tag detection
- Capability matrix generation
- Statistics extension
- Quality extension
- Discovery query construction
- Full run_discovery() flow (mocked Overpass, cache, failure handling)
- Report writers (discovery report, coverage report, capability matrix)
- Integration with OSMCollector.collect()
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures / synthetic data
# ---------------------------------------------------------------------------

KNOWN_TAGS: dict[str, str] = {
    "station": "stations",
    "halt": "stations",
    "rail": "tracks",
    "light_rail": "tracks",
    "platform": "platforms",
    "signal": "signals",
    "level_crossing": "crossings",
    "yard": "facilities",
    "siding": "facilities",
    "turntable": "facilities",
    "buffer_stop": "facilities",
    "signal_box": "facilities",
}

IMPLEMENTED_CATEGORIES = {
    "stations", "tracks", "platforms", "signals", "crossings",
    "bridges", "tunnels", "electrification", "facilities",
}


def _elements(*pairs: tuple[str, str]) -> list[dict[str, Any]]:
    """Build synthetic Overpass elements from (element_type, railway_value) pairs."""
    out = []
    for i, (etype, value) in enumerate(pairs):
        out.append({"id": i, "type": etype, "tags": {"railway": value}})
    return out


MIXED_ELEMENTS = _elements(
    ("node", "station"),
    ("node", "station"),
    ("node", "halt"),
    ("way", "rail"),
    ("way", "rail"),
    ("way", "rail"),
    ("node", "platform"),
    ("node", "future_tag_xyz"),  # unknown / future tag
)


# ---------------------------------------------------------------------------
# 1. Tag parsing / discovery
# ---------------------------------------------------------------------------

class TestParseDiscoveredTags:
    def test_counts_values_correctly(self):
        from collectors.osm.discovery import parse_discovered_tags
        discovered = parse_discovered_tags(MIXED_ELEMENTS)
        assert discovered["station"].count == 2
        assert discovered["halt"].count == 1
        assert discovered["rail"].count == 3
        assert discovered["platform"].count == 1
        assert discovered["future_tag_xyz"].count == 1

    def test_element_type_breakdown(self):
        from collectors.osm.discovery import parse_discovered_tags
        discovered = parse_discovered_tags(MIXED_ELEMENTS)
        assert discovered["station"].element_types == {"node": 2}
        assert discovered["rail"].element_types == {"way": 3}

    def test_ignores_elements_without_railway_tag(self):
        from collectors.osm.discovery import parse_discovered_tags
        elements = [{"id": 1, "type": "node", "tags": {"name": "foo"}}]
        discovered = parse_discovered_tags(elements)
        assert discovered == {}

    def test_ignores_malformed_elements(self):
        from collectors.osm.discovery import parse_discovered_tags
        discovered = parse_discovered_tags([None, "not-a-dict", {"id": 1}])  # type: ignore[list-item]
        assert discovered == {}

    def test_empty_input(self):
        from collectors.osm.discovery import parse_discovered_tags
        assert parse_discovered_tags([]) == {}

    def test_to_dict(self):
        from collectors.osm.discovery import DiscoveredTag
        tag = DiscoveredTag(value="station")
        tag.record("node")
        tag.record("node")
        d = tag.to_dict()
        assert d == {"value": "station", "count": 2, "element_types": {"node": 2}}


# ---------------------------------------------------------------------------
# 2. Coverage calculation
# ---------------------------------------------------------------------------

class TestComputeCoverage:
    def _result(self, elements):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags
        return DiscoveryResult(
            discovered_tags=parse_discovered_tags(elements),
            total_elements=len(elements),
            region="Test Region",
        )

    def test_full_coverage_when_all_known(self):
        from collectors.osm.discovery import compute_coverage
        result = self._result(_elements(("node", "station"), ("way", "rail")))
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert coverage["unsupported_tags"] == []
        assert coverage["coverage_percentage"] == 100.0

    def test_partial_coverage_with_unknown_tag(self):
        from collectors.osm.discovery import compute_coverage
        result = self._result(MIXED_ELEMENTS)
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert "future_tag_xyz" in coverage["unsupported_tags"]
        assert coverage["unsupported_count"] == 1
        assert 0.0 < coverage["coverage_percentage"] < 100.0

    def test_unused_configured_tags(self):
        from collectors.osm.discovery import compute_coverage
        result = self._result(_elements(("node", "station")))
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert "rail" in coverage["unused_configured_tags"]
        assert "yard" in coverage["unused_configured_tags"]

    def test_no_elements_full_coverage_by_definition(self):
        from collectors.osm.discovery import compute_coverage
        result = self._result([])
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert coverage["total_discovered_tags"] == 0
        assert coverage["coverage_percentage"] == 100.0

    def test_recommendations_present_for_unsupported(self):
        from collectors.osm.discovery import compute_coverage
        result = self._result(MIXED_ELEMENTS)
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert any("future_tag_xyz" in r for r in coverage["recommendations"])

    def test_occurrence_counts(self):
        from collectors.osm.discovery import compute_coverage
        result = self._result(MIXED_ELEMENTS)
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert coverage["total_tag_occurrences"] == len(MIXED_ELEMENTS)
        assert coverage["unsupported_tag_occurrences"] == 1


# ---------------------------------------------------------------------------
# 3. Unknown / future tag detection
# ---------------------------------------------------------------------------

class TestFutureTagDetection:
    def test_future_tag_classified_unsupported_not_fatal(self):
        """A brand-new OSM railway tag must be detected, counted, classified
        as unsupported, and must never raise an exception."""
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags, compute_coverage
        elements = _elements(("node", "brand_new_2027_tag"))
        result = DiscoveryResult(discovered_tags=parse_discovered_tags(elements), total_elements=1)
        coverage = compute_coverage(result, KNOWN_TAGS)  # must not raise
        assert "brand_new_2027_tag" in coverage["unsupported_tags"]

    def test_multiple_future_tags(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags, compute_coverage
        elements = _elements(("node", "alpha_future"), ("way", "beta_future"), ("node", "station"))
        result = DiscoveryResult(discovered_tags=parse_discovered_tags(elements), total_elements=3)
        coverage = compute_coverage(result, KNOWN_TAGS)
        assert set(coverage["unsupported_tags"]) == {"alpha_future", "beta_future"}


# ---------------------------------------------------------------------------
# 4. Capability matrix
# ---------------------------------------------------------------------------

class TestCapabilityMatrix:
    def _result(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags
        return DiscoveryResult(discovered_tags=parse_discovered_tags(MIXED_ELEMENTS), total_elements=len(MIXED_ELEMENTS))

    def test_known_capabilities_present(self):
        from collectors.osm.discovery import build_capability_matrix
        matrix = build_capability_matrix(self._result(), KNOWN_TAGS, IMPLEMENTED_CATEGORIES)
        for cap in ("stations", "tracks", "platforms", "signals", "crossings",
                    "bridges", "tunnels", "facilities", "electrification",
                    "yards", "sidings", "turntables", "buffer_stops",
                    "signal_boxes", "future_tags"):
            assert cap in matrix

    def test_stations_marked_implemented(self):
        from collectors.osm.discovery import build_capability_matrix
        matrix = build_capability_matrix(self._result(), KNOWN_TAGS, IMPLEMENTED_CATEGORIES)
        assert matrix["stations"]["implemented"] is True
        assert "station" in matrix["stations"]["observed_in_region"]

    def test_facilities_subcapabilities_implemented_via_facilities_module(self):
        from collectors.osm.discovery import build_capability_matrix
        matrix = build_capability_matrix(self._result(), KNOWN_TAGS, IMPLEMENTED_CATEGORIES)
        assert matrix["yards"]["implemented"] is True
        assert matrix["sidings"]["implemented"] is True

    def test_facilities_subcapabilities_not_implemented_without_facilities_module(self):
        from collectors.osm.discovery import build_capability_matrix
        reduced = IMPLEMENTED_CATEGORIES - {"facilities"}
        matrix = build_capability_matrix(self._result(), KNOWN_TAGS, reduced)
        assert matrix["yards"]["implemented"] is False

    def test_future_tags_bucket_lists_unsupported(self):
        from collectors.osm.discovery import build_capability_matrix
        matrix = build_capability_matrix(self._result(), KNOWN_TAGS, IMPLEMENTED_CATEGORIES)
        assert "future_tag_xyz" in matrix["future_tags"]["discovered_unsupported_values"]
        assert matrix["future_tags"]["implemented"] is False

    def test_non_railway_key_capabilities(self):
        from collectors.osm.discovery import build_capability_matrix
        matrix = build_capability_matrix(self._result(), KNOWN_TAGS, IMPLEMENTED_CATEGORIES)
        assert matrix["bridges"]["implemented"] is True
        assert matrix["tunnels"]["implemented"] is True
        assert matrix["electrification"]["implemented"] is True


# ---------------------------------------------------------------------------
# 5. Statistics extension
# ---------------------------------------------------------------------------

class TestDiscoveryStatisticsFields:
    def test_basic_fields(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags, discovery_statistics_fields
        result = DiscoveryResult(
            discovered_tags=parse_discovered_tags(MIXED_ELEMENTS),
            total_elements=len(MIXED_ELEMENTS),
            by_element_type={"node": 5, "way": 3},
        )
        fields = discovery_statistics_fields(result, KNOWN_TAGS)
        d = fields["discovery"]
        assert d["unique_railway_tags"] == 5
        assert d["unique_railway_object_types"] == 2
        assert d["most_common_tag"] == "rail"  # count 3 is the max
        assert d["unknown_tag_count"] == 1
        assert "tag_frequency_distribution" in d

    def test_empty_result(self):
        from collectors.osm.discovery import DiscoveryResult, discovery_statistics_fields
        result = DiscoveryResult()
        fields = discovery_statistics_fields(result, KNOWN_TAGS)
        d = fields["discovery"]
        assert d["unique_railway_tags"] == 0
        assert d["most_common_tag"] is None
        assert d["least_common_tag"] is None


# ---------------------------------------------------------------------------
# 6. Quality extension
# ---------------------------------------------------------------------------

class TestDiscoveryQualityFields:
    def test_full_coverage_yields_high_quality(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags, discovery_quality_fields
        elements = _elements(("node", "station"), ("way", "rail"))
        result = DiscoveryResult(discovered_tags=parse_discovered_tags(elements), total_elements=2)
        fields = discovery_quality_fields(result, KNOWN_TAGS)
        d = fields["discovery"]
        assert d["coverage_score"] == 100.0
        assert d["unknown_tag_penalty"] == 0.0
        assert d["overall_collector_quality"] == 100.0

    def test_unknown_tags_reduce_quality(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags, discovery_quality_fields
        result = DiscoveryResult(discovered_tags=parse_discovered_tags(MIXED_ELEMENTS), total_elements=len(MIXED_ELEMENTS))
        fields = discovery_quality_fields(result, KNOWN_TAGS)
        d = fields["discovery"]
        assert d["unknown_tag_penalty"] > 0.0
        assert d["overall_collector_quality"] < 100.0

    def test_no_elements_zero_discovery_score(self):
        from collectors.osm.discovery import DiscoveryResult, discovery_quality_fields
        result = DiscoveryResult(total_elements=0)
        fields = discovery_quality_fields(result, KNOWN_TAGS)
        assert fields["discovery"]["discovery_score"] == 0.0

    def test_quality_never_negative_or_over_100(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags, discovery_quality_fields
        # Many unsupported tags to push penalty high
        elements = [{"id": i, "type": "node", "tags": {"railway": f"weird_{i}"}} for i in range(50)]
        result = DiscoveryResult(discovered_tags=parse_discovered_tags(elements), total_elements=50)
        fields = discovery_quality_fields(result, KNOWN_TAGS)
        score = fields["discovery"]["overall_collector_quality"]
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# 7. Reference tag loading
# ---------------------------------------------------------------------------

class TestLoadReferenceTags:
    def test_loads_real_reference_file(self):
        from collectors.osm.discovery import load_reference_tags
        known = load_reference_tags()
        assert "station" in known
        assert "rail" in known
        assert known["station"] == "stations"

    def test_missing_file_returns_empty_dict(self, tmp_path):
        from collectors.osm.discovery import load_reference_tags
        known = load_reference_tags(tmp_path / "does_not_exist.json")
        assert known == {}

    def test_malformed_file_returns_empty_dict(self, tmp_path):
        from collectors.osm.discovery import load_reference_tags
        bad = tmp_path / "bad.json"
        bad.write_text("NOT JSON", encoding="utf-8")
        known = load_reference_tags(bad)
        assert known == {}


# ---------------------------------------------------------------------------
# 8. Discovery query construction
# ---------------------------------------------------------------------------

class TestBuildDiscoveryQuery:
    def test_bbox_query(self):
        from collectors.osm.discovery import build_discovery_query
        q = build_discovery_query(
            element_types=["node", "way", "relation"], area_id=None,
            bbox="8.0,76.0,13.0,80.0", timeout=60,
        )
        assert "[out:json][timeout:60]" in q
        assert '["railway"]' in q
        assert "8.0,76.0,13.0,80.0" in q
        assert "out tags;" in q
        # No value filter – discovery scans the key generically
        assert '"railway"="' not in q

    def test_area_id_query(self):
        from collectors.osm.discovery import build_discovery_query
        q = build_discovery_query(
            element_types=["node"], area_id=184640, bbox="ignored", timeout=60,
        )
        assert "searchArea" in q
        assert "area(" in q

    def test_all_element_types_included(self):
        from collectors.osm.discovery import build_discovery_query
        q = build_discovery_query(
            element_types=["node", "way", "relation"], area_id=None,
            bbox="8.0,76.0,13.0,80.0", timeout=60,
        )
        assert q.count('["railway"]') == 3


# ---------------------------------------------------------------------------
# 9. run_discovery() — full flow (mocked Overpass via collectors.osm._base)
# ---------------------------------------------------------------------------

# IMPORTANT: discovery.py calls `_base.run_overpass_query(...)` (module-attribute
# lookup at call time) specifically so that the exact same patch target used by
# the rest of the Stage 2 test suite also covers discovery, without requiring
# any real network access.
MOCK_TARGET = "collectors.osm._base.run_overpass_query"


def _mock_overpass(elements: list[dict] | None = None) -> MagicMock:
    response = {"elements": elements if elements is not None else MIXED_ELEMENTS}
    return MagicMock(return_value=response)


class TestRunDiscovery:
    def test_successful_run(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        from collectors.osm import discovery
        with patch(MOCK_TARGET, _mock_overpass()):
            result = discovery.run_discovery(tmp_path, overwrite=True, region="Test Region")
        assert result.total_elements == len(MIXED_ELEMENTS)
        assert "station" in result.discovered_tags
        assert result.region == "Test Region"

    def test_writes_raw_file(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        from collectors.osm import discovery
        with patch(MOCK_TARGET, _mock_overpass()):
            discovery.run_discovery(tmp_path, overwrite=True)
        assert (tmp_path / "discovery" / "discovery.json").exists()

    def test_never_raises_on_overpass_failure(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        from collectors.osm import discovery
        with patch(MOCK_TARGET, side_effect=RuntimeError("Overpass down")):
            result = discovery.run_discovery(tmp_path, overwrite=True)  # must not raise
        assert result.total_elements == 0
        assert result.discovered_tags == {}

    def test_cache_hit_skips_network(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        from collectors.osm import discovery

        with patch(MOCK_TARGET, _mock_overpass()) as mock_fn:
            discovery.run_discovery(tmp_path, overwrite=True)
            assert mock_fn.call_count == 1
            # Second call without overwrite should hit the cache, not the network
            discovery.run_discovery(tmp_path, overwrite=False)
            assert mock_fn.call_count == 1

    def test_continues_with_zero_records_classification(self, tmp_path, monkeypatch):
        """Unknown/future tags never abort execution."""
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        from collectors.osm import discovery
        future_elements = [{"id": 1, "type": "node", "tags": {"railway": "never_seen_before"}}]
        with patch(MOCK_TARGET, _mock_overpass(future_elements)):
            result = discovery.run_discovery(tmp_path, overwrite=True)
        assert result.discovered_tags["never_seen_before"].count == 1


# ---------------------------------------------------------------------------
# 10. Report writers
# ---------------------------------------------------------------------------

class TestReportWriters:
    def _result(self):
        from collectors.osm.discovery import DiscoveryResult, parse_discovered_tags
        return DiscoveryResult(
            discovered_tags=parse_discovered_tags(MIXED_ELEMENTS),
            total_elements=len(MIXED_ELEMENTS),
            by_element_type={"node": 5, "way": 3},
            region="Tamil Nadu",
        )

    def test_write_discovery_report(self, tmp_path):
        from collectors.osm.discovery import write_discovery_report
        path = write_discovery_report(self._result(), KNOWN_TAGS, tmp_path, "4.5.1")
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["region"] == "Tamil Nadu"
        assert data["total_railway_tags_discovered"] == 5
        assert "future_tag_xyz" in data["unknown_railway_tags"]
        assert isinstance(data["discovered_tags"], list)

    def test_write_coverage_report(self, tmp_path):
        from collectors.osm.discovery import write_coverage_report
        path = write_coverage_report(self._result(), KNOWN_TAGS, tmp_path, "4.5.1")
        assert path.exists()
        data = json.loads(path.read_text())
        assert "coverage_percentage" in data
        assert "missing_collector_support" in data
        assert "obsolete_configured_tags" in data

    def test_write_capability_matrix(self, tmp_path):
        from collectors.osm.discovery import write_capability_matrix
        path = write_capability_matrix(self._result(), KNOWN_TAGS, IMPLEMENTED_CATEGORIES, tmp_path, "4.5.1")
        assert path.exists()
        data = json.loads(path.read_text())
        assert "capabilities" in data
        assert "future_tags" in data["capabilities"]


# ---------------------------------------------------------------------------
# 11. Integration with OSMCollector.collect()
# ---------------------------------------------------------------------------

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
            "stations":        {"enabled": True},
            "tracks":          {"enabled": True},
            "platforms":       {"enabled": True},
            "signals":         {"enabled": True},
            "crossings":       {"enabled": True},
            "bridges":         {"enabled": True},
            "tunnels":         {"enabled": True},
            "electrification": {"enabled": True},
            "facilities":      {"enabled": True},
        },
    }
}


class TestOSMCollectorDiscoveryIntegration:
    def _make_collector(self, tmp_path: Path):
        from collectors.osm import OSMCollector
        c = OSMCollector(OSM_CFG, SOURCES)
        c._raw_dir = tmp_path / "raw" / "osm"
        c._processed_dir = tmp_path / "processed" / "osm"
        c._root = tmp_path
        c._raw_dir.mkdir(parents=True, exist_ok=True)
        c._processed_dir.mkdir(parents=True, exist_ok=True)
        return c

    def test_discovery_reports_created_on_full_collect(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        assert (tmp_path / "reports" / "osm_discovery_report.json").exists()
        assert (tmp_path / "coverage" / "osm_tag_coverage.json").exists()
        assert (tmp_path / "reports" / "collector_capabilities.json").exists()

    def test_statistics_extended_with_discovery_section(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        stats = json.loads((tmp_path / "statistics" / "osm_statistics.json").read_text())
        # Existing fields must still be present (backward compatibility)
        assert "total_railway_objects" in stats
        assert "stations" in stats
        # New, additive discovery section
        assert "discovery" in stats
        assert "unique_railway_tags" in stats["discovery"]

    def test_quality_extended_with_discovery_section(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            c.collect()
        quality = json.loads((tmp_path / "quality" / "osm_quality.json").read_text())
        assert "overall_quality_score" in quality  # untouched original field
        assert "discovery" in quality
        assert "overall_collector_quality" in quality["discovery"]

    def test_existing_datasets_collected_count_unaffected(self, tmp_path, monkeypatch):
        """Discovery must be purely additive: it must not change the main
        per-dataset collection counters."""
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()):
            result = c.collect()
        assert result.datasets_collected == 9

    def test_discovery_failure_does_not_break_pipeline(self, tmp_path, monkeypatch):
        """If discovery itself raises unexpectedly, the rest of the pipeline
        must still complete successfully."""
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        from collectors.osm import discovery
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass()), \
             patch.object(discovery, "run_discovery", side_effect=RuntimeError("boom")):
            result = c.collect()
        assert result.datasets_collected == 9
        assert (tmp_path / "statistics" / "osm_statistics.json").exists()
        assert (tmp_path / "quality" / "osm_quality.json").exists()

    def test_future_tag_discovered_during_full_run(self, tmp_path, monkeypatch):
        from collectors.osm import utils as u
        monkeypatch.setattr(u, "_CACHE_DIR", tmp_path / "cache")
        c = self._make_collector(tmp_path)
        with patch(MOCK_TARGET, _mock_overpass(MIXED_ELEMENTS)):
            c.collect()
        report = json.loads((tmp_path / "reports" / "osm_discovery_report.json").read_text())
        assert "future_tag_xyz" in report["unknown_railway_tags"]
