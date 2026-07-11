"""
Tests for the Stage 3B.1.6 Metadata Registry.

Scope: Only tests metadata file loading, structural validation,
reference verification, category validation, and full registry loading.
Does not test any quality engines, confidence calculations, or live
analysis.
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

import metadata_validator


# ---------------------------------------------------------------------------
# Known registry IDs
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

VALID_SOURCE_QUALITY = {
    "description": "test",
    "version": "1.0.0",
    "valid_quality_tiers": ["authoritative", "official", "community", "unknown"],
    "providers": {
        "indian_railways": {
            "quality_tier": "authoritative",
            "completeness": "unknown",
            "accuracy": "unknown",
            "timeliness": "unknown",
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_CONFIDENCE_SCORES = {
    "description": "test",
    "version": "1.0.0",
    "valid_confidence_levels": ["high", "medium", "low", "unassessed"],
    "datasets": {
        "railway_zones": {
            "confidence_level": "unassessed",
            "primary_provider": "indian_railways",
            "cross_reference_available": False,
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_UPDATE_FREQUENCY = {
    "description": "test",
    "version": "1.0.0",
    "valid_frequencies": ["static", "annual", "quarterly", "monthly",
                          "weekly", "daily", "unknown"],
    "datasets": {
        "railway_zones": {
            "expected_frequency": "static",
            "last_known_update": None,
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_MAINTAINERS = {
    "description": "test",
    "version": "1.0.0",
    "providers": {
        "indian_railways": {
            "organization": "Indian Railways",
            "department": "",
            "contact_email": "",
            "contact_url": "",
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_DATASET_PRIORITY = {
    "description": "test",
    "version": "1.0.0",
    "valid_priority_categories": ["critical", "high", "medium", "low"],
    "datasets": {
        "railway_zones": {
            "priority_category": "critical",
            "rationale": "test"
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

class TestMetadataLoading:
    """Tests for loading metadata files."""

    def test_load_valid_file(self, tmp_path):
        _write_json(tmp_path, "test.json", VALID_SOURCE_QUALITY)
        data = metadata_validator.load_metadata_file(
            "test.json", metadata_dir=str(tmp_path)
        )
        assert isinstance(data, dict)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            metadata_validator.load_metadata_file(
                "nonexistent.json", metadata_dir=str(tmp_path)
            )

    def test_load_malformed_json_raises(self, tmp_path):
        bad = tmp_path / "broken.json"
        bad.write_text("{broken json!", encoding="utf-8")
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.load_metadata_file(
                "broken.json", metadata_dir=str(tmp_path)
            )
        assert "invalid JSON" in str(exc.value)

    def test_load_each_real_metadata_file(self):
        """All 5 real metadata files should load without error."""
        for filename in metadata_validator.METADATA_FILES:
            data = metadata_validator.load_metadata_file(filename)
            assert isinstance(data, dict), f"{filename} did not load as dict"


# ---------------------------------------------------------------------------
# Source quality validation
# ---------------------------------------------------------------------------

class TestSourceQuality:
    """Tests for source_quality.json validation."""

    def test_valid_passes(self):
        assert metadata_validator.validate_source_quality(
            copy.deepcopy(VALID_SOURCE_QUALITY), KNOWN_PROVIDER_IDS
        ) is True

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_SOURCE_QUALITY)
        data["providers"]["nonexistent"] = data["providers"].pop(
            "indian_railways"
        )
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_source_quality(
                data, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_quality_tier_raises(self):
        data = copy.deepcopy(VALID_SOURCE_QUALITY)
        data["providers"]["indian_railways"]["quality_tier"] = "legendary"
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_source_quality(
                data, KNOWN_PROVIDER_IDS
            )
        assert "legendary" in str(exc.value)

    def test_missing_quality_tier_raises(self):
        data = copy.deepcopy(VALID_SOURCE_QUALITY)
        del data["providers"]["indian_railways"]["quality_tier"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_source_quality(
                data, KNOWN_PROVIDER_IDS
            )
        assert "quality_tier" in str(exc.value)

    def test_missing_notes_raises(self):
        data = copy.deepcopy(VALID_SOURCE_QUALITY)
        del data["providers"]["indian_railways"]["notes"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_source_quality(
                data, KNOWN_PROVIDER_IDS
            )
        assert "notes" in str(exc.value)

    def test_missing_providers_dict_raises(self):
        data = {"valid_quality_tiers": ["authoritative"]}
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_source_quality(
                data, KNOWN_PROVIDER_IDS
            )
        assert "providers" in str(exc.value)

    def test_non_dict_raises(self):
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_source_quality(
                ["not", "a", "dict"], KNOWN_PROVIDER_IDS
            )
        assert "invalid structure" in str(exc.value)


# ---------------------------------------------------------------------------
# Confidence scores validation
# ---------------------------------------------------------------------------

class TestConfidenceScores:
    """Tests for confidence_scores.json validation."""

    def test_valid_passes(self):
        assert metadata_validator.validate_confidence_scores(
            copy.deepcopy(VALID_CONFIDENCE_SCORES),
            KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_CONFIDENCE_SCORES)
        data["datasets"]["nonexistent"] = data["datasets"].pop(
            "railway_zones"
        )
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_confidence_scores(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_confidence_level_raises(self):
        data = copy.deepcopy(VALID_CONFIDENCE_SCORES)
        data["datasets"]["railway_zones"]["confidence_level"] = "very_high"
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_confidence_scores(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "very_high" in str(exc.value)

    def test_invalid_primary_provider_raises(self):
        data = copy.deepcopy(VALID_CONFIDENCE_SCORES)
        data["datasets"]["railway_zones"]["primary_provider"] = "nonexistent"
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_confidence_scores(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_missing_confidence_level_raises(self):
        data = copy.deepcopy(VALID_CONFIDENCE_SCORES)
        del data["datasets"]["railway_zones"]["confidence_level"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_confidence_scores(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "confidence_level" in str(exc.value)

    def test_missing_primary_provider_raises(self):
        data = copy.deepcopy(VALID_CONFIDENCE_SCORES)
        del data["datasets"]["railway_zones"]["primary_provider"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_confidence_scores(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "primary_provider" in str(exc.value)


# ---------------------------------------------------------------------------
# Update frequency validation
# ---------------------------------------------------------------------------

class TestUpdateFrequency:
    """Tests for update_frequency.json validation."""

    def test_valid_passes(self):
        assert metadata_validator.validate_update_frequency(
            copy.deepcopy(VALID_UPDATE_FREQUENCY), KNOWN_DATASET_IDS
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_UPDATE_FREQUENCY)
        data["datasets"]["nonexistent"] = data["datasets"].pop(
            "railway_zones"
        )
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_update_frequency(
                data, KNOWN_DATASET_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_frequency_raises(self):
        data = copy.deepcopy(VALID_UPDATE_FREQUENCY)
        data["datasets"]["railway_zones"]["expected_frequency"] = "hourly"
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_update_frequency(
                data, KNOWN_DATASET_IDS
            )
        assert "hourly" in str(exc.value)

    def test_missing_expected_frequency_raises(self):
        data = copy.deepcopy(VALID_UPDATE_FREQUENCY)
        del data["datasets"]["railway_zones"]["expected_frequency"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_update_frequency(
                data, KNOWN_DATASET_IDS
            )
        assert "expected_frequency" in str(exc.value)

    def test_missing_datasets_dict_raises(self):
        data = {"valid_frequencies": ["static"]}
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_update_frequency(
                data, KNOWN_DATASET_IDS
            )
        assert "datasets" in str(exc.value)


# ---------------------------------------------------------------------------
# Maintainers validation
# ---------------------------------------------------------------------------

class TestMaintainers:
    """Tests for maintainers.json validation."""

    def test_valid_passes(self):
        assert metadata_validator.validate_maintainers(
            copy.deepcopy(VALID_MAINTAINERS), KNOWN_PROVIDER_IDS
        ) is True

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_MAINTAINERS)
        data["providers"]["nonexistent"] = data["providers"].pop(
            "indian_railways"
        )
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_maintainers(
                data, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_missing_organization_raises(self):
        data = copy.deepcopy(VALID_MAINTAINERS)
        del data["providers"]["indian_railways"]["organization"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_maintainers(
                data, KNOWN_PROVIDER_IDS
            )
        assert "organization" in str(exc.value)

    def test_missing_notes_raises(self):
        data = copy.deepcopy(VALID_MAINTAINERS)
        del data["providers"]["indian_railways"]["notes"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_maintainers(
                data, KNOWN_PROVIDER_IDS
            )
        assert "notes" in str(exc.value)

    def test_missing_providers_dict_raises(self):
        data = {"description": "test"}
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_maintainers(
                data, KNOWN_PROVIDER_IDS
            )
        assert "providers" in str(exc.value)


# ---------------------------------------------------------------------------
# Dataset priority validation
# ---------------------------------------------------------------------------

class TestDatasetPriority:
    """Tests for dataset_priority.json validation."""

    def test_valid_passes(self):
        assert metadata_validator.validate_dataset_priority(
            copy.deepcopy(VALID_DATASET_PRIORITY), KNOWN_DATASET_IDS
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_DATASET_PRIORITY)
        data["datasets"]["nonexistent"] = data["datasets"].pop(
            "railway_zones"
        )
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_dataset_priority(
                data, KNOWN_DATASET_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_priority_category_raises(self):
        data = copy.deepcopy(VALID_DATASET_PRIORITY)
        data["datasets"]["railway_zones"]["priority_category"] = "ultra"
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_dataset_priority(
                data, KNOWN_DATASET_IDS
            )
        assert "ultra" in str(exc.value)

    def test_missing_priority_category_raises(self):
        data = copy.deepcopy(VALID_DATASET_PRIORITY)
        del data["datasets"]["railway_zones"]["priority_category"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_dataset_priority(
                data, KNOWN_DATASET_IDS
            )
        assert "priority_category" in str(exc.value)

    def test_missing_rationale_raises(self):
        data = copy.deepcopy(VALID_DATASET_PRIORITY)
        del data["datasets"]["railway_zones"]["rationale"]
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_dataset_priority(
                data, KNOWN_DATASET_IDS
            )
        assert "rationale" in str(exc.value)

    def test_missing_datasets_dict_raises(self):
        data = {"valid_priority_categories": ["critical"]}
        with pytest.raises(metadata_validator.MetadataValidationError) as exc:
            metadata_validator.validate_dataset_priority(
                data, KNOWN_DATASET_IDS
            )
        assert "datasets" in str(exc.value)


# ---------------------------------------------------------------------------
# Full registry tests
# ---------------------------------------------------------------------------

class TestFullMetadataRegistry:
    """Tests for loading and validating the complete metadata registry."""

    def test_complete_registry_loads(self):
        registry = metadata_validator.load_and_validate_metadata_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        assert len(registry) == 5
        for filename in metadata_validator.METADATA_FILES:
            assert filename in registry

    def test_source_quality_covers_all_providers(self):
        registry = metadata_validator.load_and_validate_metadata_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        sq = registry["source_quality.json"]
        assert KNOWN_PROVIDER_IDS == set(sq["providers"].keys())

    def test_confidence_scores_covers_all_datasets(self):
        registry = metadata_validator.load_and_validate_metadata_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        cs = registry["confidence_scores.json"]
        assert KNOWN_DATASET_IDS == set(cs["datasets"].keys())

    def test_update_frequency_covers_all_datasets(self):
        registry = metadata_validator.load_and_validate_metadata_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        uf = registry["update_frequency.json"]
        assert KNOWN_DATASET_IDS == set(uf["datasets"].keys())

    def test_maintainers_covers_all_providers(self):
        registry = metadata_validator.load_and_validate_metadata_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        mt = registry["maintainers.json"]
        assert KNOWN_PROVIDER_IDS == set(mt["providers"].keys())

    def test_dataset_priority_covers_all_datasets(self):
        registry = metadata_validator.load_and_validate_metadata_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        dp = registry["dataset_priority.json"]
        assert KNOWN_DATASET_IDS == set(dp["datasets"].keys())
