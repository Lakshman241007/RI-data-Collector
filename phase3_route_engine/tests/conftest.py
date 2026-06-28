"""
Shared pytest fixtures: a small, hand-built synthetic graph used across
the unit tests so each algorithm is tested against a known topology
instead of the (huge, messy) Phase 2 dataset.

Topology (undirected):

    A --10km-- B --20km-- C
    |                     |
   15km                 5km
    |                     |
    D --------30km------- E

    F --1km-- G        (separate component)

    H                   (isolated node)

Node coordinates are placed on a simple grid so the geographic heuristic
used by A* has something meaningful to chew on.
"""

from __future__ import annotations

import pytest

from routing.models import Edge, Graph, GraphLoadReport, Node


def _node(node_id: str, lat: float, lon: float, name: str = "") -> Node:
    return Node(
        id=node_id,
        station_id=node_id.replace("node_", ""),
        name=name,
        latitude=lat,
        longitude=lon,
        station_type="station",
    )


def _edge(edge_id: str, source: str, target: str, length_m: float) -> Edge:
    return Edge(
        id=edge_id,
        track_id=edge_id.replace("edge_", ""),
        source=source,
        target=target,
        length_m=length_m,
    )


@pytest.fixture
def sample_graph() -> Graph:
    nodes = {
        "A": _node("A", 0.00, 0.00, "Alpha"),
        "B": _node("B", 0.10, 0.00, "Bravo"),
        "C": _node("C", 0.20, 0.00, "Charlie"),
        "D": _node("D", 0.00, 0.10, "Delta"),
        "E": _node("E", 0.20, 0.10, "Echo"),
        "F": _node("F", 1.00, 1.00, "Foxtrot"),
        "G": _node("G", 1.00, 1.01, "Golf"),
        "H": _node("H", 2.00, 2.00, "Hotel"),
    }

    edges = {
        "AB": _edge("AB", "A", "B", 10_000.0),
        "BC": _edge("BC", "B", "C", 20_000.0),
        "AD": _edge("AD", "A", "D", 15_000.0),
        "CE": _edge("CE", "C", "E", 5_000.0),
        "DE": _edge("DE", "D", "E", 30_000.0),
        "FG": _edge("FG", "F", "G", 1_000.0),
    }

    adjacency: dict[str, list[tuple[str, str]]] = {n: [] for n in nodes}
    for edge in edges.values():
        adjacency[edge.source].append((edge.target, edge.id))
        adjacency[edge.target].append((edge.source, edge.id))

    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        load_report=GraphLoadReport(node_count=len(nodes), edge_count=len(edges)),
    )
