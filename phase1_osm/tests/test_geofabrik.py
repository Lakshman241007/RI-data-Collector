from pathlib import Path

import pytest

from extractor.config import GeofabrikConfig
from extractor.geofabrik import GeofabrikDownloader


@pytest.fixture
def config(tmp_path) -> GeofabrikConfig:
    return GeofabrikConfig(
        url="https://download.geofabrik.de/asia/india-latest.osm.pbf",
        download_dir=str(tmp_path),
        filename="india-latest.osm.pbf",
        chunk_size=1024,
    )


class _FakeStreamResponse:
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        for chunk in self._chunks:
            yield chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_skip_existing_complete_download(config, monkeypatch):
    downloader = GeofabrikDownloader(config)
    target = downloader.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * 100)

    monkeypatch.setattr(downloader, "_remote_size", lambda: 100)
    result = downloader.download()

    assert result == target
    assert target.read_bytes() == b"x" * 100


def test_download_fresh_file(config, monkeypatch):
    downloader = GeofabrikDownloader(config)

    fake_response = _FakeStreamResponse(
        status_code=200, headers={"Content-Length": "4"}, chunks=[b"data"]
    )
    monkeypatch.setattr("extractor.geofabrik.requests.get", lambda *a, **k: fake_response)

    result = downloader.download()
    assert result.exists()
    assert result.read_bytes() == b"data"


def test_resume_partial_download(config, monkeypatch):
    downloader = GeofabrikDownloader(config)
    target = downloader.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"partial-")

    captured_kwargs = {}

    def _fake_get(url, headers=None, stream=None, timeout=None):
        captured_kwargs["headers"] = headers
        return _FakeStreamResponse(
            status_code=206, headers={"Content-Length": "4"}, chunks=[b"rest"]
        )

    monkeypatch.setattr(downloader, "_remote_size", lambda: 100)
    monkeypatch.setattr("extractor.geofabrik.requests.get", _fake_get)

    result = downloader.download()
    assert captured_kwargs["headers"]["Range"] == "bytes=8-"
    assert result.read_bytes() == b"partial-rest"


def test_force_redownloads_even_if_present(config, monkeypatch):
    downloader = GeofabrikDownloader(config)
    target = downloader.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"old-data")

    fake_response = _FakeStreamResponse(
        status_code=200, headers={"Content-Length": "8"}, chunks=[b"new-data"]
    )
    monkeypatch.setattr("extractor.geofabrik.requests.get", lambda *a, **k: fake_response)

    result = downloader.download(force=True)
    assert result.read_bytes() == b"new-data"
