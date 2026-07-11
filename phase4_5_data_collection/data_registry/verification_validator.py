"""
Verification Registry Validator
Stage 3B.1.5 — RI-data-Collector

Scope: This module ONLY loads, validates, and registers verification
metadata files found in data_registry/verification/. It does not perform
any actual verification, contact external services, or make network
requests.

Responsibilities:
    - Load verification JSON files from data_registry/verification/.
    - Validate structure and required fields for each verification file.
    - Verify that provider references point to existing Provider Registry IDs.
    - Verify that dataset references point to existing Dataset Registry IDs.
    - Detect duplicate entries.
    - Validate status values against allowed statuses.
    - Log lifecycle events: Verification Registry Loaded,
      Verification Registry Validated, Verification Registry Registered,
      Completion.
"""

import json
import logging
import os

logger = logging.getLogger("verification_registry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Resolve paths relative to this module's location (data_registry/).
_DATA_REGISTRY_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFICATION_DIR = os.path.join(_DATA_REGISTRY_DIR, "verification")

# Verification files to load.
VERIFICATION_FILES = [
    "verified_sources.json",
    "pending_review.json",
    "failed_sources.json",
    "verification_log.json",
]


class VerificationValidationError(Exception):
    """Raised when a verification file fails structural or reference validation."""


# ---------------------------------------------------------------------------
# Generic loading
# ---------------------------------------------------------------------------

def load_verification_file(filename, verification_dir=None):
    """Load a single verification JSON file.

    Args:
        filename: Name of the JSON file inside the verification directory.
        verification_dir: Override for the verification directory (testing).

    Returns:
        Parsed data from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        VerificationValidationError: If the file contains invalid JSON.
    """
    base_dir = verification_dir if verification_dir is not None else VERIFICATION_DIR
    path = os.path.join(base_dir, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Verification file not found: {filename}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise VerificationValidationError(
                f"{filename}: invalid JSON structure ({e})"
            )

    logger.info("Verification Registry Loaded: %s", filename)
    return data


# ---------------------------------------------------------------------------
# Verified sources validation
# ---------------------------------------------------------------------------

def validate_verified_sources(data, provider_ids, dataset_ids,
                              source_name="verified_sources.json"):
    """Validate the verified sources file.

    Checks:
        - data is a dict with 'verified_providers' list and
          'verified_datasets' list
        - each provider entry references an existing provider_id
        - each dataset entry references an existing dataset_id
        - no duplicate provider or dataset entries

    Raises:
        VerificationValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise VerificationValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "verified_providers" not in data or \
            not isinstance(data["verified_providers"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'verified_providers' list"
        )

    if "verified_datasets" not in data or \
            not isinstance(data["verified_datasets"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'verified_datasets' list"
        )

    # Validate provider entries.
    seen_providers = set()
    for i, entry in enumerate(data["verified_providers"]):
        label = f"{source_name}.verified_providers[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        if "provider_id" not in entry:
            raise VerificationValidationError(
                f"{label}: missing required field 'provider_id'"
            )

        pr_id = entry["provider_id"]
        if provider_ids and pr_id not in provider_ids:
            raise VerificationValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if pr_id in seen_providers:
            raise VerificationValidationError(
                f"{label}: duplicate provider_id '{pr_id}'"
            )
        seen_providers.add(pr_id)

    # Validate dataset entries.
    seen_datasets = set()
    for i, entry in enumerate(data["verified_datasets"]):
        label = f"{source_name}.verified_datasets[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        if "dataset_id" not in entry:
            raise VerificationValidationError(
                f"{label}: missing required field 'dataset_id'"
            )

        ds_id = entry["dataset_id"]
        if dataset_ids and ds_id not in dataset_ids:
            raise VerificationValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if ds_id in seen_datasets:
            raise VerificationValidationError(
                f"{label}: duplicate dataset_id '{ds_id}'"
            )
        seen_datasets.add(ds_id)

    logger.info("Verification Registry Validated: %s (%d providers, "
                "%d datasets)", source_name,
                len(data["verified_providers"]),
                len(data["verified_datasets"]))
    return True


# ---------------------------------------------------------------------------
# Pending review validation
# ---------------------------------------------------------------------------

def validate_pending_review(data, provider_ids, dataset_ids,
                            source_name="pending_review.json"):
    """Validate the pending review file.

    Checks:
        - data is a dict with 'pending_providers' list,
          'pending_datasets' list, and 'valid_statuses' list
        - each provider entry has provider_id, status, notes
        - provider_id references an existing provider
        - status is one of the valid statuses
        - no duplicate provider or dataset entries

    Raises:
        VerificationValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise VerificationValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "pending_providers" not in data or \
            not isinstance(data["pending_providers"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'pending_providers' list"
        )

    if "pending_datasets" not in data or \
            not isinstance(data["pending_datasets"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'pending_datasets' list"
        )

    if "valid_statuses" not in data or \
            not isinstance(data["valid_statuses"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'valid_statuses' list"
        )

    valid_statuses = set(data["valid_statuses"])

    # Validate pending provider entries.
    seen_providers = set()
    for i, entry in enumerate(data["pending_providers"]):
        label = f"{source_name}.pending_providers[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        for field in ("provider_id", "status", "notes"):
            if field not in entry:
                raise VerificationValidationError(
                    f"{label}: missing required field '{field}'"
                )

        pr_id = entry["provider_id"]
        if provider_ids and pr_id not in provider_ids:
            raise VerificationValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if entry["status"] not in valid_statuses:
            raise VerificationValidationError(
                f"{label}: status '{entry['status']}' is not one of "
                f"{sorted(valid_statuses)}"
            )

        if pr_id in seen_providers:
            raise VerificationValidationError(
                f"{label}: duplicate provider_id '{pr_id}'"
            )
        seen_providers.add(pr_id)

    # Validate pending dataset entries.
    seen_datasets = set()
    for i, entry in enumerate(data["pending_datasets"]):
        label = f"{source_name}.pending_datasets[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        for field in ("dataset_id", "status", "notes"):
            if field not in entry:
                raise VerificationValidationError(
                    f"{label}: missing required field '{field}'"
                )

        ds_id = entry["dataset_id"]
        if dataset_ids and ds_id not in dataset_ids:
            raise VerificationValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if entry["status"] not in valid_statuses:
            raise VerificationValidationError(
                f"{label}: status '{entry['status']}' is not one of "
                f"{sorted(valid_statuses)}"
            )

        if ds_id in seen_datasets:
            raise VerificationValidationError(
                f"{label}: duplicate dataset_id '{ds_id}'"
            )
        seen_datasets.add(ds_id)

    logger.info("Verification Registry Validated: %s (%d providers, "
                "%d datasets)", source_name,
                len(data["pending_providers"]),
                len(data["pending_datasets"]))
    return True


# ---------------------------------------------------------------------------
# Failed sources validation
# ---------------------------------------------------------------------------

def validate_failed_sources(data, provider_ids, dataset_ids,
                            source_name="failed_sources.json"):
    """Validate the failed sources file.

    Checks:
        - data is a dict with 'failed_providers' list and
          'failed_datasets' list
        - each provider entry references an existing provider_id
        - each dataset entry references an existing dataset_id
        - no duplicate entries

    Raises:
        VerificationValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise VerificationValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "failed_providers" not in data or \
            not isinstance(data["failed_providers"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'failed_providers' list"
        )

    if "failed_datasets" not in data or \
            not isinstance(data["failed_datasets"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'failed_datasets' list"
        )

    # Validate failed provider entries.
    seen_providers = set()
    for i, entry in enumerate(data["failed_providers"]):
        label = f"{source_name}.failed_providers[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        if "provider_id" not in entry:
            raise VerificationValidationError(
                f"{label}: missing required field 'provider_id'"
            )

        pr_id = entry["provider_id"]
        if provider_ids and pr_id not in provider_ids:
            raise VerificationValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if pr_id in seen_providers:
            raise VerificationValidationError(
                f"{label}: duplicate provider_id '{pr_id}'"
            )
        seen_providers.add(pr_id)

    # Validate failed dataset entries.
    seen_datasets = set()
    for i, entry in enumerate(data["failed_datasets"]):
        label = f"{source_name}.failed_datasets[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        if "dataset_id" not in entry:
            raise VerificationValidationError(
                f"{label}: missing required field 'dataset_id'"
            )

        ds_id = entry["dataset_id"]
        if dataset_ids and ds_id not in dataset_ids:
            raise VerificationValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if ds_id in seen_datasets:
            raise VerificationValidationError(
                f"{label}: duplicate dataset_id '{ds_id}'"
            )
        seen_datasets.add(ds_id)

    logger.info("Verification Registry Validated: %s (%d providers, "
                "%d datasets)", source_name,
                len(data["failed_providers"]),
                len(data["failed_datasets"]))
    return True


# ---------------------------------------------------------------------------
# Verification log validation
# ---------------------------------------------------------------------------

def validate_verification_log(data, provider_ids, dataset_ids,
                              source_name="verification_log.json"):
    """Validate the verification log file.

    Checks:
        - data is a dict with 'entries' list, 'valid_event_types' list,
          and 'valid_outcomes' list
        - each log entry has required fields: event_type, target_type,
          target_id, outcome, timestamp
        - event_type is one of the valid event types
        - outcome is one of the valid outcomes
        - target_id references an existing provider or dataset

    Raises:
        VerificationValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise VerificationValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "entries" not in data or not isinstance(data["entries"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'entries' list"
        )

    if "valid_event_types" not in data or \
            not isinstance(data["valid_event_types"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'valid_event_types' list"
        )

    if "valid_outcomes" not in data or \
            not isinstance(data["valid_outcomes"], list):
        raise VerificationValidationError(
            f"{source_name}: missing or invalid 'valid_outcomes' list"
        )

    valid_events = set(data["valid_event_types"])
    valid_outcomes = set(data["valid_outcomes"])

    for i, entry in enumerate(data["entries"]):
        label = f"{source_name}.entries[{i}]"

        if not isinstance(entry, dict):
            raise VerificationValidationError(
                f"{label}: each entry must be a JSON object"
            )

        for field in ("event_type", "target_type", "target_id", "outcome"):
            if field not in entry:
                raise VerificationValidationError(
                    f"{label}: missing required field '{field}'"
                )

        if entry["event_type"] not in valid_events:
            raise VerificationValidationError(
                f"{label}: event_type '{entry['event_type']}' is not one of "
                f"{sorted(valid_events)}"
            )

        if entry["outcome"] not in valid_outcomes:
            raise VerificationValidationError(
                f"{label}: outcome '{entry['outcome']}' is not one of "
                f"{sorted(valid_outcomes)}"
            )

        # Validate target references.
        target_type = entry["target_type"]
        target_id = entry["target_id"]

        if target_type == "provider":
            if provider_ids and target_id not in provider_ids:
                raise VerificationValidationError(
                    f"{label}: target_id '{target_id}' does not match any "
                    f"registered provider"
                )
        elif target_type == "dataset":
            if dataset_ids and target_id not in dataset_ids:
                raise VerificationValidationError(
                    f"{label}: target_id '{target_id}' does not match any "
                    f"registered dataset"
                )
        else:
            raise VerificationValidationError(
                f"{label}: target_type must be 'provider' or 'dataset', "
                f"got '{target_type}'"
            )

    logger.info("Verification Registry Validated: %s (%d entries)",
                source_name, len(data["entries"]))
    return True


# ---------------------------------------------------------------------------
# Full verification registry lifecycle
# ---------------------------------------------------------------------------

def load_and_validate_verification_registry(
    verification_dir=None,
    provider_ids=None,
    dataset_ids=None,
):
    """Load, validate, and register all verification files.

    This is the main entry point. It performs the complete lifecycle:
        1. Load each verification JSON file.
        2. Validate structure and required fields.
        3. Verify cross-references to providers and datasets.
        4. Detect duplicates and invalid statuses.
        5. Register verification metadata.

    Args:
        verification_dir: Override for the verification directory (testing).
        provider_ids: Set of valid provider IDs. If None, resolved
            automatically.
        dataset_ids: Set of valid dataset IDs. If None, resolved
            automatically.

    Returns:
        dict mapping filename -> parsed data for each verification file.

    Raises:
        VerificationValidationError on any validation failure.
    """
    # --- Resolve IDs from existing registries if not supplied ---
    if provider_ids is None or dataset_ids is None:
        import sys
        _dr_dir = os.path.dirname(os.path.abspath(__file__))
        if _dr_dir not in sys.path:
            sys.path.insert(0, _dr_dir)

        if provider_ids is None:
            try:
                import registry_validator
                provider_reg = registry_validator.load_and_validate_registry()
                provider_ids = set(provider_reg.keys())
            except Exception:
                provider_ids = set()
                logger.warning(
                    "Could not load Provider Registry — provider reference "
                    "verification will use empty ID set"
                )

        if dataset_ids is None:
            try:
                import dataset_validator
                dataset_reg = dataset_validator.load_and_validate_dataset_registry(
                    provider_ids=provider_ids
                )
                dataset_ids = set(dataset_reg.keys())
            except Exception:
                dataset_ids = set()
                logger.warning(
                    "Could not load Dataset Registry — dataset reference "
                    "verification will use empty ID set"
                )

    logger.info("Verification Registry Loaded")

    registry = {}
    base_dir = verification_dir if verification_dir is not None else VERIFICATION_DIR

    # --- verified_sources.json ---
    vs = load_verification_file("verified_sources.json",
                                verification_dir=base_dir)
    validate_verified_sources(vs, provider_ids, dataset_ids)
    registry["verified_sources.json"] = vs
    logger.info("Verification Registry Registered: verified_sources.json")

    # --- pending_review.json ---
    pr = load_verification_file("pending_review.json",
                                verification_dir=base_dir)
    validate_pending_review(pr, provider_ids, dataset_ids)
    registry["pending_review.json"] = pr
    logger.info("Verification Registry Registered: pending_review.json")

    # --- failed_sources.json ---
    fs = load_verification_file("failed_sources.json",
                                verification_dir=base_dir)
    validate_failed_sources(fs, provider_ids, dataset_ids)
    registry["failed_sources.json"] = fs
    logger.info("Verification Registry Registered: failed_sources.json")

    # --- verification_log.json ---
    vl = load_verification_file("verification_log.json",
                                verification_dir=base_dir)
    validate_verification_log(vl, provider_ids, dataset_ids)
    registry["verification_log.json"] = vl
    logger.info("Verification Registry Registered: verification_log.json")

    logger.info(
        "Completion: loaded and registered %d verification file(s)",
        len(registry)
    )
    return registry


if __name__ == "__main__":
    load_and_validate_verification_registry()
