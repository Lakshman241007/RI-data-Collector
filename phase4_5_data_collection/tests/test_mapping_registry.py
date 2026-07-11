"""
Tests for the Stage 3B.1.3 Mapping Registry.

Scope: Only tests mapping file loading, structural validation,
reference verification, and full registry loading. Does not test
collectors, downloads, authentication, or any live configuration.
"""

import copy
import json
import os
import sys

import pytest

# Ensure data_registry directory is importable.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_REGISTRY = os.path.join(_ROOT, "data_registry")
for p in (_ROOT, _DATA_REGISTRY):
    if p not in sys.path:
        sys.path.insert(0, p)

import mapping_validator


# ---------------------------------------------------------------------------
# Known registry IDs from Stage 3B.1.1 and 3B.1.2
# ---------------------------------------------------------------------------

KNOWN_PROVIDER_IDS = {
    "indian_railways",
    "government_open_data",
    "southern_railway",
    "cris",
    "openstreetmap",
    "wikipedia",
}

KNOWN_DATASET_IDS = {
    "railway_zones",
    "railway_divisions",
    "station_codes",
    "station_master",
    "train_master",
    "station_categories",
    "station_status",
}


# ---------------------------------------------------------------------------
# Valid test fixtures
# ---------------------------------------------------------------------------

VALID_PROVIDER_DATASET_MAPPING = {
    "description": "test",
    "version": "1.0.0",
    "mappings": [
        {
            "dataset_id": "railway_zones",
            "provider_id": "indian_railways",
            "role": "primary",
            "notes": "test"
        }
    ],
    "notes": "test"
}

VALID_FIELD_MAPPING = {
    "description": "test",
    "version": "1.0.0",
    "mappings": {
        "railway_zones": {
            "canonical_fields": ["zone_code", "zone_name"],
            "provider_field_maps": {
                "indian_railways": {
                    "zone_code": "zone_code",
                    "zone_name": "zone_name"
                }
            }
        }
    },
    "notes": "test"
}

VALID_TAG_MAPPING = {
    "description": "test",
    "version": "1.0.0",
    "tag_sources": {
        "openstreetmap": {
            "tag_key": "railway",
            "mappings": [
                {
                    "tag_value": "station",
                    "dataset_id": "station_master",
                    "description": "test"
                }
            ]
        }
    },
    "notes": "test"
}

VALID_DATASET_DEPENDENCIES = {
    "description": "test",
    "version": "1.0.0",
    "dependency_graph": {
        "railway_zones": {
            "depends_on": [],
            "build_order": 1,
            "notes": "test"
        },
        "railway_divisions": {
            "depends_on": ["railway_zones"],
            "build_order": 2,
            "notes": "test"
        }
    },
    "notes": "test"
}


def _write_json(tmp_path, filename, data):
    """Helper: write a dict to a JSON file."""
    path = tmp_path / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------

class TestMappingLoading:
    """Tests for loading mapping files."""

    def test_load_valid_mapping(self, tmp_path):
        _write_json(tmp_path, "test.json", VALID_PROVIDER_DATASET_MAPPING)
        data = mapping_validator.load_mapping_file(
            "test.json", mappings_dir=str(tmp_path)
        )
        assert isinstance(data, dict)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            mapping_validator.load_mapping_file(
                "nonexistent.json", mappings_dir=str(tmp_path)
            )

    def test_load_malformed_json_raises(self, tmp_path):
        bad = tmp_path / "broken.json"
        bad.write_text("{broken json!", encoding="utf-8")
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.load_mapping_file(
                "broken.json", mappings_dir=str(tmp_path)
            )
        assert "invalid JSON" in str(exc.value)

    def test_load_each_real_mapping_file(self):
        """All 4 real mapping files should load without error."""
        for filename in mapping_validator.MAPPING_FILES:
            data = mapping_validator.load_mapping_file(filename)
            assert isinstance(data, dict), f"{filename} did not load as dict"


# ---------------------------------------------------------------------------
# Provider-dataset mapping validation
# ---------------------------------------------------------------------------

class TestProviderDatasetMapping:
    """Tests for provider_dataset_mapping.json validation."""

    def test_valid_mapping_passes(self):
        assert mapping_validator.validate_provider_dataset_mapping(
            copy.deepcopy(VALID_PROVIDER_DATASET_MAPPING),
            KNOWN_PROVIDER_IDS,
            KNOWN_DATASET_IDS,
        ) is True

    def test_non_dict_raises(self):
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                ["not", "a", "dict"], KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "invalid structure" in str(exc.value)

    def test_missing_mappings_list_raises(self):
        data = {"description": "test"}
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "mappings" in str(exc.value)

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_PROVIDER_DATASET_MAPPING)
        data["mappings"][0]["dataset_id"] = "nonexistent_dataset"
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_dataset" in str(exc.value)

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_PROVIDER_DATASET_MAPPING)
        data["mappings"][0]["provider_id"] = "nonexistent_provider"
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_provider" in str(exc.value)

    def test_duplicate_pair_raises(self):
        data = copy.deepcopy(VALID_PROVIDER_DATASET_MAPPING)
        data["mappings"].append(copy.deepcopy(data["mappings"][0]))
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_invalid_role_raises(self):
        data = copy.deepcopy(VALID_PROVIDER_DATASET_MAPPING)
        data["mappings"][0]["role"] = "invalid_role"
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "role" in str(exc.value)

    def test_missing_required_field_in_entry_raises(self):
        data = copy.deepcopy(VALID_PROVIDER_DATASET_MAPPING)
        del data["mappings"][0]["role"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_provider_dataset_mapping(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "role" in str(exc.value)


# ---------------------------------------------------------------------------
# Field mapping validation
# ---------------------------------------------------------------------------

class TestFieldMapping:
    """Tests for field_mapping.json validation."""

    def test_valid_mapping_passes(self):
        assert mapping_validator.validate_field_mapping(
            copy.deepcopy(VALID_FIELD_MAPPING),
            KNOWN_DATASET_IDS,
            KNOWN_PROVIDER_IDS,
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_FIELD_MAPPING)
        data["mappings"]["nonexistent_dataset"] = data["mappings"].pop(
            "railway_zones"
        )
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_field_mapping(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent_dataset" in str(exc.value)

    def test_invalid_provider_in_field_maps_raises(self):
        data = copy.deepcopy(VALID_FIELD_MAPPING)
        maps = data["mappings"]["railway_zones"]["provider_field_maps"]
        maps["nonexistent_provider"] = maps.pop("indian_railways")
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_field_mapping(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent_provider" in str(exc.value)

    def test_duplicate_canonical_fields_raises(self):
        data = copy.deepcopy(VALID_FIELD_MAPPING)
        data["mappings"]["railway_zones"]["canonical_fields"] = [
            "zone_code", "zone_code"
        ]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_field_mapping(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_missing_canonical_fields_raises(self):
        data = copy.deepcopy(VALID_FIELD_MAPPING)
        del data["mappings"]["railway_zones"]["canonical_fields"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_field_mapping(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "canonical_fields" in str(exc.value)

    def test_missing_provider_field_maps_raises(self):
        data = copy.deepcopy(VALID_FIELD_MAPPING)
        del data["mappings"]["railway_zones"]["provider_field_maps"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_field_mapping(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "provider_field_maps" in str(exc.value)

    def test_missing_mappings_dict_raises(self):
        data = {"description": "test"}
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_field_mapping(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "mappings" in str(exc.value)


# ---------------------------------------------------------------------------
# Tag mapping validation
# ---------------------------------------------------------------------------

class TestTagMapping:
    """Tests for tag_mapping.json validation."""

    def test_valid_mapping_passes(self):
        assert mapping_validator.validate_tag_mapping(
            copy.deepcopy(VALID_TAG_MAPPING),
            KNOWN_DATASET_IDS,
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_TAG_MAPPING)
        data["tag_sources"]["openstreetmap"]["mappings"][0][
            "dataset_id"
        ] = "nonexistent"
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_tag_mapping(data, KNOWN_DATASET_IDS)
        assert "nonexistent" in str(exc.value)

    def test_null_dataset_id_passes(self):
        """Null dataset_id is valid — it means an unmapped tag."""
        data = copy.deepcopy(VALID_TAG_MAPPING)
        data["tag_sources"]["openstreetmap"]["mappings"][0][
            "dataset_id"
        ] = None
        assert mapping_validator.validate_tag_mapping(
            data, KNOWN_DATASET_IDS
        ) is True

    def test_duplicate_tag_value_raises(self):
        data = copy.deepcopy(VALID_TAG_MAPPING)
        data["tag_sources"]["openstreetmap"]["mappings"].append(
            copy.deepcopy(
                data["tag_sources"]["openstreetmap"]["mappings"][0]
            )
        )
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_tag_mapping(data, KNOWN_DATASET_IDS)
        assert "duplicate" in str(exc.value).lower()

    def test_missing_tag_sources_raises(self):
        data = {"description": "test"}
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_tag_mapping(data, KNOWN_DATASET_IDS)
        assert "tag_sources" in str(exc.value)

    def test_missing_tag_value_raises(self):
        data = copy.deepcopy(VALID_TAG_MAPPING)
        del data["tag_sources"]["openstreetmap"]["mappings"][0]["tag_value"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_tag_mapping(data, KNOWN_DATASET_IDS)
        assert "tag_value" in str(exc.value)

    def test_missing_dataset_id_key_raises(self):
        data = copy.deepcopy(VALID_TAG_MAPPING)
        del data["tag_sources"]["openstreetmap"]["mappings"][0]["dataset_id"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_tag_mapping(data, KNOWN_DATASET_IDS)
        assert "dataset_id" in str(exc.value)


# ---------------------------------------------------------------------------
# Dataset dependencies validation
# ---------------------------------------------------------------------------

class TestDatasetDependencies:
    """Tests for dataset_dependencies.json validation."""

    def test_valid_dependencies_passes(self):
        assert mapping_validator.validate_dataset_dependencies(
            copy.deepcopy(VALID_DATASET_DEPENDENCIES),
            KNOWN_DATASET_IDS,
        ) is True

    def test_invalid_dataset_id_raises(self):
        data = {
            "description": "test",
            "version": "1.0.0",
            "dependency_graph": {
                "nonexistent": {
                    "depends_on": [],
                    "build_order": 1,
                    "notes": "test"
                }
            },
            "notes": "test"
        }
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_dataset_dependencies(
                data, KNOWN_DATASET_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_dependency_reference_raises(self):
        data = copy.deepcopy(VALID_DATASET_DEPENDENCIES)
        data["dependency_graph"]["railway_divisions"][
            "depends_on"
        ] = ["nonexistent_dep"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_dataset_dependencies(
                data, KNOWN_DATASET_IDS
            )
        assert "nonexistent_dep" in str(exc.value)

    def test_self_dependency_raises(self):
        data = copy.deepcopy(VALID_DATASET_DEPENDENCIES)
        data["dependency_graph"]["railway_zones"][
            "depends_on"
        ] = ["railway_zones"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_dataset_dependencies(
                data, KNOWN_DATASET_IDS
            )
        assert "self-dependency" in str(exc.value)

    def test_missing_depends_on_raises(self):
        data = copy.deepcopy(VALID_DATASET_DEPENDENCIES)
        del data["dependency_graph"]["railway_zones"]["depends_on"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_dataset_dependencies(
                data, KNOWN_DATASET_IDS
            )
        assert "depends_on" in str(exc.value)

    def test_missing_build_order_raises(self):
        data = copy.deepcopy(VALID_DATASET_DEPENDENCIES)
        del data["dependency_graph"]["railway_zones"]["build_order"]
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_dataset_dependencies(
                data, KNOWN_DATASET_IDS
            )
        assert "build_order" in str(exc.value)

    def test_missing_dependency_graph_raises(self):
        data = {"description": "test"}
        with pytest.raises(mapping_validator.MappingValidationError) as exc:
            mapping_validator.validate_dataset_dependencies(
                data, KNOWN_DATASET_IDS
            )
        assert "dependency_graph" in str(exc.value)


# ---------------------------------------------------------------------------
# Full registry tests
# ---------------------------------------------------------------------------

class TestFullMappingRegistry:
    """Tests for loading and validating the complete mapping registry."""

    def test_complete_registry_loads(self):
        registry = mapping_validator.load_and_validate_mapping_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        assert len(registry) == 4
        for filename in mapping_validator.MAPPING_FILES:
            assert filename in registry

    def test_provider_dataset_mapping_covers_all_datasets(self):
        registry = mapping_validator.load_and_validate_mapping_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        pdm = registry["provider_dataset_mapping.json"]
        mapped_datasets = {
            e["dataset_id"] for e in pdm["mappings"]
        }
        assert KNOWN_DATASET_IDS.issubset(mapped_datasets)

    def test_dependency_graph_covers_all_datasets(self):
        registry = mapping_validator.load_and_validate_mapping_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        dd = registry["dataset_dependencies.json"]
        graph_ids = set(dd["dependency_graph"].keys())
        assert KNOWN_DATASET_IDS == graph_ids

    def test_field_mapping_covers_all_datasets(self):
        registry = mapping_validator.load_and_validate_mapping_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        fm = registry["field_mapping.json"]
        mapped_datasets = set(fm["mappings"].keys())
        assert KNOWN_DATASET_IDS.issubset(mapped_datasets)
