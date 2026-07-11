"""
Tests for the Stage 3B.1.5 Verification Registry.

Scope: Only tests verification file loading, structural validation,
reference verification, and full registry loading. Does not test any
actual verification, provider certification, or live services.
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

import verification_validator


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

VALID_VERIFIED_SOURCES = {
    "description": "test",
    "version": "1.0.0",
    "verified_providers": [],
    "verified_datasets": [],
    "notes": "test"
}

VALID_PENDING_REVIEW = {
    "description": "test",
    "version": "1.0.0",
    "valid_statuses": ["pending", "in_review", "approved", "rejected"],
    "pending_providers": [
        {
            "provider_id": "indian_railways",
            "status": "pending",
            "submitted_at": None,
            "reviewer": None,
            "notes": "test"
        }
    ],
    "pending_datasets": [],
    "notes": "test"
}

VALID_FAILED_SOURCES = {
    "description": "test",
    "version": "1.0.0",
    "failed_providers": [],
    "failed_datasets": [],
    "notes": "test"
}

VALID_VERIFICATION_LOG = {
    "description": "test",
    "version": "1.0.0",
    "valid_event_types": [
        "provider_submitted", "provider_reviewed",
        "provider_approved", "provider_rejected"
    ],
    "valid_outcomes": ["pending", "approved", "rejected", "deferred"],
    "entries": [],
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

class TestVerificationLoading:
    """Tests for loading verification files."""

    def test_load_valid_file(self, tmp_path):
        _write_json(tmp_path, "test.json", VALID_VERIFIED_SOURCES)
        data = verification_validator.load_verification_file(
            "test.json", verification_dir=str(tmp_path)
        )
        assert isinstance(data, dict)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            verification_validator.load_verification_file(
                "nonexistent.json", verification_dir=str(tmp_path)
            )

    def test_load_malformed_json_raises(self, tmp_path):
        bad = tmp_path / "broken.json"
        bad.write_text("{broken json!", encoding="utf-8")
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.load_verification_file(
                "broken.json", verification_dir=str(tmp_path)
            )
        assert "invalid JSON" in str(exc.value)

    def test_load_each_real_verification_file(self):
        """All 4 real verification files should load without error."""
        for filename in verification_validator.VERIFICATION_FILES:
            data = verification_validator.load_verification_file(filename)
            assert isinstance(data, dict), f"{filename} did not load as dict"


# ---------------------------------------------------------------------------
# Verified sources validation
# ---------------------------------------------------------------------------

class TestVerifiedSources:
    """Tests for verified_sources.json validation."""

    def test_valid_empty_passes(self):
        assert verification_validator.validate_verified_sources(
            copy.deepcopy(VALID_VERIFIED_SOURCES),
            KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
        ) is True

    def test_valid_with_entries_passes(self):
        data = copy.deepcopy(VALID_VERIFIED_SOURCES)
        data["verified_providers"] = [
            {"provider_id": "indian_railways", "verified_at": None}
        ]
        data["verified_datasets"] = [
            {"dataset_id": "railway_zones", "verified_at": None}
        ]
        assert verification_validator.validate_verified_sources(
            data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
        ) is True

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_VERIFIED_SOURCES)
        data["verified_providers"] = [
            {"provider_id": "nonexistent_provider"}
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verified_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_provider" in str(exc.value)

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_VERIFIED_SOURCES)
        data["verified_datasets"] = [
            {"dataset_id": "nonexistent_dataset"}
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verified_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_dataset" in str(exc.value)

    def test_duplicate_provider_raises(self):
        data = copy.deepcopy(VALID_VERIFIED_SOURCES)
        data["verified_providers"] = [
            {"provider_id": "indian_railways"},
            {"provider_id": "indian_railways"},
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verified_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_duplicate_dataset_raises(self):
        data = copy.deepcopy(VALID_VERIFIED_SOURCES)
        data["verified_datasets"] = [
            {"dataset_id": "railway_zones"},
            {"dataset_id": "railway_zones"},
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verified_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_non_dict_raises(self):
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verified_sources(
                ["not", "a", "dict"],
                KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "invalid structure" in str(exc.value)

    def test_missing_verified_providers_raises(self):
        data = {"verified_datasets": [], "notes": "test"}
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verified_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "verified_providers" in str(exc.value)


# ---------------------------------------------------------------------------
# Pending review validation
# ---------------------------------------------------------------------------

class TestPendingReview:
    """Tests for pending_review.json validation."""

    def test_valid_pending_passes(self):
        assert verification_validator.validate_pending_review(
            copy.deepcopy(VALID_PENDING_REVIEW),
            KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
        ) is True

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_PENDING_REVIEW)
        data["pending_providers"][0]["provider_id"] = "nonexistent"
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_pending_review(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_status_raises(self):
        data = copy.deepcopy(VALID_PENDING_REVIEW)
        data["pending_providers"][0]["status"] = "definitely_verified"
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_pending_review(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "definitely_verified" in str(exc.value)

    def test_duplicate_provider_raises(self):
        data = copy.deepcopy(VALID_PENDING_REVIEW)
        data["pending_providers"].append(
            copy.deepcopy(data["pending_providers"][0])
        )
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_pending_review(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_missing_status_field_raises(self):
        data = copy.deepcopy(VALID_PENDING_REVIEW)
        del data["pending_providers"][0]["status"]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_pending_review(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "status" in str(exc.value)

    def test_missing_valid_statuses_raises(self):
        data = copy.deepcopy(VALID_PENDING_REVIEW)
        del data["valid_statuses"]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_pending_review(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "valid_statuses" in str(exc.value)

    def test_pending_dataset_with_invalid_reference_raises(self):
        data = copy.deepcopy(VALID_PENDING_REVIEW)
        data["pending_datasets"] = [
            {"dataset_id": "nonexistent_ds", "status": "pending", "notes": "test"}
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_pending_review(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_ds" in str(exc.value)


# ---------------------------------------------------------------------------
# Failed sources validation
# ---------------------------------------------------------------------------

class TestFailedSources:
    """Tests for failed_sources.json validation."""

    def test_valid_empty_passes(self):
        assert verification_validator.validate_failed_sources(
            copy.deepcopy(VALID_FAILED_SOURCES),
            KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
        ) is True

    def test_invalid_provider_reference_raises(self):
        data = copy.deepcopy(VALID_FAILED_SOURCES)
        data["failed_providers"] = [
            {"provider_id": "nonexistent", "reason": "test"}
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_failed_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent" in str(exc.value)

    def test_invalid_dataset_reference_raises(self):
        data = copy.deepcopy(VALID_FAILED_SOURCES)
        data["failed_datasets"] = [
            {"dataset_id": "nonexistent_ds", "reason": "test"}
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_failed_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_ds" in str(exc.value)

    def test_duplicate_failed_provider_raises(self):
        data = copy.deepcopy(VALID_FAILED_SOURCES)
        data["failed_providers"] = [
            {"provider_id": "indian_railways"},
            {"provider_id": "indian_railways"},
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_failed_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "duplicate" in str(exc.value).lower()

    def test_missing_failed_providers_raises(self):
        data = {"failed_datasets": [], "notes": "test"}
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_failed_sources(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "failed_providers" in str(exc.value)


# ---------------------------------------------------------------------------
# Verification log validation
# ---------------------------------------------------------------------------

class TestVerificationLog:
    """Tests for verification_log.json validation."""

    def test_valid_empty_log_passes(self):
        assert verification_validator.validate_verification_log(
            copy.deepcopy(VALID_VERIFICATION_LOG),
            KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
        ) is True

    def test_valid_log_entry_passes(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["entries"] = [
            {
                "event_type": "provider_submitted",
                "target_type": "provider",
                "target_id": "indian_railways",
                "outcome": "pending",
                "timestamp": None
            }
        ]
        assert verification_validator.validate_verification_log(
            data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
        ) is True

    def test_invalid_event_type_raises(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["entries"] = [
            {
                "event_type": "made_up_event",
                "target_type": "provider",
                "target_id": "indian_railways",
                "outcome": "pending"
            }
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "made_up_event" in str(exc.value)

    def test_invalid_outcome_raises(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["entries"] = [
            {
                "event_type": "provider_submitted",
                "target_type": "provider",
                "target_id": "indian_railways",
                "outcome": "maybe"
            }
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "maybe" in str(exc.value)

    def test_invalid_target_type_raises(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["entries"] = [
            {
                "event_type": "provider_submitted",
                "target_type": "something_else",
                "target_id": "indian_railways",
                "outcome": "pending"
            }
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "target_type" in str(exc.value)

    def test_invalid_provider_target_raises(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["entries"] = [
            {
                "event_type": "provider_submitted",
                "target_type": "provider",
                "target_id": "nonexistent_provider",
                "outcome": "pending"
            }
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_provider" in str(exc.value)

    def test_invalid_dataset_target_raises(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["valid_event_types"].append("dataset_submitted")
        data["entries"] = [
            {
                "event_type": "dataset_submitted",
                "target_type": "dataset",
                "target_id": "nonexistent_dataset",
                "outcome": "pending"
            }
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "nonexistent_dataset" in str(exc.value)

    def test_missing_entries_raises(self):
        data = {
            "valid_event_types": ["provider_submitted"],
            "valid_outcomes": ["pending"]
        }
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "entries" in str(exc.value)

    def test_missing_required_field_in_entry_raises(self):
        data = copy.deepcopy(VALID_VERIFICATION_LOG)
        data["entries"] = [
            {
                "event_type": "provider_submitted",
                "target_type": "provider",
                # missing target_id and outcome
            }
        ]
        with pytest.raises(verification_validator.VerificationValidationError) as exc:
            verification_validator.validate_verification_log(
                data, KNOWN_PROVIDER_IDS, KNOWN_DATASET_IDS
            )
        assert "missing required field" in str(exc.value)


# ---------------------------------------------------------------------------
# Full registry tests
# ---------------------------------------------------------------------------

class TestFullVerificationRegistry:
    """Tests for loading and validating the complete verification registry."""

    def test_complete_registry_loads(self):
        registry = verification_validator.load_and_validate_verification_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        assert len(registry) == 4
        for filename in verification_validator.VERIFICATION_FILES:
            assert filename in registry

    def test_verified_sources_initially_empty(self):
        registry = verification_validator.load_and_validate_verification_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        vs = registry["verified_sources.json"]
        assert vs["verified_providers"] == []
        assert vs["verified_datasets"] == []

    def test_pending_review_has_all_providers(self):
        registry = verification_validator.load_and_validate_verification_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        pr = registry["pending_review.json"]
        pending_ids = {e["provider_id"] for e in pr["pending_providers"]}
        assert KNOWN_PROVIDER_IDS == pending_ids

    def test_all_pending_providers_are_pending(self):
        registry = verification_validator.load_and_validate_verification_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        pr = registry["pending_review.json"]
        for entry in pr["pending_providers"]:
            assert entry["status"] == "pending", (
                f"Provider '{entry['provider_id']}' should be pending"
            )

    def test_failed_sources_initially_empty(self):
        registry = verification_validator.load_and_validate_verification_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        fs = registry["failed_sources.json"]
        assert fs["failed_providers"] == []
        assert fs["failed_datasets"] == []

    def test_verification_log_initially_empty(self):
        registry = verification_validator.load_and_validate_verification_registry(
            provider_ids=KNOWN_PROVIDER_IDS,
            dataset_ids=KNOWN_DATASET_IDS,
        )
        vl = registry["verification_log.json"]
        assert vl["entries"] == []
