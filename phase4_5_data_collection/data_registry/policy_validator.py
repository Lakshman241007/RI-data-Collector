"""
Policy Registry Validator
Stage 3B.1.4 — RI-data-Collector

Scope: This module ONLY loads, validates, and registers policy descriptor
files found in data_registry/policies/. It does not execute any policy
logic, schedule refreshes, run validation engines, perform cleanup, or
make any network requests.

Responsibilities:
    - Load policy JSON files from data_registry/policies/.
    - Validate structure and required fields for each policy file.
    - Verify that dataset references point to existing Dataset Registry IDs.
    - Verify that provider references in merge policy point to existing
      Provider Registry IDs.
    - Detect duplicate policy entries.
    - Log lifecycle events: Policies Loaded, Policies Validated,
      Policies Registered, Completion.
"""

import json
import logging
import os

logger = logging.getLogger("policy_registry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Resolve paths relative to this module's location (data_registry/).
_DATA_REGISTRY_DIR = os.path.dirname(os.path.abspath(__file__))
POLICIES_DIR = os.path.join(_DATA_REGISTRY_DIR, "policies")

# Policy files to load.
POLICY_FILES = [
    "refresh_policy.json",
    "validation_policy.json",
    "retention_policy.json",
    "merge_policy.json",
]


class PolicyValidationError(Exception):
    """Raised when a policy file fails structural or reference validation."""


# ---------------------------------------------------------------------------
# Generic loading
# ---------------------------------------------------------------------------

def load_policy_file(filename, policies_dir=None):
    """Load a single policy JSON file.

    Args:
        filename: Name of the JSON file inside the policies directory.
        policies_dir: Override for the policies directory path (testing).

    Returns:
        Parsed data from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        PolicyValidationError: If the file contains invalid JSON.
    """
    base_dir = policies_dir if policies_dir is not None else POLICIES_DIR
    path = os.path.join(base_dir, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Policy file not found: {filename}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise PolicyValidationError(
                f"{filename}: invalid JSON structure ({e})"
            )

    logger.info("Policies Loaded: %s", filename)
    return data


# ---------------------------------------------------------------------------
# Refresh policy validation
# ---------------------------------------------------------------------------

def validate_refresh_policy(data, dataset_ids,
                            source_name="refresh_policy.json"):
    """Validate the refresh policy file.

    Checks:
        - data is a dict with 'policies' dict and 'valid_strategies' list
        - each key in 'policies' is a recognized dataset_id
        - each entry has 'strategy' and 'notes'
        - strategy is one of the valid strategies
        - no duplicate dataset entries (guaranteed by dict keys)

    Raises:
        PolicyValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "policies" not in data or not isinstance(data["policies"], dict):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'policies' dict"
        )

    if "valid_strategies" not in data or \
            not isinstance(data["valid_strategies"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'valid_strategies' list"
        )

    valid_strategies = set(data["valid_strategies"])

    for ds_id, entry in data["policies"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise PolicyValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise PolicyValidationError(
                f"{label}: policy entry must be a JSON object"
            )

        if "strategy" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'strategy'"
            )

        if entry["strategy"] not in valid_strategies:
            raise PolicyValidationError(
                f"{label}: strategy '{entry['strategy']}' is not one of "
                f"{sorted(valid_strategies)}"
            )

        if "notes" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Policies Validated: %s (%d entries)", source_name,
                len(data["policies"]))
    return True


# ---------------------------------------------------------------------------
# Validation policy validation
# ---------------------------------------------------------------------------

def validate_validation_policy(data, dataset_ids,
                               source_name="validation_policy.json"):
    """Validate the validation policy file.

    Checks:
        - data is a dict with 'policies' dict and 'valid_check_types' list
        - each key in 'policies' is a recognized dataset_id
        - each entry has 'checks' (list), 'unique_key' (str), and 'notes'
        - all checks are from the valid_check_types list

    Raises:
        PolicyValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "policies" not in data or not isinstance(data["policies"], dict):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'policies' dict"
        )

    if "valid_check_types" not in data or \
            not isinstance(data["valid_check_types"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'valid_check_types' list"
        )

    valid_checks = set(data["valid_check_types"])

    for ds_id, entry in data["policies"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise PolicyValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise PolicyValidationError(
                f"{label}: policy entry must be a JSON object"
            )

        if "checks" not in entry or not isinstance(entry["checks"], list):
            raise PolicyValidationError(
                f"{label}: missing or invalid 'checks' list"
            )

        for check in entry["checks"]:
            if check not in valid_checks:
                raise PolicyValidationError(
                    f"{label}: check '{check}' is not one of "
                    f"{sorted(valid_checks)}"
                )

        # Detect duplicate checks within a single dataset entry.
        if len(entry["checks"]) != len(set(entry["checks"])):
            raise PolicyValidationError(
                f"{label}: duplicate check types detected"
            )

        if "unique_key" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'unique_key'"
            )

        if "notes" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Policies Validated: %s (%d entries)", source_name,
                len(data["policies"]))
    return True


# ---------------------------------------------------------------------------
# Retention policy validation
# ---------------------------------------------------------------------------

def validate_retention_policy(data, dataset_ids,
                              source_name="retention_policy.json"):
    """Validate the retention policy file.

    Checks:
        - data is a dict with 'policies' dict, 'valid_strategies' list,
          and 'valid_cleanup_strategies' list
        - each key in 'policies' is a recognized dataset_id
        - each entry has 'strategy', 'maximum_versions', 'cleanup_strategy',
          and 'notes'
        - strategy is one of the valid strategies
        - cleanup_strategy is one of the valid cleanup strategies
        - maximum_versions is a positive integer

    Raises:
        PolicyValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "policies" not in data or not isinstance(data["policies"], dict):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'policies' dict"
        )

    if "valid_strategies" not in data or \
            not isinstance(data["valid_strategies"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'valid_strategies' list"
        )

    if "valid_cleanup_strategies" not in data or \
            not isinstance(data["valid_cleanup_strategies"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'valid_cleanup_strategies' list"
        )

    valid_strategies = set(data["valid_strategies"])
    valid_cleanup = set(data["valid_cleanup_strategies"])

    for ds_id, entry in data["policies"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise PolicyValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise PolicyValidationError(
                f"{label}: policy entry must be a JSON object"
            )

        if "strategy" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'strategy'"
            )

        if entry["strategy"] not in valid_strategies:
            raise PolicyValidationError(
                f"{label}: strategy '{entry['strategy']}' is not one of "
                f"{sorted(valid_strategies)}"
            )

        if "maximum_versions" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'maximum_versions'"
            )

        if not isinstance(entry["maximum_versions"], int) or \
                entry["maximum_versions"] < 1:
            raise PolicyValidationError(
                f"{label}: 'maximum_versions' must be a positive integer"
            )

        if "cleanup_strategy" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'cleanup_strategy'"
            )

        if entry["cleanup_strategy"] not in valid_cleanup:
            raise PolicyValidationError(
                f"{label}: cleanup_strategy '{entry['cleanup_strategy']}' "
                f"is not one of {sorted(valid_cleanup)}"
            )

        if "notes" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Policies Validated: %s (%d entries)", source_name,
                len(data["policies"]))
    return True


# ---------------------------------------------------------------------------
# Merge policy validation
# ---------------------------------------------------------------------------

def validate_merge_policy(data, dataset_ids, provider_ids,
                          source_name="merge_policy.json"):
    """Validate the merge policy file.

    Checks:
        - data is a dict with 'provider_priority' list,
          'dataset_merge_policies' dict, 'valid_conflict_resolutions' list,
          and 'valid_overwrite_rules' list
        - provider_priority entries reference existing providers
        - no duplicate providers in priority list
        - dataset_merge_policies keys are recognized dataset_ids
        - each dataset entry has 'conflict_resolution', 'overwrite_rule',
          'canonical_field_preference', and 'notes'
        - conflict_resolution is one of the valid values
        - overwrite_rule is one of the valid values

    Raises:
        PolicyValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise PolicyValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "provider_priority" not in data or \
            not isinstance(data["provider_priority"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'provider_priority' list"
        )

    if "dataset_merge_policies" not in data or \
            not isinstance(data["dataset_merge_policies"], dict):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'dataset_merge_policies' dict"
        )

    if "valid_conflict_resolutions" not in data or \
            not isinstance(data["valid_conflict_resolutions"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'valid_conflict_resolutions' list"
        )

    if "valid_overwrite_rules" not in data or \
            not isinstance(data["valid_overwrite_rules"], list):
        raise PolicyValidationError(
            f"{source_name}: missing or invalid 'valid_overwrite_rules' list"
        )

    valid_resolutions = set(data["valid_conflict_resolutions"])
    valid_overwrites = set(data["valid_overwrite_rules"])

    # Validate provider priority list.
    seen_providers = set()
    for i, entry in enumerate(data["provider_priority"]):
        label = f"{source_name}.provider_priority[{i}]"

        if not isinstance(entry, dict):
            raise PolicyValidationError(
                f"{label}: each priority entry must be a JSON object"
            )

        if "provider_id" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'provider_id'"
            )

        pr_id = entry["provider_id"]

        if provider_ids and pr_id not in provider_ids:
            raise PolicyValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if pr_id in seen_providers:
            raise PolicyValidationError(
                f"{label}: duplicate provider_id '{pr_id}' in priority list"
            )
        seen_providers.add(pr_id)

        if "priority" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'priority'"
            )

    # Validate dataset merge policies.
    for ds_id, entry in data["dataset_merge_policies"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise PolicyValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise PolicyValidationError(
                f"{label}: policy entry must be a JSON object"
            )

        if "conflict_resolution" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'conflict_resolution'"
            )

        if entry["conflict_resolution"] not in valid_resolutions:
            raise PolicyValidationError(
                f"{label}: conflict_resolution "
                f"'{entry['conflict_resolution']}' is not one of "
                f"{sorted(valid_resolutions)}"
            )

        if "overwrite_rule" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'overwrite_rule'"
            )

        if entry["overwrite_rule"] not in valid_overwrites:
            raise PolicyValidationError(
                f"{label}: overwrite_rule '{entry['overwrite_rule']}' "
                f"is not one of {sorted(valid_overwrites)}"
            )

        if "canonical_field_preference" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field "
                f"'canonical_field_preference'"
            )

        if "notes" not in entry:
            raise PolicyValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Policies Validated: %s (%d dataset policies, "
                "%d provider priorities)", source_name,
                len(data["dataset_merge_policies"]),
                len(data["provider_priority"]))
    return True


# ---------------------------------------------------------------------------
# Full policy registry lifecycle
# ---------------------------------------------------------------------------

def load_and_validate_policy_registry(
    policies_dir=None,
    dataset_ids=None,
    provider_ids=None,
):
    """Load, validate, and register all policy files.

    This is the main entry point. It performs the complete lifecycle:
        1. Load each policy JSON file.
        2. Validate structure and required fields.
        3. Verify cross-references to datasets and providers.
        4. Detect duplicates.
        5. Register policies.

    Args:
        policies_dir: Override for the policies directory (testing).
        dataset_ids: Set of valid dataset IDs. If None, resolved
            automatically from the Dataset Registry.
        provider_ids: Set of valid provider IDs. If None, resolved
            automatically from the Provider Registry.

    Returns:
        dict mapping filename -> parsed data for each policy file.

    Raises:
        PolicyValidationError on any validation failure.
    """
    # --- Resolve IDs from existing registries if not supplied ---
    if dataset_ids is None or provider_ids is None:
        import sys
        _dr_dir = os.path.dirname(os.path.abspath(__file__))
        if _dr_dir not in sys.path:
            sys.path.insert(0, _dr_dir)

        # Resolve provider IDs.
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

        # Resolve dataset IDs.
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

    logger.info("Policies Loaded")

    registry = {}
    base_dir = policies_dir if policies_dir is not None else POLICIES_DIR

    # --- refresh_policy.json ---
    rp = load_policy_file("refresh_policy.json", policies_dir=base_dir)
    validate_refresh_policy(rp, dataset_ids)
    registry["refresh_policy.json"] = rp
    logger.info("Policies Registered: refresh_policy.json")

    # --- validation_policy.json ---
    vp = load_policy_file("validation_policy.json", policies_dir=base_dir)
    validate_validation_policy(vp, dataset_ids)
    registry["validation_policy.json"] = vp
    logger.info("Policies Registered: validation_policy.json")

    # --- retention_policy.json ---
    ret = load_policy_file("retention_policy.json", policies_dir=base_dir)
    validate_retention_policy(ret, dataset_ids)
    registry["retention_policy.json"] = ret
    logger.info("Policies Registered: retention_policy.json")

    # --- merge_policy.json ---
    mp = load_policy_file("merge_policy.json", policies_dir=base_dir)
    validate_merge_policy(mp, dataset_ids, provider_ids)
    registry["merge_policy.json"] = mp
    logger.info("Policies Registered: merge_policy.json")

    logger.info(
        "Completion: loaded and registered %d policy file(s)", len(registry)
    )
    return registry


if __name__ == "__main__":
    load_and_validate_policy_registry()
