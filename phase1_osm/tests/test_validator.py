from extractor.models import RailwayObject
from extractor.validator import validate_dataset


def test_valid_node_has_no_issues():
    objects = [
        RailwayObject(osm_id=1, osm_type="node", tags={"railway": "station"}, geometry=[80.0, 13.0])
    ]
    report = validate_dataset(objects)
    assert report.total_objects == 1
    assert report.missing_coordinates_count == 0
    assert report.invalid_railway_tag_count == 0
    assert report.broken_geometry_count == 0
    assert report.duplicate_id_count == 0


def test_missing_id_detected():
    objects = [RailwayObject(osm_id=None, osm_type="node", tags={"railway": "station"}, geometry=[80.0, 13.0])]
    report = validate_dataset(objects)
    assert report.missing_id_count == 1


def test_missing_coordinates_detected_for_node():
    objects = [RailwayObject(osm_id=1, osm_type="node", tags={"railway": "station"}, geometry=None)]
    report = validate_dataset(objects)
    assert report.missing_coordinates_count == 1


def test_missing_coordinates_detected_for_way():
    objects = [RailwayObject(osm_id=1, osm_type="way", tags={"railway": "rail"}, geometry=[])]
    report = validate_dataset(objects)
    assert report.missing_coordinates_count == 1


def test_duplicate_ids_detected():
    objects = [
        RailwayObject(osm_id=1, osm_type="node", tags={"railway": "station"}, geometry=[80.0, 13.0]),
        RailwayObject(osm_id=1, osm_type="node", tags={"railway": "station"}, geometry=[80.0, 13.0]),
    ]
    report = validate_dataset(objects)
    assert report.duplicate_id_count == 1


def test_invalid_railway_tag_value_detected():
    objects = [RailwayObject(osm_id=1, osm_type="node", tags={"railway": "not_a_real_value"}, geometry=[80.0, 13.0])]
    report = validate_dataset(objects)
    assert report.invalid_railway_tag_count == 1


def test_missing_railway_tag_detected():
    objects = [RailwayObject(osm_id=1, osm_type="node", tags={"name": "Some Place"}, geometry=[80.0, 13.0])]
    report = validate_dataset(objects)
    assert report.invalid_railway_tag_count == 1


def test_broken_geometry_detected_for_short_way():
    objects = [RailwayObject(osm_id=1, osm_type="way", tags={"railway": "rail"}, geometry=[[80.0, 13.0]])]
    report = validate_dataset(objects)
    assert report.broken_geometry_count == 1


def test_broken_geometry_detected_for_out_of_range_coords():
    objects = [RailwayObject(osm_id=1, osm_type="node", tags={"railway": "station"}, geometry=[999.0, 13.0])]
    report = validate_dataset(objects)
    assert report.broken_geometry_count == 1


def test_valid_way_with_multiple_points_passes():
    objects = [
        RailwayObject(
            osm_id=1,
            osm_type="way",
            tags={"railway": "rail"},
            geometry=[[80.0, 13.0], [80.1, 13.1], [80.2, 13.2]],
        )
    ]
    report = validate_dataset(objects)
    assert report.broken_geometry_count == 0
