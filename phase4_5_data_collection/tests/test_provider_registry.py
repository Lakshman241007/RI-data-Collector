"""
Tests for the Stage 3B.1.1 Provider Registry.

Scope: Only tests provider loading and validation, as specified for this
stage. Does not test collectors, downloads, authentication, or any
provider configuration, since none of that is in scope for this stage.
"""

import copy
import json
import os
from wsgiref.validate import validator

import pytest

import registry_validator


VALID_PROVIDER = {
    "id": "test_provider",
    "display_name": "Test Provider",
    "description": "A test provider used only for unit tests.",
    "country": "",
    "organization": "",
    "provider_type": "test",
    "authentication_type": None,
    "supported_formats": [],
    "supported_protocols": [],
    "priority": None,
    "verification_status": "pending",
    "last_verified": None,
    "update_frequency": None,
    "license_reference": "",
    "documentation_reference": "",
    "datasets_supported": [],
    "notes": "test",
}


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------

def test_load_each_single_provider_file_succeeds():
    for filename in registry_validator.SINGLE_PROVIDER_FILES:
        data = registry_validator.load_provider_file(filename)
        assert isinstance(data, dict)


def test_load_future_providers_placeholder_succeeds():
    data = registry_validator.load_provider_file(registry_validator.PLACEHOLDER_REGISTRY_FILE)
    assert isinstance(data, dict)
    assert "providers" in data
    assert data["providers"] == []


def test_load_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        registry_validator.load_provider_file("does_not_exist.json")


def test_load_invalid_json_raises_validation_error(tmp_path, monkeypatch):
    bad_file = tmp_path / "broken.json"
    bad_file.write_text("{not valid json")
    monkeypatch.setattr(registry_validator, "PROVIDERS_DIR", str(tmp_path))
    with pytest.raises(registry_validator.ProviderValidationError):
        registry_validator.load_provider_file("broken.json")


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_valid_provider_passes_validation():
    assert registry_validator.validate_provider(copy.deepcopy(VALID_PROVIDER), "unit_test") is True


def test_validation_fails_on_missing_required_field():
    broken = copy.deepcopy(VALID_PROVIDER)
    del broken["organization"]
    with pytest.raises(registry_validator.ProviderValidationError) as exc:
        registry_validator.validate_provider(broken, "unit_test")
    assert "missing mandatory keys" in str(exc.value)
    assert "organization" in str(exc.value)


def test_validation_fails_on_non_dict_structure():
    with pytest.raises(registry_validator.ProviderValidationError) as exc:
        registry_validator.validate_provider(["not", "a", "dict"], "unit_test")
    assert "invalid structure" in str(exc.value)


def test_validation_fails_on_empty_id():
    broken = copy.deepcopy(VALID_PROVIDER)
    broken["id"] = ""
    with pytest.raises(registry_validator.ProviderValidationError) as exc:
        registry_validator.validate_provider(broken, "unit_test")
    assert "'id'" in str(exc.value)


def test_validation_fails_on_non_list_field():
    broken = copy.deepcopy(VALID_PROVIDER)
    broken["supported_formats"] = "csv"
    with pytest.raises(registry_validator.ProviderValidationError) as exc:
        registry_validator.validate_provider(broken, "unit_test")
    assert "supported_formats" in str(exc.value)


def test_validation_fails_on_invalid_verification_status():
    broken = copy.deepcopy(VALID_PROVIDER)
    broken["verification_status"] = "definitely_verified"
    with pytest.raises(registry_validator.ProviderValidationError) as exc:
        registry_validator.validate_provider(broken, "unit_test")
    assert "verification_status" in str(exc.value)


# ---------------------------------------------------------------------------
# Full registry tests
# ---------------------------------------------------------------------------

def test_full_registry_loads_and_validates_without_error():
    registry = registry_validator.load_and_validate_registry()
    expected_ids = {
        "government_open_data",
        "indian_railways",
        "southern_railway",
        "cris",
        "openstreetmap",
        "wikipedia",
    }
    assert expected_ids.issubset(set(registry.keys()))


def test_all_registered_providers_start_as_pending():
    registry = registry_validator.load_and_validate_registry()
    for provider_id, data in registry.items():
        assert data["verification_status"] == "pending", (
            f"Provider '{provider_id}' should start as 'pending', "
            f"found '{data['verification_status']}'"
        )


def test_no_duplicate_ids_in_registry():
    registry = registry_validator.load_and_validate_registry()
    ids = list(registry.keys())
    assert len(ids) == len(set(ids)), "Duplicate provider ids found in registry"