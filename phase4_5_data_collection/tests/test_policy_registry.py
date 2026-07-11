"""
Tests for the Stage 3B.1.4 Policy Registry.

Scope: Only tests policy file loading, structural validation,
reference verification, and full registry loading. Does not test
any policy execution, merge engines, schedulers, or cleanup jobs.
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

import policy_validator


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

VALID_REFRESH_POLICY = {
    "description": "test",
    "version": "1.0.0",
    "valid_strategies": ["manual", "daily", "weekly", "monthly", "on_demand"],
    "policies": {
        "railway_zones": {
            "strategy": "manual",
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_VALIDATION_POLICY = {
    "description": "test",
    "version": "1.0.0",
    "valid_check_types": [
        "required_fields", "unique_identifiers", "schema_validation",
        "duplicate_detection"
    ],
    "policies": {
        "railway_zones": {
            "checks": ["required_fields", "unique_identifiers"],
            "unique_key": "zone_code",
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_RETENTION_POLICY = {
    "description": "test",
    "version": "1.0.0",
    "valid_strategies": ["keep_latest", "archive_previous", "retain_versions"],
    "valid_cleanup_strategies": ["delete_oldest", "archive_oldest", "none"],
    "policies": {
        "railway_zones": {
            "strategy": "keep_latest",
            "maximum_versions": 3,
            "cleanup_strategy": "archive_oldest",
            "notes": "test"
        }
    },
    "notes": "test"
}

VALID_MERGE_POLICY = {
    "description": "test",
    "version": "1.0.0",
    "valid_conflict_resolutions": [
        "prefer_primary", "prefer_latest", "prefer_most_complete",
        "manual_review"
    ],
    "valid_overwrite_rules": ["always", "if_empty", "never", "manual"],
    "provider_priority": [
        {
            "provider_id": "indian_railways",
            "priority": 1,
            "role": "primary",
            "notes": "test"
        }
    ],
    "dataset_merge_policies": {
        "railway_zones": {
            "conflict_resolution": "prefer_primary",
            "overwrite_rule": "never",
            "canonical_field_preference": "indian_railways",
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

class TestPolicyLoading:
    """Tests for loading policy files."""

    def test_load_valid_policy(self, tmp_path):
        _write_json(tmp_path, "test.json", VALID_REFRESH_POLICY)
        data = policy_validator.load_policy_file(
            "test.json", policies_dir=str(tmp_path)
        )
        assert isinstance(data, dict)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            policy_validator.load_policy_file(
                "nonexistent.json", policies_dir=str(tmp_path)
            )

    def test_load_malformed_json_raises(self, tmp_path):
        bad = tmp_path / "broken.json"
        bad.write_text("{broken json!", encoding="utf-8")
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.load_policy_file(
                "broken.json", policies_dir=str(tmp_path)
            )
        assert "invalid JSON" in str(exc.value)

    def test_load_each_real_policy_file(self):
        """All 4 real policy files should load without error."""
        for filename in policy_validator.POLICY_FILES:
            data = policy_validator.load_policy_file(filename)
            assert isinstance(data, dict), f"{filename} did not load as dict"


# ---------------------------------------------------------------------------
# Refresh policy validation
# ---------------------------------------------------------------------------

class TestRefreshPolicy:
    """Tests for refresh_policy.json validation."""

    def test_valid_policy_passes(self):
        assert policy_validator.validate_refresh_policy(
            copy.deepcopy(VALID_REFRESH_POLICY), KNOWN_DATASET_IDS
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_REFRESH_POLICY)
        data["policies"]["nonexistent"] = data["policies"].pop("railway_zones")
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_refresh_policy(data, KNOWN_DATASET_IDS)
        assert "nonexistent" in str(exc.value)

    def test_invalid_strategy_raises(self):
        data = copy.deepcopy(VALID_REFRESH_POLICY)
        data["policies"]["railway_zones"]["strategy"] = "hourly"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_refresh_policy(data, KNOWN_DATASET_IDS)
        assert "hourly" in str(exc.value)

    def test_missing_strategy_raises(self):
        data = copy.deepcopy(VALID_REFRESH_POLICY)
        del data["policies"]["railway_zones"]["strategy"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_refresh_policy(data, KNOWN_DATASET_IDS)
        assert "strategy" in str(exc.value)

    def test_missing_policies_dict_raises(self):
        data = {"description": "test", "valid_strategies": ["manual"]}
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_refresh_policy(data, KNOWN_DATASET_IDS)
        assert "policies" in str(exc.value)

    def test_missing_notes_raises(self):
        data = copy.deepcopy(VALID_REFRESH_POLICY)
        del data["policies"]["railway_zones"]["notes"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_refresh_policy(data, KNOWN_DATASET_IDS)
        assert "notes" in str(exc.value)

    def test_non_dict_raises(self):
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_refresh_policy(
                ["not", "a", "dict"], KNOWN_DATASET_IDS
            )
        assert "invalid structure" in str(exc.value)


# ---------------------------------------------------------------------------
# Validation policy validation
# ---------------------------------------------------------------------------

class TestValidationPolicy:
    """Tests for validation_policy.json validation."""

    def test_valid_policy_passes(self):
        assert policy_validator.validate_validation_policy(
            copy.deepcopy(VALID_VALIDATION_POLICY), KNOWN_DATASET_IDS
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_VALIDATION_POLICY)
        data["policies"]["nonexistent"] = data["policies"].pop("railway_zones")
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_validation_policy(data, KNOWN_DATASET_IDS)
        assert "nonexistent" in str(exc.value)

    def test_invalid_check_type_raises(self):
        data = copy.deepcopy(VALID_VALIDATION_POLICY)
        data["policies"]["railway_zones"]["checks"].append("made_up_check")
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_validation_policy(data, KNOWN_DATASET_IDS)
        assert "made_up_check" in str(exc.value)

    def test_duplicate_check_types_raises(self):
        data = copy.deepcopy(VALID_VALIDATION_POLICY)
        data["policies"]["railway_zones"]["checks"] = [
            "required_fields", "required_fields"
        ]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_validation_policy(data, KNOWN_DATASET_IDS)
        assert "duplicate" in str(exc.value).lower()

    def test_missing_checks_raises(self):
        data = copy.deepcopy(VALID_VALIDATION_POLICY)
        del data["policies"]["railway_zones"]["checks"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_validation_policy(data, KNOWN_DATASET_IDS)
        assert "checks" in str(exc.value)

    def test_missing_unique_key_raises(self):
        data = copy.deepcopy(VALID_VALIDATION_POLICY)
        del data["policies"]["railway_zones"]["unique_key"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_validation_policy(data, KNOWN_DATASET_IDS)
        assert "unique_key" in str(exc.value)


# ---------------------------------------------------------------------------
# Retention policy validation
# ---------------------------------------------------------------------------

class TestRetentionPolicy:
    """Tests for retention_policy.json validation."""

    def test_valid_policy_passes(self):
        assert policy_validator.validate_retention_policy(
            copy.deepcopy(VALID_RETENTION_POLICY), KNOWN_DATASET_IDS
        ) is True

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        data["policies"]["nonexistent"] = data["policies"].pop("railway_zones")
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "nonexistent" in str(exc.value)

    def test_invalid_strategy_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        data["policies"]["railway_zones"]["strategy"] = "delete_everything"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "delete_everything" in str(exc.value)

    def test_invalid_cleanup_strategy_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        data["policies"]["railway_zones"]["cleanup_strategy"] = "burn"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "burn" in str(exc.value)

    def test_invalid_maximum_versions_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        data["policies"]["railway_zones"]["maximum_versions"] = 0
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "maximum_versions" in str(exc.value)

    def test_non_int_maximum_versions_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        data["policies"]["railway_zones"]["maximum_versions"] = "five"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "maximum_versions" in str(exc.value)

    def test_missing_strategy_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        del data["policies"]["railway_zones"]["strategy"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "strategy" in str(exc.value)

    def test_missing_cleanup_strategy_raises(self):
        data = copy.deepcopy(VALID_RETENTION_POLICY)
        del data["policies"]["railway_zones"]["cleanup_strategy"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_retention_policy(data, KNOWN_DATASET_IDS)
        assert "cleanup_strategy" in str(exc.value)


# ---------------------------------------------------------------------------
# Merge policy validation
# ---------------------------------------------------------------------------

class TestMergePolicy:
    """Tests for merge_policy.json validation."""

    def test_valid_policy_passes(self):
        assert policy_validator.validate_merge_policy(
            copy.deepcopy(VALID_MERGE_POLICY),
            KNOWN_DATASET_IDS,
            KNOWN_PROVIDER_IDS,
        ) is True

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        data["provider_priority"][0]["provider_id"] = "nonexistent_provider"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent_provider" in str(exc.value)

    def test_duplicate_provider_in_priority_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        data["provider_priority"].append(
            copy.deepcopy(data["provider_priority"][0])
        )
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        data["dataset_merge_policies"]["nonexistent"] = \
            data["dataset_merge_policies"].pop("railway_zones")
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_conflict_resolution_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        data["dataset_merge_policies"]["railway_zones"][
            "conflict_resolution"
        ] = "prefer_random"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "prefer_random" in str(exc.value)

    def test_invalid_overwrite_rule_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        data["dataset_merge_policies"]["railway_zones"][
            "overwrite_rule"
        ] = "sometimes"
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "sometimes" in str(exc.value)

    def test_missing_conflict_resolution_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        del data["dataset_merge_policies"]["railway_zones"][
            "conflict_resolution"
        ]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "conflict_resolution" in str(exc.value)

    def test_missing_provider_priority_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        del data["provider_priority"]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "provider_priority" in str(exc.value)

    def test_missing_canonical_field_preference_raises(self):
        data = copy.deepcopy(VALID_MERGE_POLICY)
        del data["dataset_merge_policies"]["railway_zones"][
            "canonical_field_preference"
        ]
        with pytest.raises(policy_validator.PolicyValidationError) as exc:
            policy_validator.validate_merge_policy(
                data, KNOWN_DATASET_IDS, KNOWN_PROVIDER_IDS
            )
        assert "canonical_field_preference" in str(exc.value)


# ---------------------------------------------------------------------------
# Full registry tests
# ---------------------------------------------------------------------------

class TestFullPolicyRegistry:
    """Tests for loading and validating the complete policy registry."""

    def test_complete_registry_loads(self):
        registry = policy_validator.load_and_validate_policy_registry(
            dataset_ids=KNOWN_DATASET_IDS,
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        assert len(registry) == 4
        for filename in policy_validator.POLICY_FILES:
            assert filename in registry

    def test_refresh_policy_covers_all_datasets(self):
        registry = policy_validator.load_and_validate_policy_registry(
            dataset_ids=KNOWN_DATASET_IDS,
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        rp = registry["refresh_policy.json"]
        assert KNOWN_DATASET_IDS == set(rp["policies"].keys())

    def test_validation_policy_covers_all_datasets(self):
        registry = policy_validator.load_and_validate_policy_registry(
            dataset_ids=KNOWN_DATASET_IDS,
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        vp = registry["validation_policy.json"]
        assert KNOWN_DATASET_IDS == set(vp["policies"].keys())

    def test_retention_policy_covers_all_datasets(self):
        registry = policy_validator.load_and_validate_policy_registry(
            dataset_ids=KNOWN_DATASET_IDS,
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        ret = registry["retention_policy.json"]
        assert KNOWN_DATASET_IDS == set(ret["policies"].keys())

    def test_merge_policy_covers_all_datasets(self):
        registry = policy_validator.load_and_validate_policy_registry(
            dataset_ids=KNOWN_DATASET_IDS,
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        mp = registry["merge_policy.json"]
        assert KNOWN_DATASET_IDS == set(mp["dataset_merge_policies"].keys())

    def test_merge_policy_covers_all_providers(self):
        registry = policy_validator.load_and_validate_policy_registry(
            dataset_ids=KNOWN_DATASET_IDS,
            provider_ids=KNOWN_PROVIDER_IDS,
        )
        mp = registry["merge_policy.json"]
        priority_providers = {
            e["provider_id"] for e in mp["provider_priority"]
        }
        assert KNOWN_PROVIDER_IDS == priority_providers
