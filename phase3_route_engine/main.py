"""
main.py
-------
Phase 3.1 pipeline entry point — Railway Route Engine.

Pipeline
--------
1. Load railway_graph.json         -> Graph (nodes + adjacency lists)
2. Discover connected components   -> BFS
3. Generate route requests         -> sampled valid pairs + synthetic
                                       disconnected / missing-node cases
4. Build routes                    -> BFS / DFS / Dijkstra / A*
5. Validate routes                 -> validation.json
6. Compute statistics              -> statistics.json
7. Export routes                   -> routes.json
"""

from __future__ import annotations

import itertools
import json
import logging
import logging.handlers
import random
import sys
import time
from pathlib import Path

from routing.bfs import bfs_connected_components
from routing.exporter import export_routes, export_statistics, export_validation
from routing.graph_loader import load_graph
from routing.models import AlgorithmType, Graph, RequestKind, RouteRequest
from routing.route_builder import build_routes
from routing.statistics import compute_route_statistics
from routing.validator import validate_routes


# ---------------------------------------------------------------------------
# Bootstrap: configure logging before importing any routing module's
# work happens, so every module-level logger is already configured.
# ---------------------------------------------------------------------------

def _setup_logging(settings: dict) -> None:
    log_cfg = settings.get("logging", {})
    log_dir = Path(log_cfg.get("directory", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = log_dir / log_cfg.get("filename", "phase3_route_engine.log")

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def _load_settings(config_path: Path) -> dict:
    with config_path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Route request generation
# ---------------------------------------------------------------------------

def _generate_sampled_requests(
    graph: Graph,
    components: list[set[str]],
    rng: random.Random,
    algorithms: list[AlgorithmType],
    max_routes_per_component: int,
    max_component_size_for_full_pairs: int,
    max_total_routes: int,
) -> list[RouteRequest]:
    """Sample valid (connected) source/target pairs across components.

    Small components (<= ``max_component_size_for_full_pairs`` nodes) get
    every distinct pair exercised (capped by ``max_routes_per_component``);
    larger components get a random sample of pairs. Algorithms are
    assigned round-robin so every algorithm gets exercised across the set.
    """
    requests: list[RouteRequest] = []
    algo_cycle = itertools.cycle(algorithms)
    seq = 0

    for component in components:
        if len(requests) >= max_total_routes:
            break
        if len(component) < 2:
            continue

        members = sorted(component)
        if len(members) <= max_component_size_for_full_pairs:
            candidate_pairs = list(itertools.combinations(members, 2))
        else:
            candidate_pairs = [tuple(rng.sample(members, 2)) for _ in range(max_routes_per_component * 2)]

        rng.shuffle(candidate_pairs)
        chosen = candidate_pairs[:max_routes_per_component]

        for source_id, target_id in chosen:
            if len(requests) >= max_total_routes:
                break
            seq += 1
            requests.append(
                RouteRequest(
                    request_id=f"route_{seq:05d}",
                    source_id=source_id,
                    target_id=target_id,
                    algorithm=next(algo_cycle),
                    kind=RequestKind.SAMPLED,
                )
            )

    return requests


def _generate_synthetic_disconnected_requests(
    graph: Graph,
    components: list[set[str]],
    rng: random.Random,
    algorithms: list[AlgorithmType],
    count: int,
    start_seq: int,
) -> list[RouteRequest]:
    """Pick pairs of nodes from *different* components — these should be
    reported as disconnected_paths during validation."""
    requests: list[RouteRequest] = []
    non_trivial = [c for c in components if c]
    if len(non_trivial) < 2:
        return requests

    algo_cycle = itertools.cycle(algorithms)
    seq = start_seq

    for _ in range(count):
        comp_a, comp_b = rng.sample(non_trivial, 2)
        source_id = rng.choice(sorted(comp_a))
        target_id = rng.choice(sorted(comp_b))
        seq += 1
        requests.append(
            RouteRequest(
                request_id=f"route_{seq:05d}",
                source_id=source_id,
                target_id=target_id,
                algorithm=next(algo_cycle),
                kind=RequestKind.SYNTHETIC_DISCONNECTED,
            )
        )

    return requests


def _generate_synthetic_missing_node_requests(
    graph: Graph,
    rng: random.Random,
    algorithms: list[AlgorithmType],
    count: int,
    start_seq: int,
) -> list[RouteRequest]:
    """Reference a node id that doesn't exist in the graph — these should
    be reported as missing_nodes during validation."""
    requests: list[RouteRequest] = []
    real_node_ids = list(graph.nodes.keys())
    if not real_node_ids:
        return requests

    algo_cycle = itertools.cycle(algorithms)
    seq = start_seq

    for i in range(count):
        valid_id = rng.choice(real_node_ids)
        bogus_id = f"node_missing_{i:04d}"
        seq += 1
        requests.append(
            RouteRequest(
                request_id=f"route_{seq:05d}",
                source_id=valid_id,
                target_id=bogus_id,
                algorithm=next(algo_cycle),
                kind=RequestKind.SYNTHETIC_MISSING_NODE,
            )
        )

    return requests


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(settings: dict, base: Path) -> None:
    logger = logging.getLogger("pipeline")
    t_start = time.perf_counter()

    input_path = base / settings["input"]["directory"] / settings["input"]["graph_file"]
    out_dir = base / settings["output"]["directory"]
    out_dir.mkdir(parents=True, exist_ok=True)

    routes_path = out_dir / settings["output"]["routes_file"]
    stats_path = out_dir / settings["output"]["statistics_file"]
    validation_path = out_dir / settings["output"]["validation_file"]

    gen_cfg = settings.get("route_generation", {})
    rng = random.Random(gen_cfg.get("random_seed", 42))
    algorithms = [AlgorithmType(a) for a in gen_cfg.get("algorithms", ["bfs", "dfs", "dijkstra", "astar"])]

    # ── Step 1: Load graph ──────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1 — Loading railway graph")
    graph = load_graph(input_path)
    logger.info("Graph: %d nodes, %d edges", len(graph.nodes), len(graph.edges))

    # ── Step 2: Connected components (BFS) ───────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2 — Discovering connected components (BFS)")
    components = bfs_connected_components(graph)
    sizes = sorted((len(c) for c in components), reverse=True)
    logger.info(
        "Components: %d total, largest=%d, %d are single-node (isolated)",
        len(components),
        sizes[0] if sizes else 0,
        sum(1 for s in sizes if s == 1),
    )

    # ── Step 3: Generate route requests ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 3 — Generating route requests")
    sampled = _generate_sampled_requests(
        graph,
        components,
        rng,
        algorithms,
        max_routes_per_component=gen_cfg.get("max_routes_per_component", 3),
        max_component_size_for_full_pairs=gen_cfg.get("max_component_size_for_full_pairs", 6),
        max_total_routes=gen_cfg.get("max_total_routes", 250),
    )
    next_seq = len(sampled)
    disconnected = _generate_synthetic_disconnected_requests(
        graph,
        components,
        rng,
        algorithms,
        count=gen_cfg.get("synthetic_disconnected_requests", 5),
        start_seq=next_seq,
    )
    next_seq += len(disconnected)
    missing_node = _generate_synthetic_missing_node_requests(
        graph,
        rng,
        algorithms,
        count=gen_cfg.get("synthetic_missing_node_requests", 5),
        start_seq=next_seq,
    )

    all_requests = sampled + disconnected + missing_node
    logger.info(
        "Requests: %d sampled, %d synthetic-disconnected, %d synthetic-missing-node "
        "(total=%d)",
        len(sampled),
        len(disconnected),
        len(missing_node),
        len(all_requests),
    )

    # ── Step 4: Build routes ─────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4 — Building routes (BFS / DFS / Dijkstra / A*)")
    routes = build_routes(graph, all_requests)

    # ── Step 5: Validate ─────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 5 — Validating routes")
    validation_report = validate_routes(graph, routes)

    # ── Step 6: Statistics ────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 6 — Computing statistics")
    stats = compute_route_statistics(routes)

    # ── Step 7: Export ────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 7 — Exporting outputs")
    export_routes(routes, routes_path)
    export_statistics(stats, stats_path)
    export_validation(validation_report, validation_path)

    elapsed = time.perf_counter() - t_start
    logger.info("=" * 60)
    logger.info("Pipeline complete in %.2f s", elapsed)
    logger.info("Output directory: %s", out_dir.resolve())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    base_dir = Path(__file__).parent
    config_path = base_dir / "config" / "route_settings.json"
    settings = _load_settings(config_path)
    _setup_logging(settings)
    run_pipeline(settings, base_dir)
