import json

import pytest
import requests

from extractor.config import OverpassConfig
from extractor.overpass import OverpassClient, OverpassError, parse_elements


@pytest.fixture
def config() -> OverpassConfig:
    return OverpassConfig(
        endpoint="https://overpass-api.de/api/interpreter",
        timeout=30,
        retries=2,
        retry_backoff=0,
        region="Tamil Nadu",
    )


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, raise_exc=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc

    def json(self):
        return self._json_data


def test_health_check_success(config, monkeypatch):
    client = OverpassClient(config)
    monkeypatch.setattr(client.session, "post", lambda *a, **k: _FakeResponse(200))
    assert client.health_check() is True


def test_health_check_failure(config, monkeypatch):
    client = OverpassClient(config)

    def _raise(*args, **kwargs):
        raise requests.exceptions.ConnectionError("unreachable")

    monkeypatch.setattr(client.session, "post", _raise)
    assert client.health_check() is False


def test_fetch_railway_data_retries_then_succeeds(config, monkeypatch):
    client = OverpassClient(config)
    calls = {"count": 0}

    def _post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.exceptions.ConnectionError("temporary failure")
        return _FakeResponse(200, json_data={"elements": []})

    monkeypatch.setattr(client.session, "post", _post)
    data = client.fetch_railway_data()
    assert data == {"elements": []}
    assert calls["count"] == 2


def test_fetch_railway_data_exhausts_retries(config, monkeypatch):
    client = OverpassClient(config)

    def _raise(*args, **kwargs):
        raise requests.exceptions.Timeout("too slow")

    monkeypatch.setattr(client.session, "post", _raise)
    with pytest.raises(OverpassError):
        client.fetch_railway_data()


def test_save_raw_writes_json(tmp_path, config):
    data = {"elements": [{"type": "node", "id": 1}]}
    output_path = tmp_path / "raw_overpass.json"
    OverpassClient.save_raw(data, output_path)
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["elements"][0]["id"] == 1


def test_parse_elements_filters_non_railway_nodes():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 13.08, "lon": 80.27, "tags": {"railway": "station"}},
            {"type": "node", "id": 2, "lat": 13.0, "lon": 80.0, "tags": {"amenity": "cafe"}},
        ]
    }
    objects = parse_elements(data)
    assert len(objects) == 1
    assert objects[0].osm_id == 1
    assert objects[0].source == "overpass"
    assert objects[0].geometry == [80.27, 13.08]


def test_parse_elements_way_geometry():
    data = {
        "elements": [
            {
                "type": "way",
                "id": 10,
                "tags": {"railway": "rail"},
                "geometry": [{"lat": 13.0, "lon": 80.0}, {"lat": 13.1, "lon": 80.1}],
            }
        ]
    }
    objects = parse_elements(data)
    assert len(objects) == 1
    assert objects[0].osm_type == "way"
    assert objects[0].geometry == [[80.0, 13.0], [80.1, 13.1]]


def test_parse_elements_relation_members():
    data = {
        "elements": [
            {
                "type": "relation",
                "id": 99,
                "tags": {"railway": "rail", "type": "route"},
                "members": [{"type": "way", "ref": 10, "role": ""}],
            }
        ]
    }
    objects = parse_elements(data)
    assert len(objects) == 1
    assert objects[0].geometry[0]["ref"] == 10
