"""
routing.validator
-------------------
Validates the full set of built routes and produces the structured report
exported as ``validation.json``:

* **missing_nodes**       — requests whose source/target id isn't in the graph.
* **disconnected_paths**  — requests where both endpoints exist but no path
  was found between them (different connected components).
* **invalid_routes**      — successfully "found" routes that fail a sanity
  check (e.g. a station appears twice, or consecutive stations in the
  route aren't actually joined by the claimed edge). These indicate a bug
  in a pathfinding algorithm rather than a data problem, and should
  normally be an empty list.

The Phase-2-inherited graph data-quality issues (self-loops, null
endpoints) recorded by the graph loader are also included for
transparency under ``graph_load_issues``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

from routing.models import Graph, RouteResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationReport:
    issue_counts: dict[str, int] = field(default_factory=dict)
    missing_nodes: list[dict] = field(default_factory=list)
    disconnected_paths: list[dict] = field(default_factory=list)
    invalid_routes: list[dict] = field(default_factory=list)
    graph_load_issues: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _sanity_check_route(graph: Graph, route: RouteResult) -> str | None:
    """Return an error string if ``route`` fails a structural sanity check."""
    if len(route.station_ids) != route.node_count:
        return "node_count_mismatch"
    if len(route.edge_ids) != route.edge_count:
        return "edge_count_mismatch"
    if route.node_count > 1 and route.edge_count != route.node_count - 1:
        return "edge_node_count_inconsistent"
    if len(set(route.station_ids)) != len(route.station_ids):
        return "repeated_station_in_route"

    # Every consecutive pair of stations must actually be joined by the
    # edge claimed at that position in `edge_ids`.
    for i, edge_id in enumerate(route.edge_ids):
        edge = graph.edges.get(edge_id)
        if edge is None:
            return f"unknown_edge:{edge_id}"
        a, b = route.station_ids[i], route.station_ids[i + 1]
        if {edge.source, edge.target} != {a, b}:
            return f"edge_endpoint_mismatch:{edge_id}"

    return None


def validate_routes(graph: Graph, routes: list[RouteResult]) -> ValidationReport:
    """Classify every route result into the validation report categories."""
    report = ValidationReport()

    for route in routes:
        if not route.success:
            if route.error and route.error.startswith("missing_node"):
                report.missing_nodes.append(
                    {
                        "route_id": route.route_id,
                        "algorithm": route.algorithm.value,
                        "source_id": route.source_id,
                        "target_id": route.target_id,
                        "detail": route.error,
                    }
                )
            elif route.error == "disconnected":
                report.disconnected_paths.append(
                    {
                        "route_id": route.route_id,
                        "algorithm": route.algorithm.value,
                        "source_id": route.source_id,
                        "target_id": route.target_id,
                        "nodes_expanded": route.nodes_expanded,
                    }
                )
            else:
                report.invalid_routes.append(
                    {
                        "route_id": route.route_id,
                        "algorithm": route.algorithm.value,
                        "source_id": route.source_id,
                        "target_id": route.target_id,
                        "detail": route.error or "unknown_failure",
                    }
                )
            continue

        sanity_error = _sanity_check_route(graph, route)
        if sanity_error is not None:
            report.invalid_routes.append(
                {
                    "route_id": route.route_id,
                    "algorithm": route.algorithm.value,
                    "source_id": route.source_id,
                    "target_id": route.target_id,
                    "detail": sanity_error,
                }
            )

    report.graph_load_issues = {
        "node_count": graph.load_report.node_count,
        "edge_count": graph.load_report.edge_count,
        "skipped_self_loops": graph.load_report.skipped_self_loops,
        "skipped_null_endpoint_edges": len(graph.load_report.skipped_null_endpoint_edges),
        "skipped_missing_node_edges": len(graph.load_report.skipped_missing_node_edges),
    }

    report.issue_counts = {
        "missing_nodes": len(report.missing_nodes),
        "disconnected_paths": len(report.disconnected_paths),
        "invalid_routes": len(report.invalid_routes),
    }

    logger.info(
        "Validation — missing_nodes=%d disconnected_paths=%d invalid_routes=%d",
        report.issue_counts["missing_nodes"],
        report.issue_counts["disconnected_paths"],
        report.issue_counts["invalid_routes"],
    )

    return report
