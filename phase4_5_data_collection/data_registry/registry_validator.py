"""
Provider Registry Validator
Stage 3B.1.1 — RI-data-Collector

Scope: This module ONLY loads, validates, and registers provider metadata
files found in data_registry/providers/. It does not configure, contact,
or download anything from any provider. It performs no network activity.

Responsibilities:
    - Load provider JSON files (single-provider files) and the
      future_providers.json placeholder registry file (list-based file).
    - Validate structure and required fields for each provider record.
    - Detect duplicate provider ids across the registry.
    - Log lifecycle events: Provider Loaded, Provider Validated,
      Provider Registered, Completion.
"""

import json
import logging
import os

logger = logging.getLogger("provider_registry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

PROVIDERS_DIR = os.path.dirname(os.path.abspath(__file__))

# Single-provider metadata files (each file is one provider record).
SINGLE_PROVIDER_FILES = [
    "government_open_data.json",
    "indian_railways.json",
    "southern_railway.json",
    "cris.json",
    "openstreetmap.json",
    "wikipedia.json",
]

# Placeholder registry file (a list-based container for future providers).
PLACEHOLDER_REGISTRY_FILE = "future_providers.json"

REQUIRED_FIELDS = [
    "id",
    "display_name",
    "description",
    "country",
    "organization",
    "provider_type",
    "authentication_type",
    "supported_formats",
    "supported_protocols",
    "priority",
    "verification_status",
    "last_verified",
    "update_frequency",
    "license_reference",
    "documentation_reference",
    "datasets_supported",
    "notes",
]

LIST_FIELDS = ["supported_formats", "supported_protocols", "datasets_supported"]


class ProviderValidationError(Exception):
    """Raised when a provider record fails structural or field validation."""


def load_provider_file(filename):
    """Load a single provider JSON file from the providers directory."""
    path = os.path.join(PROVIDERS_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Provider file not found: {filename}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ProviderValidationError(f"{filename}: invalid JSON structure ({e})")

    logger.info("Provider Loaded: %s", filename)
    return data


def validate_provider(data, source_name="<unknown>"):
    """
    Validate a single provider record.

    Checks:
        - data is a JSON object (dict)
        - all required fields are present
        - list-type fields are actually lists
        - verification_status is a recognized value
        - id is a non-empty string

    Raises ProviderValidationError with a descriptive message on failure.
    Returns True if the record is valid.
    """
    if not isinstance(data, dict):
        raise ProviderValidationError(
            f"{source_name}: invalid structure — expected a JSON object, got {type(data).__name__}"
        )

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ProviderValidationError(
            f"{source_name}: missing mandatory keys: {', '.join(missing)}"
        )

    if not isinstance(data.get("id"), str) or not data.get("id").strip():
        raise ProviderValidationError(
            f"{source_name}: 'id' must be a non-empty string"
        )

    for field in LIST_FIELDS:
        if not isinstance(data.get(field), list):
            raise ProviderValidationError(
                f"{source_name}: field '{field}' must be a list, got {type(data.get(field)).__name__}"
            )

    valid_statuses = {"pending", "verified", "rejected", "expired"}
    status = data.get("verification_status")
    if status not in valid_statuses:
        raise ProviderValidationError(
            f"{source_name}: 'verification_status' must be one of {sorted(valid_statuses)}, got {status!r}"
        )

    logger.info("Provider Validated: %s (id=%s)", source_name, data["id"])
    return True


def load_and_validate_registry():
    """
    Load and validate every provider file in the registry.

    Returns a dict mapping provider id -> provider record.
    Raises ProviderValidationError on duplicate ids or invalid records.
    """
    registry = {}

    for filename in SINGLE_PROVIDER_FILES:
        data = load_provider_file(filename)
        validate_provider(data, source_name=filename)

        provider_id = data["id"]
        if provider_id in registry:
            raise ProviderValidationError(
                f"Duplicate provider id detected: '{provider_id}' "
                f"(already registered from another file, conflict in {filename})"
            )

        registry[provider_id] = data
        logger.info("Provider Registered: %s", provider_id)

    # future_providers.json is a placeholder list-based registry, validated
    # separately since it is not itself a single provider record.
    placeholder = load_provider_file(PLACEHOLDER_REGISTRY_FILE)
    if not isinstance(placeholder, dict) or "providers" not in placeholder:
        raise ProviderValidationError(
            f"{PLACEHOLDER_REGISTRY_FILE}: invalid structure — expected an object with a 'providers' list"
        )
    if not isinstance(placeholder["providers"], list):
        raise ProviderValidationError(
            f"{PLACEHOLDER_REGISTRY_FILE}: 'providers' must be a list"
        )

    for entry in placeholder["providers"]:
        validate_provider(entry, source_name=PLACEHOLDER_REGISTRY_FILE)
        provider_id = entry["id"]
        if provider_id in registry:
            raise ProviderValidationError(
                f"Duplicate provider id detected: '{provider_id}' "
                f"(conflict between {PLACEHOLDER_REGISTRY_FILE} and an existing provider file)"
            )
        registry[provider_id] = entry
        logger.info("Provider Registered: %s", provider_id)

    logger.info("Completion: loaded and registered %d provider(s)", len(registry))
    return registry


if __name__ == "__main__":
    load_and_validate_registry()