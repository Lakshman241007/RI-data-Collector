"""
Mapping Registry Validator
Stage 3B.1.3 — RI-data-Collector

Scope: This module ONLY loads, validates, and registers mapping descriptor
files found in data_registry/mappings/. It does not download data, contact
providers, or perform any network activity.

Responsibilities:
    - Load mapping JSON files from data_registry/mappings/.
    - Validate structure and required fields for each mapping file.
    - Verify that provider_dataset_mapping entries reference existing
      Provider Registry and Dataset Registry IDs.
    - Verify that field_mapping entries reference existing dataset IDs
      and provider IDs.
    - Verify that tag_mapping entries reference existing dataset IDs
      (when non-null).
    - Verify that dataset_dependencies entries reference existing
      dataset IDs.
    - Detect duplicate mappings.
    - Log lifecycle events: Mappings Loaded, Mappings Validated,
      Mappings Registered, Completion.
"""

import json
import logging
import os

logger = logging.getLogger("mapping_registry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Resolve paths relative to this module's location (data_registry/).
_DATA_REGISTRY_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_DIR = os.path.join(_DATA_REGISTRY_DIR, "mappings")

# Mapping files to load.
MAPPING_FILES = [
    "provider_dataset_mapping.json",
    "field_mapping.json",
    "tag_mapping.json",
    "dataset_dependencies.json",
]


class MappingValidationError(Exception):
    """Raised when a mapping file fails structural or reference validation."""


# ---------------------------------------------------------------------------
# Generic loading
# ---------------------------------------------------------------------------

def load_mapping_file(filename, mappings_dir=None):
    """Load a single mapping JSON file.

    Args:
        filename: Name of the JSON file inside the mappings directory.
        mappings_dir: Override for the mappings directory path (testing).

    Returns:
        Parsed data from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        MappingValidationError: If the file contains invalid JSON.
    """
    base_dir = mappings_dir if mappings_dir is not None else MAPPINGS_DIR
    path = os.path.join(base_dir, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Mapping file not found: {filename}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise MappingValidationError(
                f"{filename}: invalid JSON structure ({e})"
            )

    logger.info("Mappings Loaded: %s", filename)
    return data


# ---------------------------------------------------------------------------
# Provider-dataset mapping validation
# ---------------------------------------------------------------------------

def validate_provider_dataset_mapping(data, provider_ids, dataset_ids,
                                       source_name="provider_dataset_mapping.json"):
    """Validate the provider-dataset mapping file.

    Checks:
        - data is a dict with a 'mappings' list
        - each entry has dataset_id, provider_id, role
        - dataset_id references an existing dataset
        - provider_id references an existing provider
        - no duplicate (dataset_id, provider_id) pairs
        - role is one of the recognized values

    Raises:
        MappingValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MappingValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "mappings" not in data or not isinstance(data["mappings"], list):
        raise MappingValidationError(
            f"{source_name}: missing or invalid 'mappings' list"
        )

    valid_roles = {"primary", "supplementary", "verification"}
    seen_pairs = set()

    for i, entry in enumerate(data["mappings"]):
        label = f"{source_name}[{i}]"

        if not isinstance(entry, dict):
            raise MappingValidationError(
                f"{label}: each mapping entry must be a JSON object"
            )

        for field in ("dataset_id", "provider_id", "role"):
            if field not in entry:
                raise MappingValidationError(
                    f"{label}: missing required field '{field}'"
                )

        ds_id = entry["dataset_id"]
        pr_id = entry["provider_id"]
        role = entry["role"]

        if dataset_ids and ds_id not in dataset_ids:
            raise MappingValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if provider_ids and pr_id not in provider_ids:
            raise MappingValidationError(
                f"{label}: provider_id '{pr_id}' does not match any "
                f"registered provider"
            )

        if role not in valid_roles:
            raise MappingValidationError(
                f"{label}: role must be one of {sorted(valid_roles)}, "
                f"got '{role}'"
            )

        pair = (ds_id, pr_id)
        if pair in seen_pairs:
            raise MappingValidationError(
                f"{label}: duplicate mapping for dataset '{ds_id}' "
                f"and provider '{pr_id}'"
            )
        seen_pairs.add(pair)

    logger.info("Mappings Validated: %s (%d entries)", source_name,
                len(data["mappings"]))
    return True


# ---------------------------------------------------------------------------
# Field mapping validation
# ---------------------------------------------------------------------------

def validate_field_mapping(data, dataset_ids, provider_ids,
                           source_name="field_mapping.json"):
    """Validate the field mapping file.

    Checks:
        - data is a dict with a 'mappings' dict
        - each key in 'mappings' is a recognized dataset_id
        - each dataset entry has 'canonical_fields' (list) and
          'provider_field_maps' (dict)
        - each provider key in 'provider_field_maps' is a recognized
          provider_id
        - no duplicate canonical fields within a dataset

    Raises:
        MappingValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MappingValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "mappings" not in data or not isinstance(data["mappings"], dict):
        raise MappingValidationError(
            f"{source_name}: missing or invalid 'mappings' dict"
        )

    for ds_id, ds_data in data["mappings"].items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise MappingValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(ds_data, dict):
            raise MappingValidationError(
                f"{label}: dataset mapping must be a JSON object"
            )

        if "canonical_fields" not in ds_data:
            raise MappingValidationError(
                f"{label}: missing 'canonical_fields'"
            )

        if not isinstance(ds_data["canonical_fields"], list):
            raise MappingValidationError(
                f"{label}: 'canonical_fields' must be a list"
            )

        # Check for duplicate canonical fields.
        fields = ds_data["canonical_fields"]
        if len(fields) != len(set(fields)):
            raise MappingValidationError(
                f"{label}: duplicate canonical fields detected"
            )

        if "provider_field_maps" not in ds_data:
            raise MappingValidationError(
                f"{label}: missing 'provider_field_maps'"
            )

        if not isinstance(ds_data["provider_field_maps"], dict):
            raise MappingValidationError(
                f"{label}: 'provider_field_maps' must be a dict"
            )

        for pr_id in ds_data["provider_field_maps"]:
            if provider_ids and pr_id not in provider_ids:
                raise MappingValidationError(
                    f"{label}: provider_id '{pr_id}' in provider_field_maps "
                    f"does not match any registered provider"
                )

    logger.info("Mappings Validated: %s (%d datasets)", source_name,
                len(data["mappings"]))
    return True


# ---------------------------------------------------------------------------
# Tag mapping validation
# ---------------------------------------------------------------------------

def validate_tag_mapping(data, dataset_ids,
                         source_name="tag_mapping.json"):
    """Validate the tag mapping file.

    Checks:
        - data is a dict with a 'tag_sources' dict
        - each source has a 'tag_key' and 'mappings' list
        - each mapping entry has 'tag_value' and 'dataset_id'
        - non-null dataset_id references exist in the dataset registry
        - no duplicate tag_value within a source

    Raises:
        MappingValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MappingValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "tag_sources" not in data or not isinstance(data["tag_sources"], dict):
        raise MappingValidationError(
            f"{source_name}: missing or invalid 'tag_sources' dict"
        )

    for source_id, source_data in data["tag_sources"].items():
        label = f"{source_name}[{source_id}]"

        if not isinstance(source_data, dict):
            raise MappingValidationError(
                f"{label}: tag source must be a JSON object"
            )

        if "tag_key" not in source_data:
            raise MappingValidationError(
                f"{label}: missing 'tag_key'"
            )

        if "mappings" not in source_data or \
                not isinstance(source_data["mappings"], list):
            raise MappingValidationError(
                f"{label}: missing or invalid 'mappings' list"
            )

        seen_tags = set()
        for i, entry in enumerate(source_data["mappings"]):
            entry_label = f"{label}.mappings[{i}]"

            if not isinstance(entry, dict):
                raise MappingValidationError(
                    f"{entry_label}: each mapping entry must be a JSON object"
                )

            if "tag_value" not in entry:
                raise MappingValidationError(
                    f"{entry_label}: missing 'tag_value'"
                )

            if "dataset_id" not in entry:
                raise MappingValidationError(
                    f"{entry_label}: missing 'dataset_id'"
                )

            tag_val = entry["tag_value"]
            ds_id = entry["dataset_id"]

            if tag_val in seen_tags:
                raise MappingValidationError(
                    f"{entry_label}: duplicate tag_value '{tag_val}' "
                    f"within source '{source_id}'"
                )
            seen_tags.add(tag_val)

            # null dataset_id is allowed (unmapped tag).
            if ds_id is not None and dataset_ids and ds_id not in dataset_ids:
                raise MappingValidationError(
                    f"{entry_label}: dataset_id '{ds_id}' does not match "
                    f"any registered dataset"
                )

    logger.info("Mappings Validated: %s (%d sources)", source_name,
                len(data["tag_sources"]))
    return True


# ---------------------------------------------------------------------------
# Dataset dependencies validation
# ---------------------------------------------------------------------------

def validate_dataset_dependencies(data, dataset_ids,
                                   source_name="dataset_dependencies.json"):
    """Validate the dataset dependencies file.

    Checks:
        - data is a dict with a 'dependency_graph' dict
        - each key in 'dependency_graph' is a recognized dataset_id
        - each entry has 'depends_on' (list) and 'build_order' (int)
        - all depends_on entries reference existing datasets
        - no self-dependencies

    Raises:
        MappingValidationError on any validation failure.

    Returns:
        True if valid.
    """
    if not isinstance(data, dict):
        raise MappingValidationError(
            f"{source_name}: invalid structure — expected a JSON object, "
            f"got {type(data).__name__}"
        )

    if "dependency_graph" not in data or \
            not isinstance(data["dependency_graph"], dict):
        raise MappingValidationError(
            f"{source_name}: missing or invalid 'dependency_graph' dict"
        )

    graph = data["dependency_graph"]
    all_graph_ids = set(graph.keys())

    for ds_id, ds_data in graph.items():
        label = f"{source_name}[{ds_id}]"

        if dataset_ids and ds_id not in dataset_ids:
            raise MappingValidationError(
                f"{label}: dataset_id '{ds_id}' does not match any "
                f"registered dataset"
            )

        if not isinstance(ds_data, dict):
            raise MappingValidationError(
                f"{label}: entry must be a JSON object"
            )

        if "depends_on" not in ds_data:
            raise MappingValidationError(
                f"{label}: missing 'depends_on'"
            )

        if not isinstance(ds_data["depends_on"], list):
            raise MappingValidationError(
                f"{label}: 'depends_on' must be a list"
            )

        if "build_order" not in ds_data:
            raise MappingValidationError(
                f"{label}: missing 'build_order'"
            )

        if not isinstance(ds_data["build_order"], int):
            raise MappingValidationError(
                f"{label}: 'build_order' must be an integer"
            )

        for dep in ds_data["depends_on"]:
            if dep == ds_id:
                raise MappingValidationError(
                    f"{label}: self-dependency detected"
                )
            if dep not in all_graph_ids:
                raise MappingValidationError(
                    f"{label}: dependency '{dep}' does not match any "
                    f"dataset in the dependency graph"
                )

    logger.info("Mappings Validated: %s (%d datasets)", source_name,
                len(graph))
    return True


# ---------------------------------------------------------------------------
# Full mapping registry lifecycle
# ---------------------------------------------------------------------------

def load_and_validate_mapping_registry(
    mappings_dir=None,
    provider_ids=None,
    dataset_ids=None,
):
    """Load, validate, and register all mapping files.

    This is the main entry point. It performs the complete lifecycle:
        1. Load each mapping JSON file.
        2. Validate structure and required fields.
        3. Verify cross-references to providers and datasets.
        4. Detect duplicates.
        5. Register mappings.

    Args:
        mappings_dir: Override for the mappings directory (testing).
        provider_ids: Set of valid provider IDs. If None, resolved
            automatically from the Dataset Registry.
        dataset_ids: Set of valid dataset IDs. If None, resolved
            automatically from the Dataset Registry.

    Returns:
        dict mapping filename -> parsed data for each mapping file.

    Raises:
        MappingValidationError on any validation failure.
    """
    # --- Resolve IDs from existing registries if not supplied ---
    if provider_ids is None or dataset_ids is None:
        import sys
        _dr_dir = os.path.dirname(os.path.abspath(__file__))
        if _dr_dir not in sys.path:
            sys.path.insert(0, _dr_dir)

        # Resolve provider IDs from the Provider Registry.
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

        # Resolve dataset IDs from the Dataset Registry.
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

    logger.info("Mappings Loaded")

    registry = {}
    base_dir = mappings_dir if mappings_dir is not None else MAPPINGS_DIR

    # --- provider_dataset_mapping.json ---
    pdm = load_mapping_file("provider_dataset_mapping.json",
                            mappings_dir=base_dir)
    validate_provider_dataset_mapping(pdm, provider_ids, dataset_ids)
    registry["provider_dataset_mapping.json"] = pdm
    logger.info("Mappings Registered: provider_dataset_mapping.json")

    # --- field_mapping.json ---
    fm = load_mapping_file("field_mapping.json", mappings_dir=base_dir)
    validate_field_mapping(fm, dataset_ids, provider_ids)
    registry["field_mapping.json"] = fm
    logger.info("Mappings Registered: field_mapping.json")

    # --- tag_mapping.json ---
    tm = load_mapping_file("tag_mapping.json", mappings_dir=base_dir)
    validate_tag_mapping(tm, dataset_ids)
    registry["tag_mapping.json"] = tm
    logger.info("Mappings Registered: tag_mapping.json")

    # --- dataset_dependencies.json ---
    dd = load_mapping_file("dataset_dependencies.json",
                           mappings_dir=base_dir)
    validate_dataset_dependencies(dd, dataset_ids)
    registry["dataset_dependencies.json"] = dd
    logger.info("Mappings Registered: dataset_dependencies.json")

    logger.info(
        "Completion: loaded and registered %d mapping file(s)", len(registry)
    )
    return registry


if __name__ == "__main__":
    load_and_validate_mapping_registry()
