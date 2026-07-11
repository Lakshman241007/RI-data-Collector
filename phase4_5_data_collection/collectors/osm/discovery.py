"""
collectors/osm/discovery.py
Railway Tag Discovery Engine — Phase 4.5.1 Stage 2 final enhancement.

Turns the OSM Railway Infrastructure Collector into a self-discovering,
self-auditing collector:

- Scans the configured region for every unique ``railway=*`` tag value
  actually present in OpenStreetMap (no hardcoded railway values).
- Cross-references discovered values against ``reference/railway_tags.json``
  to compute coverage, unsupported ("future") tags, and a capability matrix.
- Never raises on unknown/future tags — they are simply discovered, counted,
  classified as unsupported, and reported. Execution always continues.

This module is purely additive: it does not alter any existing Stage 2
dataset module, schema, cache entry, or report. It only adds new reports
(``reports/osm_discovery_report.json``, ``coverage/osm_tag_coverage.json``,
``reports/collector_capabilities.json``) and new sub-sections inside the
existing ``statistics/osm_statistics.json`` / ``quality/osm_quality.json``
files.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from collectors.osm import _base  # module reference so test patches of
                                   # collectors.osm._base.run_overpass_query
                                   # transparently cover discovery as well.
from collectors.osm.downloader import OVERPASS_ENDPOINT, DEFAULT_TIMEOUT
from collectors.osm.utils import load_query_config, load_from_cache, save_to_cache
from common.file_utils import timestamp_utc, ensure_dir
from common.json_utils import save_json, safe_load_json
from common.logger import get_logger

_log = get_logger("osm.discovery", "osm.log")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_PATH = _PROJECT_ROOT / "reference" / "railway_tags.json"

DISCOVERY_DATASET_KEY = "discovery"
DEFAULT_ELEMENT_TYPES: list[str] = ["node", "way", "relation"]

#: Capability groups derived from railway=* values. Purely descriptive —
#: used only to *organise* whatever is discovered/known, never to restrict
#: what can be discovered.
_CAPABILITY_GROUPS: dict[str, set[str]] = {
    "stations": {"station", "halt", "stop", "junction", "terminal"},
    "tracks": {
        "rail", "light_rail", "narrow_gauge", "monorail", "miniature",
        "preserved", "construction", "disused", "abandoned", "razed",
        "proposed",
    },
    "platforms": {"platform"},
    "signals": {"signal", "semaphore"},
    "crossings": {"level_crossing", "crossing"},
    "facilities": {
        "depot", "engine_shed", "maintenance", "workshop", "roundhouse",
        "refuelling", "wash", "loading_gauge", "switch",
    },
    "yards": {"yard"},
    "sidings": {"siding"},
    "turntables": {"turntable"},
    "buffer_stops": {"buffer_stop"},
    "signal_boxes": {"signal_box"},
}

#: These capabilities are determined by the *presence of a dedicated
#: collector module*, not by a railway=* value (they key off bridge=*,
#: tunnel=* and electrified=* instead).
_NON_RAILWAY_KEY_CAPABILITIES: set[str] = {"bridges", "tunnels", "electrification"}

#: Capabilities implicitly covered by the "facilities" collector module.
_FACILITIES_SUBCAPABILITIES: set[str] = {
    "yards", "sidings", "turntables", "buffer_stops", "signal_boxes",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredTag:
    """A single railway=* value observed in the region, with its counts."""

    value: str
    count: int = 0
    element_types: dict[str, int] = field(default_factory=dict)

    def record(self, element_type: str) -> None:
        self.count += 1
        self.element_types[element_type] = self.element_types.get(element_type, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "count": self.count,
            "element_types": dict(self.element_types),
        }


@dataclass
class DiscoveryResult:
    """Outcome of one discovery scan."""

    discovered_tags: dict[str, DiscoveredTag] = field(default_factory=dict)
    total_elements: int = 0
    by_element_type: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    region: str = "unknown"
    generated_at: str = field(default_factory=timestamp_utc)


# ---------------------------------------------------------------------------
# Reference tag loading
# ---------------------------------------------------------------------------

def load_reference_tags(reference_path: Path = _REFERENCE_PATH) -> dict[str, str]:
    """
    Flatten ``reference/railway_tags.json`` into ``{value: category}`` for
    every ``railway=<value>`` key found across all categories.

    Returns an empty dict (never raises) if the reference file is missing
    or malformed — discovery must continue regardless.
    """
    ref = safe_load_json(reference_path, default={}) or {}
    known: dict[str, str] = {}
    for category, block in ref.items():
        if category.startswith("_") or not isinstance(block, dict):
            continue
        tags = block.get("tags", {})
        if not isinstance(tags, dict):
            continue
        for key in tags:
            if key.startswith("railway="):
                value = key.split("=", 1)[1]
                if value and value != "*":
                    known[value] = category
    return known


# ---------------------------------------------------------------------------
# Query construction (config-driven; no hardcoded railway values)
# ---------------------------------------------------------------------------

def build_discovery_query(
    *,
    element_types: list[str],
    area_id: int | None,
    bbox: str,
    timeout: int,
) -> str:
    """
    Build an Overpass QL query that returns every element carrying a
    ``railway`` key (any value) in the configured region, with tags only
    (no geometry needed for tag discovery).
    """
    if area_id:
        area_header = f"area({area_id + 3_600_000_000})->.searchArea;\n"
        spatial = "(area.searchArea)"
    else:
        area_header = ""
        spatial = f"({bbox})"

    clauses = [f'  {etype}["railway"]{spatial};' for etype in element_types]
    union_body = "\n".join(clauses)
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"{area_header}"
        f"(\n{union_body}\n);\n"
        f"out tags;"
    )


def _resolve_element_types() -> list[str]:
    """Element types come from config/osm_queries.json when present."""
    try:
        cfg = load_query_config(DISCOVERY_DATASET_KEY)
        types = cfg.get("element_types")
        if types:
            return list(types)
    except KeyError:
        _log.debug(
            "No 'discovery' entry in config/osm_queries.json – "
            "falling back to default element types."
        )
    return list(DEFAULT_ELEMENT_TYPES)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_discovered_tags(elements: list[dict[str, Any]]) -> dict[str, DiscoveredTag]:
    """
    Tally every ``railway=*`` value present in *elements* into
    :class:`DiscoveredTag` instances, keyed by value.
    """
    discovered: dict[str, DiscoveredTag] = {}
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") or {}
        value = tags.get("railway")
        if not value:
            continue
        etype = element.get("type", "unknown")
        tag = discovered.setdefault(value, DiscoveredTag(value=value))
        tag.record(etype)
    return discovered


# ---------------------------------------------------------------------------
# Discovery execution
# ---------------------------------------------------------------------------

def run_discovery(
    raw_dir: Path,
    *,
    area_id: int | None = None,
    bbox: str = "8.0,68.0,37.0,97.5",
    timeout: int = DEFAULT_TIMEOUT,
    overwrite: bool = False,
    endpoint: str = OVERPASS_ENDPOINT,
    retries: int = 3,
    region: str = "unknown",
) -> DiscoveryResult:
    """
    Scan the configured region for every railway=* tag in use and return a
    :class:`DiscoveryResult`.

    This function never raises: if the Overpass query fails after all
    retries, discovery completes with zero elements rather than aborting
    the pipeline, satisfying the "never fail on unknown/future tags or
    transient errors" requirement.
    """
    _log.info("Discovery started – region='%s'", region)
    t0 = time.monotonic()

    element_types = _resolve_element_types()

    ds_dir = raw_dir / DISCOVERY_DATASET_KEY
    ensure_dir(ds_dir)
    dest = ds_dir / f"{DISCOVERY_DATASET_KEY}.json"

    elements: list[dict[str, Any]] = []

    if not overwrite:
        cached = load_from_cache(DISCOVERY_DATASET_KEY)
        if cached is not None:
            elements, _checksum = cached
            _log.info("Discovery loaded from cache (%d elements)", len(elements))

    if not elements:
        query = build_discovery_query(
            element_types=element_types, area_id=area_id, bbox=bbox, timeout=timeout,
        )
        _log.debug("Discovery query:\n%s", query)
        try:
            data = _base.run_overpass_query(
                query, endpoint=endpoint, timeout=timeout + 30, retries=retries,
            )
            elements = data.get("elements", [])
        except Exception as exc:  # noqa: BLE001 - discovery must never abort the pipeline
            _log.error("Discovery query failed: %s – continuing with zero elements.", exc)
            elements = []

        payload = {
            "meta": {
                "dataset": DISCOVERY_DATASET_KEY,
                "collected_at": timestamp_utc(),
                "record_count": len(elements),
                "area_id": area_id,
                "bbox": bbox,
                "element_types": element_types,
            },
            "elements": elements,
        }
        save_json(payload, dest)
        if elements:
            save_to_cache(DISCOVERY_DATASET_KEY, payload)

    discovered_tags = parse_discovered_tags(elements)

    by_element_type: dict[str, int] = {}
    for el in elements:
        if not isinstance(el, dict):
            continue
        t = el.get("type", "unknown")
        by_element_type[t] = by_element_type.get(t, 0) + 1

    elapsed = round(time.monotonic() - t0, 3)

    _log.info(
        "Discovery completed – elements_scanned=%d tags_discovered=%d runtime=%.2fs",
        len(elements), len(discovered_tags), elapsed,
    )

    return DiscoveryResult(
        discovered_tags=discovered_tags,
        total_elements=len(elements),
        by_element_type=by_element_type,
        elapsed_seconds=elapsed,
        region=region,
    )


# ---------------------------------------------------------------------------
# Coverage audit
# ---------------------------------------------------------------------------

def compute_coverage(result: DiscoveryResult, known_tags: dict[str, str]) -> dict[str, Any]:
    """
    Dynamically compute supported/unsupported/unused-configured tags and a
    coverage percentage. Nothing here is a hardcoded expected count —
    everything is derived from *result* and *known_tags*.
    """
    discovered_values = set(result.discovered_tags.keys())
    known_values = set(known_tags.keys())

    supported = sorted(discovered_values & known_values)
    unsupported = sorted(discovered_values - known_values)
    unused_configured = sorted(known_values - discovered_values)

    total_discovered = len(discovered_values)
    coverage_pct = round(
        (len(supported) / total_discovered * 100.0) if total_discovered else 100.0, 2,
    )

    total_occurrences = sum(t.count for t in result.discovered_tags.values())
    unsupported_occurrences = sum(result.discovered_tags[v].count for v in unsupported)

    recommendations: list[str] = []
    if unsupported:
        recommendations.append(
            f"Add reference/collector support for {len(unsupported)} newly "
            f"discovered railway tag(s): {', '.join(unsupported)}."
        )
    if unused_configured:
        recommendations.append(
            f"{len(unused_configured)} reference tag(s) were not observed in "
            f"this region and may be region-specific or obsolete: "
            f"{', '.join(unused_configured)}."
        )
    if not unsupported and not unused_configured:
        recommendations.append(
            "Reference tag dictionary fully matches discovered tags. No action needed."
        )

    return {
        "total_discovered_tags": total_discovered,
        "supported_tags": supported,
        "supported_count": len(supported),
        "unsupported_tags": unsupported,
        "unsupported_count": len(unsupported),
        "unused_configured_tags": unused_configured,
        "unused_configured_count": len(unused_configured),
        "coverage_percentage": coverage_pct,
        "total_tag_occurrences": total_occurrences,
        "unsupported_tag_occurrences": unsupported_occurrences,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------

def build_capability_matrix(
    result: DiscoveryResult,
    known_tags: dict[str, str],
    implemented_categories: set[str],
) -> dict[str, Any]:
    """
    Automatically determine which railway object categories are supported,
    based on what the collector currently implements (*implemented_categories*,
    i.e. the OSM collector's dataset-module map) cross-referenced with what
    has actually been discovered in the region.
    """
    discovered_values = set(result.discovered_tags.keys())
    known_values = set(known_tags.keys())
    matrix: dict[str, Any] = {}

    for capability, values in _CAPABILITY_GROUPS.items():
        implemented = capability in implemented_categories or (
            capability in _FACILITIES_SUBCAPABILITIES and "facilities" in implemented_categories
        )
        observed = sorted(values & discovered_values)
        matrix[capability] = {
            "implemented": implemented,
            "known_tag_values": sorted(values),
            "supported_tag_values": sorted(values & known_values),
            "observed_in_region": observed,
            "observed_count": sum(result.discovered_tags[v].count for v in observed),
        }

    for capability in _NON_RAILWAY_KEY_CAPABILITIES:
        matrix[capability] = {
            "implemented": capability in implemented_categories,
            "note": (
                "Determined by presence of a dedicated collector module — "
                "this category is keyed by bridge=*/tunnel=*/electrified=*, "
                "not by a railway=* value, so it is outside tag discovery scope."
            ),
        }

    future_tags = sorted(discovered_values - known_values)
    matrix["future_tags"] = {
        "implemented": False,
        "discovered_unsupported_values": future_tags,
        "count": len(future_tags),
        "occurrences": sum(result.discovered_tags[v].count for v in future_tags),
        "note": (
            "Railway tags observed in OSM that are not yet present in "
            "reference/railway_tags.json. Detected and reported automatically; "
            "no code change is required for this detection to keep working."
        ),
    }
    return matrix


# ---------------------------------------------------------------------------
# Statistics / quality extension helpers (additive sub-sections only)
# ---------------------------------------------------------------------------

def discovery_statistics_fields(
    result: DiscoveryResult, known_tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return the ``"discovery"`` sub-section to merge into osm_statistics.json."""
    known_tags = known_tags if known_tags is not None else load_reference_tags()
    freq = {value: tag.count for value, tag in result.discovered_tags.items()}

    if not freq:
        return {
            "discovery": {
                "unique_railway_tags": 0,
                "unique_railway_object_types": len(result.by_element_type),
                "tag_frequency_distribution": {},
                "most_common_tag": None,
                "least_common_tag": None,
                "unknown_tag_count": 0,
                "coverage_score": 0.0,
            }
        }

    coverage = compute_coverage(result, known_tags)
    return {
        "discovery": {
            "unique_railway_tags": len(freq),
            "unique_railway_object_types": len(result.by_element_type),
            "tag_frequency_distribution": freq,
            "most_common_tag": max(freq, key=freq.get),
            "least_common_tag": min(freq, key=freq.get),
            "unknown_tag_count": coverage["unsupported_count"],
            "coverage_score": coverage["coverage_percentage"],
        }
    }


def discovery_quality_fields(
    result: DiscoveryResult, known_tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return the ``"discovery"`` sub-section to merge into osm_quality.json."""
    known_tags = known_tags if known_tags is not None else load_reference_tags()
    coverage = compute_coverage(result, known_tags)

    coverage_score = coverage["coverage_percentage"]
    discovery_score = 100.0 if result.total_elements > 0 else 0.0
    unknown_tag_penalty = round(coverage["unsupported_count"] * 2.0, 1)
    overall = round(
        max(0.0, min(100.0, coverage_score * 0.6 + discovery_score * 0.4 - unknown_tag_penalty)),
        1,
    )
    return {
        "discovery": {
            "coverage_score": coverage_score,
            "discovery_score": discovery_score,
            "unknown_tag_penalty": unknown_tag_penalty,
            "overall_collector_quality": overall,
        }
    }


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def write_discovery_report(
    result: DiscoveryResult,
    known_tags: dict[str, str],
    reports_dir: Path,
    collector_version: str,
) -> Path:
    """Write ``reports/osm_discovery_report.json``."""
    coverage = compute_coverage(result, known_tags)
    sorted_tags = sorted(result.discovered_tags.values(), key=lambda t: t.value)

    report = {
        "collector": "osm",
        "collector_version": collector_version,
        "generated_at": timestamp_utc(),
        "region": result.region,
        "runtime_seconds": result.elapsed_seconds,
        "total_elements_scanned": result.total_elements,
        "by_element_type": result.by_element_type,
        "total_railway_tags_discovered": len(result.discovered_tags),
        "known_railway_tags": sorted(known_tags.keys()),
        "unknown_railway_tags": coverage["unsupported_tags"],
        "new_tags_not_currently_supported": coverage["unsupported_tags"],
        "coverage_percentage": coverage["coverage_percentage"],
        "discovered_tags": [
            {
                **tag.to_dict(),
                "supported": tag.value in known_tags,
                "reference_category": known_tags.get(tag.value),
            }
            for tag in sorted_tags
        ],
    }
    ensure_dir(reports_dir)
    dest = reports_dir / "osm_discovery_report.json"
    save_json(report, dest)
    _log.info(
        "Written discovery report → %s (tags=%d coverage=%.1f%%)",
        dest, len(result.discovered_tags), coverage["coverage_percentage"],
    )
    return dest


def write_coverage_report(
    result: DiscoveryResult,
    known_tags: dict[str, str],
    coverage_dir: Path,
    collector_version: str,
) -> Path:
    """Write ``coverage/osm_tag_coverage.json``."""
    coverage = compute_coverage(result, known_tags)
    out = {
        "collector": "osm",
        "collector_version": collector_version,
        "generated_at": timestamp_utc(),
        "region": result.region,
        "total_discovered_tags": coverage["total_discovered_tags"],
        "supported_tags": coverage["supported_tags"],
        "unsupported_tags": coverage["unsupported_tags"],
        "coverage_percentage": coverage["coverage_percentage"],
        "missing_collector_support": coverage["unsupported_tags"],
        "obsolete_configured_tags": coverage["unused_configured_tags"],
        "recommendations": coverage["recommendations"],
    }
    ensure_dir(coverage_dir)
    dest = coverage_dir / "osm_tag_coverage.json"
    save_json(out, dest)
    _log.info(
        "Written coverage report → %s (coverage=%.1f%% unsupported=%d)",
        dest, coverage["coverage_percentage"], coverage["unsupported_count"],
    )
    return dest


def write_capability_matrix(
    result: DiscoveryResult,
    known_tags: dict[str, str],
    implemented_categories: set[str],
    reports_dir: Path,
    collector_version: str,
) -> Path:
    """Write ``reports/collector_capabilities.json``."""
    matrix = build_capability_matrix(result, known_tags, implemented_categories)
    out = {
        "collector": "osm",
        "collector_version": collector_version,
        "generated_at": timestamp_utc(),
        "region": result.region,
        "capabilities": matrix,
    }
    ensure_dir(reports_dir)
    dest = reports_dir / "collector_capabilities.json"
    save_json(out, dest)
    _log.info("Written capability matrix → %s", dest)
    return dest
