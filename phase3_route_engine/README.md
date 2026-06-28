# Phase 3.1 — Railway Route Engine

Pathfinding engine that consumes the Phase 2 artifact `railway_graph.json`
and produces three outputs: `routes.json`, `statistics.json`,
`validation.json`. It does **not** read, import, or modify any Phase 2
code — only the JSON file Phase 2 already wrote to disk.

## Layout

```
phase3_route_engine/
├── main.py                  # pipeline entry point
├── config/route_settings.json
├── input/railway_graph.json # copy of the Phase 2 output artifact
├── output/                  # routes.json, statistics.json, validation.json
├── logs/                    # rotating log file
├── routing/
│   ├── models.py            # Node, Edge, Graph, RouteRequest/Result, enums
│   ├── graph_loader.py       # railway_graph.json -> Graph (adjacency lists)
│   ├── bfs.py                # connectivity, connected components, hop-shortest path
│   ├── dfs.py                # full traversal order + DFS-discovered path
│   ├── dijkstra.py           # weighted shortest path (heapq)
│   ├── heuristics.py         # haversine geographic heuristic
│   ├── astar.py              # weighted shortest path, geo-heuristic guided
│   ├── route_builder.py      # dispatches a request to the right algorithm,
│   │                         # times it, builds an ordered RouteResult
│   ├── validator.py          # classifies failures: missing_nodes /
│   │                         # disconnected_paths / invalid_routes
│   ├── statistics.py         # average/longest/shortest route, per-algo timings
│   └── exporter.py           # JSON writers for the three output files
└── tests/                    # pytest unit tests (one file per module)
```

## Running

```bash
cd phase3_route_engine
pip install -r requirements.txt --break-system-packages   # only needed for tests
python main.py
```

This reads `input/railway_graph.json` and writes:

- `output/routes.json` — every route attempted, with its ordered station
  list, distance (m), node/edge counts, and timing.
- `output/statistics.json` — aggregate stats: average/longest/shortest
  route, and per-algorithm (BFS/DFS/Dijkstra/A*) timing breakdown.
- `output/validation.json` — `missing_nodes`, `disconnected_paths`, and
  `invalid_routes` (structural sanity-check failures), plus a summary of
  the data-quality issues (self-loops, null-endpoint edges) inherited
  from the Phase 2 graph.

## How routes are chosen

The underlying graph is highly fragmented (~2,000 connected components,
largest only ~19 nodes), so `main.py`:

1. Runs BFS to find every connected component.
2. Samples valid source/target pairs from within components (exhaustive
   pairs for small components, random sampling for larger ones),
   distributing them round-robin across all four algorithms.
3. Adds a handful of **synthetic** requests that are deliberately invalid
   — one node from each of two different components (→ exercises
   `disconnected_paths` in validation) and a request referencing a
   nonexistent node id (→ exercises `missing_nodes`).

All of this is configurable in `config/route_settings.json`
(`random_seed`, `max_total_routes`, `algorithms`, etc.).

## Algorithms

| Module        | Guarantees shortest? | Weighted by `length_m`? | Notes |
|---------------|----------------------|--------------------------|-------|
| `bfs.py`      | Yes (fewest hops)     | No (distance reported, not minimized) | Also used for connectivity/components |
| `dfs.py`      | No                    | No                        | Returns the first path DFS backtracking finds |
| `dijkstra.py` | Yes                   | Yes                       | Binary heap (`heapq`) priority queue |
| `astar.py`    | Yes (admissible heuristic) | Yes                  | Haversine distance-to-goal heuristic |

## Explicitly out of scope

Per the Phase 3.1 brief, this engine does **not** implement train
movement, signalling, scheduling, or physics — it only computes static
routes over the graph topology.

## Tests

```bash
python -m pytest
```

47 unit tests cover the graph loader (including malformed-data handling
inherited from Phase 2: self-loops, null endpoints, missing nodes),
each algorithm module, route building, validation classification,
statistics aggregation, and JSON export — using a small hand-built
8-node synthetic graph (`tests/conftest.py`) rather than the full
3,000-node Phase 2 dataset, so behavior is verified against known,
hand-computed expected paths and distances.
