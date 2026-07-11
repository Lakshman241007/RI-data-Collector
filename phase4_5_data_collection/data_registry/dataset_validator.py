"""
Dataset Registry Validator
Stage 3B.1.2 — RI-data-Collector

Scope: This module ONLY loads, validates, and registers dataset descriptor
files found in data_registry/datasets/. It does not download data, contact
providers, or perform any network activity.

Responsibilities:
    - Load dataset JSON descriptor files from data_registry/datasets/.
    - Validate structure and required fields for each dataset descriptor.
    - Verify that provider_reference values point to existing Provider
      Registry entries (loaded via registry_validator).
    - Verify that schema_reference paths exist on disk (when non-empty).
    - Verify that dependency references point to other registered datasets.
    - Detect duplicate dataset IDs across the registry.
    - Log lifecycle events: Dataset Loaded, Dataset Validated,
      Dataset Registered, Completion.
"""

import json
import logging
import os

logger = logging.getLogger("dataset_registry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Resolve paths relative to this module's location (data_registry/).
_DATA_REGISTRY_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(_DATA_REGISTRY_DIR, "datasets")
PROJECT_ROOT = os.path.dirname(_DATA_REGISTRY_DIR)

# Dataset descriptor files to load (only the 7 files specified for Stage 3B.1.2).
DATASET_FILES = [
    "railway_zones.json",
    "railway_divisions.json",
    "station_codes.json",
    "station_master.json",
    "train_master.json",
    "station_categories.json",
    "station_status.json",
]

REQUIRED_FIELDS = [
    "dataset_id",
    "display_name",
    "description",
    "provider_reference",
    "schema_reference",
    "mapping_reference",
    "policy_reference",
    "license_reference",
    "verification_reference",
    "version_reference",
    "dependencies",
    "priority",
    "refresh_policy",
    "enabled",
    "notes",
]


class DatasetValidationError(Exception):
    """Raised when a dataset descriptor fails structural or reference validation."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_dataset_file(filename, datasets_dir=None):
    """Load a single dataset JSON descriptor file.

    Args:
        filename: Name of the JSON file inside the datasets directory.
        datasets_dir: Override for the datasets directory path (testing).

    Returns:
        Parsed dict from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        DatasetValidationError: If the file contains invalid JSON.
    """
    base_dir = datasets_dir if datasets_dir is not None else DATASETS_DIR
    path = os.path.join(base_dir, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Dataset file not found: {filename}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise DatasetValidationError(
                f"{filename}: invalid JSON structure ({e})"
            )

    logger.info("Dataset Loaded: %s", filename)
    return data


# ---------------------------------------------------------------------------
# Validation — structural
# ---------------------------------------------------------------------------

def validate_dataset(data, source_name="<unknown>"):
    """Validate the structure and required fields of a single dataset descriptor.

    Checks:
        - data is a dict
        - all REQUIRED_FIELDS are present
        - dataset_id is a non-empty string
        - dependencies is a list
        - enabled is a boolean

    Raises:
        DatasetValidationError with a descriptive message on failure.

    Returns:
        True if the descriptor is structurally valid.
    """
    if not isinstance(data, dict):
        raise DatasetValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise DatasetValidationError(
            f"{source_name}: missing required fields: {', '.join(missing)}"
        )

    if not isinstance(data.get("dataset_id"), str) or not data["dataset_id"].strip():
        raise DatasetValidationError(
            f"{source_name}: 'dataset_id' must be a non-empty string"
        )

    if not isinstance(data.get("dependencies"), list):
        raise DatasetValidationError(
            f"{source_name}: 'dependencies' must be a list, "
            f"got {type(data.get('dependencies')).__name__}"
        )

    if not isinstance(data.get("enabled"), bool):
        raise DatasetValidationError(
            f"{source_name}: 'enabled' must be a boolean, "
            f"got {type(data.get('enabled')).__name__}"
        )

    logger.info("Dataset Validated: %s (id=%s)", source_name, data["dataset_id"])
    return True


# ---------------------------------------------------------------------------
# Reference verification helpers
# ---------------------------------------------------------------------------

def verify_provider_references(registry, provider_ids, source_label="dataset"):
    """Verify that every dataset's provider_reference exists in the Provider Registry.

    Args:
        registry: dict mapping dataset_id -> dataset descriptor.
        provider_ids: set of valid provider IDs from the Provider Registry.
        source_label: label used in error messages.

    Raises:
        DatasetValidationError if any provider_reference is invalid.
    """
    for dataset_id, data in registry.items():
        ref = data.get("provider_reference", "")
        if ref and ref not in provider_ids:
            raise DatasetValidationError(
                f"{source_label} '{dataset_id}': provider_reference '{ref}' "
                f"does not match any registered provider"
            )
    logger.info("Provider References Verified")


def verify_schema_references(registry, project_root=None):
    """Verify that every non-empty schema_reference points to an existing file.

    Args:
        registry: dict mapping dataset_id -> dataset descriptor.
        project_root: override for the project root directory.

    Raises:
        DatasetValidationError if a schema file is referenced but missing.
    """
    root = project_root if project_root is not None else PROJECT_ROOT
    for dataset_id, data in registry.items():
        ref = data.get("schema_reference", "")
        if ref:
            schema_path = os.path.join(root, ref)
            if not os.path.exists(schema_path):
                raise DatasetValidationError(
                    f"Dataset '{dataset_id}': schema_reference '{ref}' "
                    f"file not found at {schema_path}"
                )
    logger.info("Schema References Verified")


def verify_dependencies(registry):
    """Verify that every dependency listed in each dataset exists in the registry.

    Args:
        registry: dict mapping dataset_id -> dataset descriptor.

    Raises:
        DatasetValidationError if a dependency references a non-existent dataset.
    """
    all_ids = set(registry.keys())
    for dataset_id, data in registry.items():
        for dep in data.get("dependencies", []):
            if dep not in all_ids:
                raise DatasetValidationError(
                    f"Dataset '{dataset_id}': dependency '{dep}' "
                    f"does not match any registered dataset"
                )
    logger.info("Dependencies Verified")


def verify_mapping_references(registry):
    """Verify mapping_reference values.

    Currently mapping files are empty placeholders, so non-empty references
    are accepted as forward declarations. This validator logs verification
    without raising, unless a reference is structurally invalid (non-string).

    Args:
        registry: dict mapping dataset_id -> dataset descriptor.

    Raises:
        DatasetValidationError if a mapping_reference is not a string.
    """
    for dataset_id, data in registry.items():
        ref = data.get("mapping_reference", "")
        if not isinstance(ref, str):
            raise DatasetValidationError(
                f"Dataset '{dataset_id}': mapping_reference must be a string, "
                f"got {type(ref).__name__}"
            )
    logger.info("Mapping References Verified")


def verify_policy_references(registry):
    """Verify policy_reference values.

    Currently policy files are empty placeholders, so non-empty references
    are accepted as forward declarations. This validator logs verification
    without raising, unless a reference is structurally invalid (non-string).

    Args:
        registry: dict mapping dataset_id -> dataset descriptor.

    Raises:
        DatasetValidationError if a policy_reference is not a string.
    """
    for dataset_id, data in registry.items():
        ref = data.get("policy_reference", "")
        if not isinstance(ref, str):
            raise DatasetValidationError(
                f"Dataset '{dataset_id}': policy_reference must be a string, "
                f"got {type(ref).__name__}"
            )
    logger.info("Policy References Verified")


def verify_license_references(registry):
    """Verify license_reference values.

    Currently license files are empty placeholders, so non-empty references
    are accepted as forward declarations. This validator logs verification
    without raising, unless a reference is structurally invalid (non-string).

    Args:
        registry: dict mapping dataset_id -> dataset descriptor.

    Raises:
        DatasetValidationError if a license_reference is not a string.
    """
    for dataset_id, data in registry.items():
        ref = data.get("license_reference", "")
        if not isinstance(ref, str):
            raise DatasetValidationError(
                f"Dataset '{dataset_id}': license_reference must be a string, "
                f"got {type(ref).__name__}"
            )
    logger.info("License References Verified")


# ---------------------------------------------------------------------------
# Full registry lifecycle
# ---------------------------------------------------------------------------

def load_and_validate_dataset_registry(
    datasets_dir=None,
    provider_ids=None,
    project_root=None,
):
    """Load, validate, and register every dataset descriptor.

    This is the main entry point. It performs the complete lifecycle:
        1. Load each dataset JSON file.
        2. Validate structure and required fields.
        3. Detect duplicate dataset IDs.
        4. Register each dataset.
        5. Verify provider references.
        6. Verify schema references.
        7. Verify mapping, policy, and license references.
        8. Verify dependency references.

    Args:
        datasets_dir: Override for the datasets directory (testing).
        provider_ids: Set of valid provider IDs. If None, the Provider
            Registry is loaded automatically via registry_validator.
        project_root: Override for the project root directory (testing).

    Returns:
        dict mapping dataset_id -> dataset descriptor.

    Raises:
        DatasetValidationError on any validation failure.
    """
    # --- Resolve provider IDs from the Provider Registry if not supplied ---
    if provider_ids is None:
        try:
            import registry_validator
            provider_registry = registry_validator.load_and_validate_registry()
            provider_ids = set(provider_registry.keys())
        except Exception:
            # If the provider registry cannot be loaded, treat as empty.
            # This allows the dataset validator to be tested independently.
            provider_ids = set()
            logger.warning(
                "Could not load Provider Registry — provider reference "
                "verification will be skipped"
            )

    logger.info("Dataset Registry Loaded")

    registry = {}

    for filename in DATASET_FILES:
        try:
            data = load_dataset_file(filename, datasets_dir=datasets_dir)
        except FileNotFoundError:
            logger.warning("Dataset file not found, skipping: %s", filename)
            continue

        validate_dataset(data, source_name=filename)

        dataset_id = data["dataset_id"]
        if dataset_id in registry:
            raise DatasetValidationError(
                f"Duplicate dataset_id detected: '{dataset_id}' "
                f"(already registered, conflict in {filename})"
            )

        registry[dataset_id] = data
        logger.info("Dataset Registered: %s", dataset_id)

    logger.info("Dataset Registry Validated")

    # --- Cross-reference verification ---
    if provider_ids:
        verify_provider_references(registry, provider_ids)

    root = project_root if project_root is not None else PROJECT_ROOT
    verify_schema_references(registry, project_root=root)
    verify_mapping_references(registry)
    verify_policy_references(registry)
    verify_license_references(registry)
    verify_dependencies(registry)

    logger.info(
        "Registry Passed: loaded and registered %d dataset(s)", len(registry)
    )
    return registry


if __name__ == "__main__":
    load_and_validate_dataset_registry()
