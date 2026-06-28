import pytest

from extractor.pbf_reader import extract_railway_objects

_OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="phase1-tests">
  <node id="1" lat="13.0827" lon="80.2707" version="1" timestamp="2024-01-01T00:00:00Z">
    <tag k="railway" v="station"/>
    <tag k="name" v="Test Station"/>
  </node>
  <node id="2" lat="13.0000" lon="80.0000" version="1" timestamp="2024-01-01T00:00:00Z"/>
  <node id="3" lat="13.1000" lon="80.1000" version="1" timestamp="2024-01-01T00:00:00Z"/>
  <node id="4" lat="13.2000" lon="80.2000" version="1" timestamp="2024-01-01T00:00:00Z">
    <tag k="shop" v="bakery"/>
  </node>
  <way id="100" version="1" timestamp="2024-01-01T00:00:00Z">
    <nd ref="2"/>
    <nd ref="3"/>
    <tag k="railway" v="rail"/>
    <tag k="gauge" v="1676"/>
  </way>
  <relation id="500" version="1" timestamp="2024-01-01T00:00:00Z">
    <member type="way" ref="100" role=""/>
    <tag k="railway" v="rail"/>
    <tag k="type" v="route"/>
  </relation>
</osm>
"""


@pytest.fixture
def osm_file(tmp_path):
    path = tmp_path / "sample.osm"
    path.write_text(_OSM_XML, encoding="utf-8")
    return path


def test_extract_returns_only_railway_objects(osm_file):
    objects = extract_railway_objects(osm_file)
    osm_types = {obj.osm_type for obj in objects}
    assert osm_types == {"node", "way", "relation"}
    # node id=4 (a bakery) must not appear — it has no railway tag
    assert all(obj.osm_id != 4 for obj in objects)


def test_extract_node_geometry(osm_file):
    objects = extract_railway_objects(osm_file)
    node = next(o for o in objects if o.osm_type == "node")
    assert node.osm_id == 1
    assert node.tags["railway"] == "station"
    assert node.geometry == [80.2707, 13.0827]
    assert node.source == "geofabrik"


def test_extract_way_geometry_resolved_from_nodes(osm_file):
    objects = extract_railway_objects(osm_file)
    way = next(o for o in objects if o.osm_type == "way")
    assert way.osm_id == 100
    assert way.tags["gauge"] == "1676"
    assert way.geometry == [[80.0000, 13.0000], [80.1000, 13.1000]]


def test_extract_relation_members(osm_file):
    objects = extract_railway_objects(osm_file)
    relation = next(o for o in objects if o.osm_type == "relation")
    assert relation.osm_id == 500
    assert relation.geometry[0] == {"type": "way", "ref": 100, "role": ""}


def test_extract_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_railway_objects(tmp_path / "missing.osm")
