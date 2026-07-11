"""
Tests for the Stage 3B.1.2 Dataset Registry.

Scope: Only tests dataset descriptor loading, structural validation,
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

import dataset_validator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_DATASET = {
    "dataset_id": "test_dataset",
    "display_name": "Test Dataset",
    "description": "A test dataset descriptor used only for unit tests.",
    "provider_reference": "indian_railways",
    "schema_reference": "",
    "mapping_reference": "",
    "policy_reference": "",
    "license_reference": "",
    "verification_reference": "",
    "version_reference": "",
    "dependencies": [],
    "priority": 1,
    "refresh_policy": "manual",
    "enabled": True,
    "notes": "test",
}

# Known provider IDs from the Stage 3B.1.1 Provider Registry.
KNOWN_PROVIDER_IDS = {
    "indian_railways",
    "government_open_data",
    "southern_railway",
    "cris",
    "openstreetmap",
    "wikipedia",
}


def _write_dataset(tmp_path, filename, data):
    """Helper: write a dataset descriptor dict to a JSON file."""
    path = tmp_path / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------

class TestDatasetLoading:
    """Tests for loading dataset descriptor files."""

    def test_load_valid_dataset(self, tmp_path):
        _write_dataset(tmp_path, "test.json", VALID_DATASET)
        data = dataset_validator.load_dataset_file("test.json", datasets_dir=str(tmp_path))
        assert isinstance(data, dict)
        assert data["dataset_id"] == "test_dataset"

    def test_load_missing_dataset_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            dataset_validator.load_dataset_file(
                "does_not_exist.json", datasets_dir=str(tmp_path)
            )

    def test_load_malformed_json_raises_validation_error(self, tmp_path):
        bad_file = tmp_path / "broken.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.load_dataset_file("broken.json", datasets_dir=str(tmp_path))
        assert "invalid JSON" in str(exc.value)

    def test_load_each_real_dataset_file_succeeds(self):
        """All 7 dataset files in the repository should load without error."""
        for filename in dataset_validator.DATASET_FILES:
            data = dataset_validator.load_dataset_file(filename)
            assert isinstance(data, dict), f"{filename} did not load as a dict"


# ---------------------------------------------------------------------------
# Structural validation tests
# ---------------------------------------------------------------------------

class TestDatasetValidation:
    """Tests for structural validation of a single dataset descriptor."""

    def test_valid_dataset_passes(self):
        assert dataset_validator.validate_dataset(
            copy.deepcopy(VALID_DATASET), "unit_test"
        ) is True

    def test_missing_required_field_raises(self):
        broken = copy.deepcopy(VALID_DATASET)
        del broken["description"]
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.validate_dataset(broken, "unit_test")
        assert "missing required fields" in str(exc.value)
        assert "description" in str(exc.value)

    def test_non_dict_structure_raises(self):
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.validate_dataset(["not", "a", "dict"], "unit_test")
        assert "invalid structure" in str(exc.value)

    def test_empty_dataset_id_raises(self):
        broken = copy.deepcopy(VALID_DATASET)
        broken["dataset_id"] = ""
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.validate_dataset(broken, "unit_test")
        assert "dataset_id" in str(exc.value)

    def test_non_list_dependencies_raises(self):
        broken = copy.deepcopy(VALID_DATASET)
        broken["dependencies"] = "not_a_list"
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.validate_dataset(broken, "unit_test")
        assert "dependencies" in str(exc.value)

    def test_non_boolean_enabled_raises(self):
        broken = copy.deepcopy(VALID_DATASET)
        broken["enabled"] = "yes"
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.validate_dataset(broken, "unit_test")
        assert "enabled" in str(exc.value)


# ---------------------------------------------------------------------------
# Reference verification tests
# ---------------------------------------------------------------------------

class TestReferenceVerification:
    """Tests for cross-reference verification."""

    def test_valid_provider_reference_passes(self):
        registry = {"ds1": copy.deepcopy(VALID_DATASET)}
        # Should not raise.
        dataset_validator.verify_provider_references(
            registry, KNOWN_PROVIDER_IDS
        )

    def test_invalid_provider_reference_raises(self):
        ds = copy.deepcopy(VALID_DATASET)
        ds["provider_reference"] = "nonexistent_provider"
        registry = {"ds1": ds}
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.verify_provider_references(
                registry, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent_provider" in str(exc.value)

    def test_invalid_dependency_raises(self):
        ds = copy.deepcopy(VALID_DATASET)
        ds["dependencies"] = ["nonexistent_dataset"]
        registry = {"test_dataset": ds}
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.verify_dependencies(registry)
        assert "nonexistent_dataset" in str(exc.value)

    def test_valid_dependency_passes(self):
        ds_a = copy.deepcopy(VALID_DATASET)
        ds_a["dataset_id"] = "ds_a"
        ds_a["dependencies"] = ["ds_b"]

        ds_b = copy.deepcopy(VALID_DATASET)
        ds_b["dataset_id"] = "ds_b"
        ds_b["dependencies"] = []

        registry = {"ds_a": ds_a, "ds_b": ds_b}
        # Should not raise.
        dataset_validator.verify_dependencies(registry)

    def test_invalid_schema_reference_raises(self, tmp_path):
        ds = copy.deepcopy(VALID_DATASET)
        ds["schema_reference"] = "schemas/official/nonexistent_schema.json"
        registry = {"test_dataset": ds}
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.verify_schema_references(
                registry, project_root=str(tmp_path)
            )
        assert "nonexistent_schema" in str(exc.value)

    def test_valid_schema_reference_passes(self, tmp_path):
        # Create the expected schema file.
        schema_dir = tmp_path / "schemas" / "official"
        schema_dir.mkdir(parents=True)
        (schema_dir / "test_schema.json").write_text("{}", encoding="utf-8")

        ds = copy.deepcopy(VALID_DATASET)
        ds["schema_reference"] = "schemas/official/test_schema.json"
        registry = {"test_dataset": ds}
        # Should not raise.
        dataset_validator.verify_schema_references(
            registry, project_root=str(tmp_path)
        )

    def test_empty_schema_reference_passes(self, tmp_path):
        ds = copy.deepcopy(VALID_DATASET)
        ds["schema_reference"] = ""
        registry = {"test_dataset": ds}
        # Empty reference should be accepted without error.
        dataset_validator.verify_schema_references(
            registry, project_root=str(tmp_path)
        )

    def test_invalid_mapping_reference_type_raises(self):
        ds = copy.deepcopy(VALID_DATASET)
        ds["mapping_reference"] = 12345
        registry = {"test_dataset": ds}
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.verify_mapping_references(registry)
        assert "mapping_reference" in str(exc.value)

    def test_invalid_policy_reference_type_raises(self):
        ds = copy.deepcopy(VALID_DATASET)
        ds["policy_reference"] = ["not", "a", "string"]
        registry = {"test_dataset": ds}
        with pytest.raises(dataset_validator.DatasetValidationError) as exc:
            dataset_validator.verify_policy_references(registry)
        assert "policy_reference" in str(exc.value)


# ---------------------------------------------------------------------------
# Duplicate ID tests
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    """Tests for duplicate dataset_id detection."""

    def test_duplicate_dataset_id_raises(self, tmp_path):
        ds = copy.deepcopy(VALID_DATASET)
        _write_dataset(tmp_path, "ds1.json", ds)
        _write_dataset(tmp_path, "ds2.json", ds)  # Same dataset_id.

        # Override the file list to use our duplicates.
        original = dataset_validator.DATASET_FILES
        try:
            dataset_validator.DATASET_FILES = ["ds1.json", "ds2.json"]
            with pytest.raises(dataset_validator.DatasetValidationError) as exc:
                dataset_validator.load_and_validate_dataset_registry(
                    datasets_dir=str(tmp_path),
                    provider_ids=KNOWN_PROVIDER_IDS,
                    project_root=str(tmp_path),
                )
            assert "Duplicate" in str(exc.value)
        finally:
            dataset_validator.DATASET_FILES = original


# ---------------------------------------------------------------------------
# Full registry tests
# ---------------------------------------------------------------------------

class TestFullRegistry:
    """Tests for loading and validating the complete dataset registry."""

    def test_complete_registry_loads_without_error(self):
        registry = dataset_validator.load_and_validate_dataset_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        expected_ids = {
            "railway_zones",
            "railway_divisions",
            "station_codes",
            "station_master",
            "train_master",
            "station_categories",
            "station_status",
        }
        assert expected_ids == set(registry.keys())

    def test_all_datasets_enabled(self):
        registry = dataset_validator.load_and_validate_dataset_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        for dataset_id, data in registry.items():
            assert data["enabled"] is True, (
                f"Dataset '{dataset_id}' should be enabled"
            )

    def test_no_duplicate_ids_in_registry(self):
        registry = dataset_validator.load_and_validate_dataset_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        ids = list(registry.keys())
        assert len(ids) == len(set(ids)), "Duplicate dataset_ids found in registry"

    def test_dependency_chain_is_consistent(self):
        """Verify the expected dependency chain:
        station_master -> station_codes -> railway_divisions -> railway_zones
        """
        registry = dataset_validator.load_and_validate_dataset_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        assert registry["station_master"]["dependencies"] == ["station_codes"]
        assert registry["station_codes"]["dependencies"] == ["railway_divisions"]
        assert registry["railway_divisions"]["dependencies"] == ["railway_zones"]
        assert registry["railway_zones"]["dependencies"] == []

    def test_all_provider_references_are_valid(self):
        registry = dataset_validator.load_and_validate_dataset_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        for dataset_id, data in registry.items():
            ref = data.get("provider_reference", "")
            if ref:
                assert ref in KNOWN_PROVIDER_IDS, (
                    f"Dataset '{dataset_id}' references unknown provider '{ref}'"
                )
