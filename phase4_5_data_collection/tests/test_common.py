"""
tests/test_common.py
Unit tests for common utility modules.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.checksum import sha256_file, verify_checksum
from common.file_utils import (
    archive_file,
    ensure_dir,
    file_size_bytes,
    iter_files,
    safe_filename,
    timestamp_utc,
)
from common.json_utils import load_json, safe_load_json, save_json
from common.logger import get_logger
from common.validator import DatasetValidator, ValidationResult


# ---------------------------------------------------------------------------
# checksum
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_sha256_known_content(self, tmp_path: Path) -> None:
        import hashlib
        content = b"hello railway"
        f = tmp_path / "test.bin"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert sha256_file(f) == expected

    def test_sha256_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            sha256_file(tmp_path / "nonexistent.bin")

    def test_verify_checksum_pass(self, tmp_path: Path) -> None:
        f = tmp_path / "c.txt"
        f.write_bytes(b"data")
        digest = sha256_file(f)
        assert verify_checksum(f, digest) is True

    def test_verify_checksum_fail(self, tmp_path: Path) -> None:
        f = tmp_path / "c.txt"
        f.write_bytes(b"data")
        assert verify_checksum(f, "0" * 64) is False


# ---------------------------------------------------------------------------
# file_utils
# ---------------------------------------------------------------------------

class TestFileUtils:
    def test_ensure_dir_creates(self, tmp_path: Path) -> None:
        d = tmp_path / "a" / "b" / "c"
        result = ensure_dir(d)
        assert d.is_dir()
        assert result == d

    def test_file_size_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_bytes(b"12345")
        assert file_size_bytes(f) == 5

    def test_file_size_missing(self, tmp_path: Path) -> None:
        assert file_size_bytes(tmp_path / "missing.txt") == 0

    def test_timestamp_utc_format(self) -> None:
        ts = timestamp_utc()
        assert "T" in ts
        assert ts.endswith("+00:00")

    def test_archive_file_copy(self, tmp_path: Path) -> None:
        src = tmp_path / "src.json"
        src.write_text('{"a": 1}')
        dest_dir = tmp_path / "dest"
        dest = archive_file(src, dest_dir)
        assert dest.exists()
        assert dest.read_text() == '{"a": 1}'

    def test_archive_file_compress(self, tmp_path: Path) -> None:
        import gzip
        src = tmp_path / "src.txt"
        src.write_bytes(b"compress me")
        dest_dir = tmp_path / "dest"
        dest = archive_file(src, dest_dir, compress=True)
        assert dest.suffix == ".gz"
        with gzip.open(dest, "rb") as fh:
            assert fh.read() == b"compress me"

    def test_iter_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.txt").write_text("hi")
        json_files = list(iter_files(tmp_path, suffix=".json"))
        assert len(json_files) == 1
        assert json_files[0].name == "a.json"

    def test_safe_filename(self) -> None:
        assert safe_filename("New Delhi / Station") == "new_delhi___station"
        assert safe_filename("  Hello World  ") == "hello_world"


# ---------------------------------------------------------------------------
# json_utils
# ---------------------------------------------------------------------------

class TestJsonUtils:
    def test_save_and_load(self, tmp_path: Path) -> None:
        data = {"key": "value", "num": 42}
        path = tmp_path / "data.json"
        save_json(data, path)
        loaded = load_json(path)
        assert loaded == data

    def test_load_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "nope.json")

    def test_safe_load_returns_default(self, tmp_path: Path) -> None:
        result = safe_load_json(tmp_path / "missing.json", default={"x": 1})
        assert result == {"x": 1}

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "data.json"
        save_json({"ok": True}, path)
        assert path.exists()


# ---------------------------------------------------------------------------
# logger
# ---------------------------------------------------------------------------

class TestLogger:
    def test_get_logger_returns_logger(self, tmp_path: Path) -> None:
        logger = get_logger("test_logger")
        assert logger.name == "test_logger"

    def test_get_logger_idempotent(self) -> None:
        l1 = get_logger("idempotent_logger")
        l2 = get_logger("idempotent_logger")
        assert l1 is l2


# ---------------------------------------------------------------------------
# validator
# ---------------------------------------------------------------------------

class TestDatasetValidator:
    def test_validate_file_exists(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text('{"records": []}')
        v = DatasetValidator("test")
        result = v.validate_file(f, "test_dataset")
        assert isinstance(result, ValidationResult)

    def test_validate_file_missing(self, tmp_path: Path) -> None:
        v = DatasetValidator("test")
        result = v.validate_file(tmp_path / "missing.json", "missing")
        assert not result.passed
        assert any("not found" in e for e in result.errors)

    def test_validate_file_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.json"
        f.write_bytes(b"")
        v = DatasetValidator("test")
        result = v.validate_file(f, "empty", min_size_bytes=1)
        assert not result.passed

    def test_validate_file_bad_json(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        v = DatasetValidator("test")
        result = v.validate_file(f, "bad")
        assert not result.passed

    def test_validate_records_pass(self) -> None:
        v = DatasetValidator("test")
        records = [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]
        result = v.validate_records(records, "dataset", ["id", "name"])
        assert result.passed

    def test_validate_records_empty(self) -> None:
        v = DatasetValidator("test")
        result = v.validate_records([], "empty_dataset")
        assert not result.passed

    def test_validate_records_missing_keys(self) -> None:
        v = DatasetValidator("test")
        records = [{"id": "1"}]  # missing "name"
        result = v.validate_records(records, "dataset", ["id", "name"])
        # Should warn but not necessarily fail
        assert len(result.warnings) > 0

    def test_validate_checksum_mismatch(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello")
        v = DatasetValidator("test")
        result = v.validate_file(f, "data", expected_checksum="0" * 64)
        assert not result.passed
        assert any("Checksum" in e for e in result.errors)
