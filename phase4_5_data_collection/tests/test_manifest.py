"""
tests/test_manifest.py
Unit tests for the manifest generation module.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.manifest import CollectorManifest, DatasetEntry, load_manifest


class TestCollectorManifest:
    def test_create_manifest(self) -> None:
        m = CollectorManifest(
            collector_name="test",
            collector_version="4.5.1",
            source_name="Test Source",
            license="CC0",
        )
        assert m.collector_name == "test"
        assert m.datasets == []

    def test_add_file(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text('{"records": [1, 2, 3]}')
        m = CollectorManifest(
            collector_name="test",
            collector_version="4.5.1",
            source_name="Src",
            license="MIT",
        )
        m.add_file(f, record_count=3, validation_passed=True)
        assert len(m.datasets) == 1
        assert m.datasets[0].record_count == 3
        assert len(m.datasets[0].checksum_sha256) == 64

    def test_add_file_missing(self, tmp_path: Path) -> None:
        m = CollectorManifest(
            collector_name="test",
            collector_version="4.5.1",
            source_name="Src",
            license="MIT",
        )
        # Missing file should be silently skipped (warning logged)
        m.add_file(tmp_path / "nonexistent.json", record_count=0)
        assert len(m.datasets) == 0

    def test_total_records(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.json"
        f1.write_text('{}')
        f2 = tmp_path / "b.json"
        f2.write_text('{}')
        m = CollectorManifest(
            collector_name="test",
            collector_version="4.5.1",
            source_name="Src",
            license="MIT",
        )
        m.add_file(f1, record_count=10)
        m.add_file(f2, record_count=25)
        assert m.total_records() == 35

    def test_save_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from common import manifest as manifest_mod
        monkeypatch.setattr(manifest_mod, "MANIFESTS_DIR", tmp_path)
        m = CollectorManifest(
            collector_name="test_collector",
            collector_version="4.5.1",
            source_name="Src",
            license="MIT",
        )
        path = m.save()
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["collector_name"] == "test_collector"
        assert "download_timestamp" in data

    def test_validation_summary(self) -> None:
        m = CollectorManifest(
            collector_name="test",
            collector_version="4.5.1",
            source_name="Src",
            license="MIT",
        )
        m.set_validation_summary(passed=5, failed=1, warnings=2)
        assert m.validation_summary["passed"] == 5
        assert m.validation_summary["failed"] == 1
        assert m.validation_summary["total_datasets"] == 6

    def test_to_dict_structure(self) -> None:
        m = CollectorManifest(
            collector_name="osm",
            collector_version="4.5.1",
            source_name="OpenStreetMap",
            license="ODbL",
        )
        d = m.to_dict()
        assert "collector_name" in d
        assert "datasets" in d
        assert "total_records" in d
        assert "total_size_bytes" in d
