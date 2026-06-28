"""
graph/connectivity.py
-----------------------
Graph connectivity utilities for the Phase 2.2 railway graph: attaching
edges to their endpoint nodes, finding isolated stations, and computing
connected components via a union-find (disjoint set) structure.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Sequence

from graph.edge_builder import GraphEdge
from graph.node_builder import GraphNode

logger = logging.getLogger(__name__)


def attach_edges_to_nodes(
    nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]
) -> None:
    """
    Populate each GraphNode.edge_ids with the ids of every edge that has
    that node as a source or target. Mutates *nodes* in place.

    A self-loop (source == target) contributes its edge id to that node
    exactly once.
    """
    lookup = {n.node_id: n for n in nodes}
    attached = 0

    for edge in edges:
        endpoint_ids = {
            nid for nid in (edge.source_node_id, edge.target_node_id) if nid
        }
        for node_id in endpoint_ids:
            node = lookup.get(node_id)
            if node is not None:
                node.edge_ids.append(edge.edge_id)
                attached += 1

    logger.info("Attached edges to nodes (%d node-edge links)", attached)


def find_isolated_nodes(nodes: Sequence[GraphNode]) -> list[GraphNode]:
    """Return all nodes with no connected edges."""
    return [n for n in nodes if not n.edge_ids]


class _UnionFind:
    """Disjoint-set structure with path halving and union by attachment."""

    __slots__ = ("_parent",)

    def __init__(self, items: Sequence[str]):
        self._parent: dict[str, str] = {item: item for item in items}

    def find(self, x: str) -> str:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def compute_connected_components(
    nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]
) -> list[list[str]]:
    """
    Compute the connected components of the graph.

    Parameters
    ----------
    nodes : sequence of GraphNode
    edges : sequence of GraphEdge

    Returns
    -------
    list[list[str]]
        Node-id lists, one per connected component, sorted largest first.
        Isolated nodes (no valid edges) each form their own singleton
        component.
    """
    if not nodes:
        return []

    uf = _UnionFind(n.node_id for n in nodes)

    for edge in edges:
        if edge.source_node_id and edge.target_node_id:
            uf.union(edge.source_node_id, edge.target_node_id)

    groups: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        groups[uf.find(n.node_id)].append(n.node_id)

    components = sorted(groups.values(), key=len, reverse=True)
    logger.info(
        "Computed %d connected component(s) across %d nodes",
        len(components), len(nodes),
    )
    return components
