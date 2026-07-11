"""
tests/test_pipeline.py
Integration-level tests for main.py pipeline execution (dry-run mode).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from main import build_statistics, load_config, run_pipeline
from collectors import CollectorResult


class TestLoadConfig:
    def test_loads_settings(self, project_root: Path) -> None:
        settings, sources = load_config(project_root / "config" / "settings.json")
        assert "project" in settings
        assert "collectors" in settings
        assert "osm" in sources

    def test_loads_sources(self, project_root: Path) -> None:
        _, sources = load_config(project_root / "config" / "settings.json")
        assert "official" in sources
        assert "public" in sources
        assert "metadata" in sources


class TestBuildStatistics:
    def test_all_success(self) -> None:
        results = [
            CollectorResult(collector_name="osm", success=True, datasets_collected=8, total_records=1000),
            CollectorResult(collector_name="official", success=True, datasets_collected=5, total_records=500),
        ]
        stats = build_statistics(results, elapsed=12.5, settings={"project": "Test", "version": "4.5.1"})
        assert stats["overall_success"] is True
        assert stats["totals"]["datasets"] == 13
        assert stats["totals"]["records"] == 1500
        assert stats["elapsed_seconds"] == 12.5

    def test_partial_failure(self) -> None:
        results = [
            CollectorResult(collector_name="osm", success=True, datasets_collected=8, total_records=1000),
            CollectorResult(collector_name="official", success=False, datasets_collected=3, total_records=100),
        ]
        results[1].errors.append("Network error")
        stats = build_statistics(results, elapsed=5.0, settings={"project": "T", "version": "1"})
        assert stats["overall_success"] is False
        assert stats["totals"]["errors"] == 1

    def test_statistics_structure(self) -> None:
        results = [CollectorResult(collector_name="test", success=True)]
        stats = build_statistics(results, elapsed=1.0, settings={"project": "T", "version": "1"})
        assert "pipeline_run_at" in stats
        assert "collectors" in stats
        assert "totals" in stats


class TestRunPipelineDryRun:
    def test_dry_run_succeeds(self, project_root: Path) -> None:
        """Dry-run should complete without errors."""
        success = run_pipeline(project_root / "config" / "settings.json", dry_run=True)
        assert success is True

    def test_dry_run_generates_statistics(self, project_root: Path) -> None:
        run_pipeline(project_root / "config" / "settings.json", dry_run=True)
        stats_file = project_root / "statistics.json"
        assert stats_file.exists()
        data = json.loads(stats_file.read_text())
        assert "pipeline_run_at" in data

    def test_invalid_config_path_returns_false(self) -> None:
        success = run_pipeline(Path("/nonexistent/settings.json"))
        assert success is False
