"""
Metadata Registry Validator
Stage 3B.1.6 — RI-data-Collector

Scope: This module ONLY loads, validates, and registers metadata
descriptor files found in data_registry/metadata/. It does not compute
quality scores, calculate confidence, analyse data, or make network
requests.

Responsibilities:
    - Load metadata JSON files from data_registry/metadata/.
    - Validate structure and required fields for each metadata file.
    - Verify that provider references point to existing Provider Registry IDs.
    - Verify that dataset references point to existing Dataset Registry IDs.
    - Validate metadata categories against allowed values.
    - Detect duplicate entries.
    - Log lifecycle events: Metadata Registry Loaded,
      Metadata Registry Validated, Metadata Registry Registered,
      Completion.
"""

import json
import logging
import os

logger = logging.getLogger("metadata_registry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Resolve paths relative to this module's location (data_registry/).
_DATA_REGISTRY_DIR = os.path.dirname(os.path.abspath(__file__))
METADATA_DIR = os.path.join(_DATA_REGISTRY_DIR, "metadata")

# Metadata files to load.
METADATA_FILES = [
    "source_quality.json",
    "confidence_scores.json",
    "update_frequency.json",
    "maintainers.json",
    "dataset_priority.json",
]


class MetadataValidationError(Exception):
    """Raised when a metadata file fails structural or reference validation."""


# ---------------------------------------------------------------------------
# Generic loading
# ---------------------------------------------------------------------------

def load_metadata_file(filename, metadata_dir=None):
    """Load a single metadata JSON file.

    Args:
        filename: Name of the JSON file inside the metadata directory.
        metadata_dir: Override for the metadata directory path (testing).

    Returns:
        Parsed data from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        MetadataValidationError: If the file contains invalid JSON.
    """
    base_dir = metadata_dir if metadata_dir is not None else METADATA_DIR
    path = os.path.join(base_dir, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Metadata file not found: {filename}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise MetadataValidationError(
                f"{filename}: invalid JSON structure ({e})"
            )

    logger.info("Metadata Registry Loaded: %s", filename)
    return data


# ---------------------------------------------------------------------------
# Source quality validation
# ---------------------------------------------------------------------------

def validate_source_quality(data, provider_ids,
                            source_name="source_quality.json"):
    """Validate the source quality metadata file.

    Checks:
        - data is a dict with 'providers' dict and 'valid_quality_tiers' list
        - each key in 'providers' references an existing provider_id
        - each entry has 'quality_tier' and 'notes'
        - quality_tier is one of the valid tiers

    Raises:
        MetadataValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MetadataValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "providers" not in data or not isinstance(data["providers"], dict):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'providers' dict"
        )

    if "valid_quality_tiers" not in data or \
            not isinstance(data["valid_quality_tiers"], list):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'valid_quality_tiers' list"
        )

    valid_tiers = set(data["valid_quality_tiers"])

    for pr_id, entry in data["providers"].items():
        label = f"{source_name}[{pr_id}]"

        if provider_ids and pr_id not in provider_ids:
            raise MetadataValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if not isinstance(entry, dict):
            raise MetadataValidationError(
                f"{label}: entry must be a JSON object"
            )

        if "quality_tier" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'quality_tier'"
            )

        if entry["quality_tier"] not in valid_tiers:
            raise MetadataValidationError(
                f"{label}: quality_tier '{entry['quality_tier']}' is not "
                f"one of {sorted(valid_tiers)}"
            )

        if "notes" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Metadata Registry Validated: %s (%d providers)",
                source_name, len(data["providers"]))
    return True


# ---------------------------------------------------------------------------
# Confidence scores validation
# ---------------------------------------------------------------------------

def validate_confidence_scores(data, dataset_ids, provider_ids,
                               source_name="confidence_scores.json"):
    """Validate the confidence scores metadata file.

    Checks:
        - data is a dict with 'datasets' dict and
          'valid_confidence_levels' list
        - each key in 'datasets' references an existing dataset_id
        - each entry has 'confidence_level', 'primary_provider', and 'notes'
        - confidence_level is one of the valid levels
        - primary_provider references an existing provider (if non-empty)

    Raises:
        MetadataValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MetadataValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "datasets" not in data or not isinstance(data["datasets"], dict):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'datasets' dict"
        )

    if "valid_confidence_levels" not in data or \
            not isinstance(data["valid_confidence_levels"], list):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'valid_confidence_levels' list"
        )

    valid_levels = set(data["valid_confidence_levels"])

    for ds_id, entry in data["datasets"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise MetadataValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise MetadataValidationError(
                f"{label}: entry must be a JSON object"
            )

        if "confidence_level" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'confidence_level'"
            )

        if entry["confidence_level"] not in valid_levels:
            raise MetadataValidationError(
                f"{label}: confidence_level '{entry['confidence_level']}' "
                f"is not one of {sorted(valid_levels)}"
            )

        if "primary_provider" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'primary_provider'"
            )

        pp = entry["primary_provider"]
        if pp and provider_ids and pp not in provider_ids:
            raise MetadataValidationError(
                f"{label}: primary_provider '{pp}' does not match any "
                f"registered provider"
            )

        if "notes" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Metadata Registry Validated: %s (%d datasets)",
                source_name, len(data["datasets"]))
    return True


# ---------------------------------------------------------------------------
# Update frequency validation
# ---------------------------------------------------------------------------

def validate_update_frequency(data, dataset_ids,
                              source_name="update_frequency.json"):
    """Validate the update frequency metadata file.

    Checks:
        - data is a dict with 'datasets' dict and
          'valid_frequencies' list
        - each key in 'datasets' references an existing dataset_id
        - each entry has 'expected_frequency' and 'notes'
        - expected_frequency is one of the valid frequencies

    Raises:
        MetadataValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MetadataValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "datasets" not in data or not isinstance(data["datasets"], dict):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'datasets' dict"
        )

    if "valid_frequencies" not in data or \
            not isinstance(data["valid_frequencies"], list):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'valid_frequencies' list"
        )

    valid_freqs = set(data["valid_frequencies"])

    for ds_id, entry in data["datasets"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise MetadataValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise MetadataValidationError(
                f"{label}: entry must be a JSON object"
            )

        if "expected_frequency" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'expected_frequency'"
            )

        if entry["expected_frequency"] not in valid_freqs:
            raise MetadataValidationError(
                f"{label}: expected_frequency "
                f"'{entry['expected_frequency']}' is not one of "
                f"{sorted(valid_freqs)}"
            )

        if "notes" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Metadata Registry Validated: %s (%d datasets)",
                source_name, len(data["datasets"]))
    return True


# ---------------------------------------------------------------------------
# Maintainers validation
# ---------------------------------------------------------------------------

def validate_maintainers(data, provider_ids,
                         source_name="maintainers.json"):
    """Validate the maintainers metadata file.

    Checks:
        - data is a dict with 'providers' dict
        - each key references an existing provider_id
        - each entry has 'organization' and 'notes'

    Raises:
        MetadataValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MetadataValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "providers" not in data or not isinstance(data["providers"], dict):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'providers' dict"
        )

    for pr_id, entry in data["providers"].items():
        label = f"{source_name}[{pr_id}]"

        if provider_ids and pr_id not in provider_ids:
            raise MetadataValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if not isinstance(entry, dict):
            raise MetadataValidationError(
                f"{label}: entry must be a JSON object"
            )

        if "organization" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'organization'"
            )

        if "notes" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'notes'"
            )

    logger.info("Metadata Registry Validated: %s (%d providers)",
                source_name, len(data["providers"]))
    return True


# ---------------------------------------------------------------------------
# Dataset priority validation
# ---------------------------------------------------------------------------

def validate_dataset_priority(data, dataset_ids,
                              source_name="dataset_priority.json"):
    """Validate the dataset priority metadata file.

    Checks:
        - data is a dict with 'datasets' dict and
          'valid_priority_categories' list
        - each key in 'datasets' references an existing dataset_id
        - each entry has 'priority_category' and 'rationale'
        - priority_category is one of the valid categories

    Raises:
        MetadataValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MetadataValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "datasets" not in data or not isinstance(data["datasets"], dict):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid 'datasets' dict"
        )

    if "valid_priority_categories" not in data or \
            not isinstance(data["valid_priority_categories"], list):
        raise MetadataValidationError(
            f"{source_name}: missing or invalid "
            f"'valid_priority_categories' list"
        )

    valid_categories = set(data["valid_priority_categories"])

    for ds_id, entry in data["datasets"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise MetadataValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(entry, dict):
            raise MetadataValidationError(
                f"{label}: entry must be a JSON object"
            )

        if "priority_category" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'priority_category'"
            )

        if entry["priority_category"] not in valid_categories:
            raise MetadataValidationError(
                f"{label}: priority_category "
                f"'{entry['priority_category']}' is not one of "
                f"{sorted(valid_categories)}"
            )

        if "rationale" not in entry:
            raise MetadataValidationError(
                f"{label}: missing required field 'rationale'"
            )

    logger.info("Metadata Registry Validated: %s (%d datasets)",
                source_name, len(data["datasets"]))
    return True


# ---------------------------------------------------------------------------
# Full metadata registry lifecycle
# ---------------------------------------------------------------------------

def load_and_validate_metadata_registry(
    metadata_dir=None,
    provider_ids=None,
    dataset_ids=None,
):
    """Load, validate, and register all metadata files.

    This is the main entry point. It performs the complete lifecycle:
        1. Load each metadata JSON file.
        2. Validate structure and required fields.
        3. Verify cross-references to providers and datasets.
        4. Validate metadata categories.
        5. Register metadata.

    Args:
        metadata_dir: Override for the metadata directory (testing).
        provider_ids: Set of valid provider IDs. If None, resolved
            automatically.
        dataset_ids: Set of valid dataset IDs. If None, resolved
            automatically.

    Returns:
        dict mapping filename -> parsed data for each metadata file.

    Raises:
        MetadataValidationError on any validation failure.
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

    logger.info("Metadata Registry Loaded")

    registry = {}
    base_dir = metadata_dir if metadata_dir is not None else METADATA_DIR

    # --- source_quality.json ---
    sq = load_metadata_file("source_quality.json", metadata_dir=base_dir)
    validate_source_quality(sq, provider_ids)
    registry["source_quality.json"] = sq
    logger.info("Metadata Registry Registered: source_quality.json")

    # --- confidence_scores.json ---
    cs = load_metadata_file("confidence_scores.json", metadata_dir=base_dir)
    validate_confidence_scores(cs, dataset_ids, provider_ids)
    registry["confidence_scores.json"] = cs
    logger.info("Metadata Registry Registered: confidence_scores.json")

    # --- update_frequency.json ---
    uf = load_metadata_file("update_frequency.json", metadata_dir=base_dir)
    validate_update_frequency(uf, dataset_ids)
    registry["update_frequency.json"] = uf
    logger.info("Metadata Registry Registered: update_frequency.json")

    # --- maintainers.json ---
    mt = load_metadata_file("maintainers.json", metadata_dir=base_dir)
    validate_maintainers(mt, provider_ids)
    registry["maintainers.json"] = mt
    logger.info("Metadata Registry Registered: maintainers.json")

    # --- dataset_priority.json ---
    dp = load_metadata_file("dataset_priority.json", metadata_dir=base_dir)
    validate_dataset_priority(dp, dataset_ids)
    registry["dataset_priority.json"] = dp
    logger.info("Metadata Registry Registered: dataset_priority.json")

    logger.info(
        "Completion: loaded and registered %d metadata file(s)",
        len(registry)
    )
    return registry


if __name__ == "__main__":
    load_and_validate_metadata_registry()
