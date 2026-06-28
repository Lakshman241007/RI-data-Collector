"""
routing.dfs
-----------
Depth-First Search utilities:

* ``dfs_traversal`` — the full visit order starting from a node (iterative,
  to avoid recursion-depth issues on large graphs).
* ``dfs_path``      — *a* path between two nodes found via DFS backtracking.
  Note this is generally *not* the shortest path — use Dijkstra/A* for that.
"""

from __future__ import annotations

import logging

from routing.models import Graph, PathResult

logger = logging.getLogger(__name__)


def dfs_traversal(graph: Graph, start_id: str) -> list[str]:
    """Return the full DFS visit order starting from ``start_id``."""
    if not graph.has_node(start_id):
        return []

    visited: set[str] = set()
    order: list[str] = []
    stack: list[str] = [start_id]

    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        order.append(current)

        # Push neighbors in reverse so that, when popped, they are visited
        # in the same order they appear in the adjacency list.
        for neighbor_id, _edge_id in reversed(graph.neighbors(current)):
            if neighbor_id not in visited:
                stack.append(neighbor_id)

    return order


def dfs_path(graph: Graph, start_id: str, end_id: str) -> PathResult:
    """Find *a* path between ``start_id`` and ``end_id`` via iterative DFS.

    Unlike BFS/Dijkstra/A*, this does not guarantee a shortest path — it
    returns the first path DFS backtracking discovers.
    """
    if not graph.has_node(start_id) or not graph.has_node(end_id):
        return PathResult(found=False)

    if start_id == end_id:
        return PathResult(found=True, node_ids=[start_id], edge_ids=[], distance_m=0.0)

    visited: set[str] = {start_id}
    # Stack frames are kept 1:1 with the current path. The root frame
    # carries no incoming edge (edge_id is None for start_id).
    path_nodes: list[str] = [start_id]
    path_edges: list[str] = []
    iter_stack: list[iter] = [iter(graph.neighbors(start_id))]
    nodes_expanded = 0

    while iter_stack:
        try:
            neighbor_id, edge_id = next(iter_stack[-1])
        except StopIteration:
            # Dead end at this depth: backtrack one level.
            iter_stack.pop()
            path_nodes.pop()
            if path_edges:
                path_edges.pop()
            continue

        if neighbor_id in visited:
            continue

        nodes_expanded += 1

        if neighbor_id == end_id:
            final_nodes = path_nodes + [neighbor_id]
            final_edges = path_edges + [edge_id]
            distance = sum(graph.edge_length(e) for e in final_edges)
            return PathResult(
                found=True,
                node_ids=final_nodes,
                edge_ids=final_edges,
                distance_m=distance,
                nodes_expanded=nodes_expanded,
            )

        visited.add(neighbor_id)
        path_nodes.append(neighbor_id)
        path_edges.append(edge_id)
        iter_stack.append(iter(graph.neighbors(neighbor_id)))

    return PathResult(found=False, nodes_expanded=nodes_expanded)
