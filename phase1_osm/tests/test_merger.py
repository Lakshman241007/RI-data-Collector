from extractor.merger import merge_datasets
from extractor.models import RailwayObject


def _obj(osm_id, source, tags=None, osm_type="node"):
    return RailwayObject(
        osm_id=osm_id,
        osm_type=osm_type,
        tags=tags or {"railway": "station"},
        geometry=[80.0, 13.0],
        source=source,
    )


def test_merge_with_no_overlap_keeps_everything():
    geofabrik = [_obj(1, "geofabrik"), _obj(2, "geofabrik")]
    overpass = [_obj(3, "overpass")]
    merged, duplicates = merge_datasets(geofabrik, overpass)
    assert len(merged) == 3
    assert duplicates == 0


def test_merge_prefers_overpass_on_duplicate_id():
    geofabrik = [_obj(1, "geofabrik", tags={"railway": "rail"})]
    overpass = [_obj(1, "overpass", tags={"railway": "station"})]
    merged, duplicates = merge_datasets(geofabrik, overpass)

    assert len(merged) == 1
    assert duplicates == 1
    assert merged[0].source == "overpass"
    assert merged[0].tags["railway"] == "station"


def test_merge_distinguishes_by_osm_type_not_just_id():
    # same numeric id but different osm_type must NOT be treated as duplicate
    geofabrik = [_obj(1, "geofabrik", osm_type="node")]
    overpass = [_obj(1, "overpass", osm_type="way")]
    merged, duplicates = merge_datasets(geofabrik, overpass)

    assert len(merged) == 2
    assert duplicates == 0


def test_merge_preserves_all_railway_tags():
    geofabrik = [_obj(1, "geofabrik", tags={"railway": "rail", "gauge": "1676", "electrified": "yes"})]
    merged, _ = merge_datasets(geofabrik, [])
    assert merged[0].tags == {"railway": "rail", "gauge": "1676", "electrified": "yes"}


def test_merge_removes_duplicates_count_correctly_across_many():
    geofabrik = [_obj(i, "geofabrik") for i in range(1, 6)]
    overpass = [_obj(i, "overpass") for i in range(3, 8)]  # ids 3,4,5 overlap
    merged, duplicates = merge_datasets(geofabrik, overpass)

    assert duplicates == 3
    assert len(merged) == 7  # 1,2,3,4,5,6,7 unique ids
