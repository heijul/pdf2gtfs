from __future__ import annotations

from dataclasses import dataclass
from heapq import heappush
from operator import itemgetter

from geopy import distance as _distance

import pandas as pd


def distance(lat1, lon1, lat2, lon2) -> float:
    """ Distance between two locations. """
    dist = _distance.distance((lat1, lon1), (lat2, lon2)).km
    return dist


@dataclass(eq=True, frozen=True)
class StopNode:
    name: str


@dataclass
class Node:
    stop: str
    lat: float
    lon: float

    @staticmethod
    def from_series(series: pd.Series) -> Node:
        return Node(series["name"], series["lat"], series["lon"])


class Cluster:
    stop: StopNode
    lat: float
    lon: float
    nodes: list[Node]
    prev: list[tuple[float, Cluster]]
    next: list[tuple[float, Cluster]]

    def __init__(self, stop: StopNode, lat: float, lon: float,
                 nodes: list[pd.Series]):
        self.stop = stop
        self.lat = lat
        self.lon = lon
        self._prev = []
        self._next = []
        self._set_nodes(nodes)

    def _set_nodes(self, nodes: list[pd.Series]):
        self.nodes = [Node.from_series(node) for node in nodes]

    @property
    def prev(self):
        return self._prev

    @property
    def next(self):
        return self._next

    @property
    def is_dummy(self):
        return self.nodes == []

    def add_prev(self, node: Cluster, dist: float):
        # TODO: Add priority to dist
        heappush(self._prev, (dist, node))

    def add_next(self, node: Cluster, dist: float):
        heappush(self._next, (dist, node))

    def __repr__(self) -> str:
        return f"CNode({self.stop!r}, lat={self.lat}, lon={self.lon})"

    def get_closest(self, other: Cluster | Node) -> Node:
        if self.is_dummy:
            return Node(self.stop.name, self.lat, self.lon)

        dists = [(distance(other.lat, other.lon, node.lat, node.lon), node)
                 for node in self.nodes]
        return min(dists, key=itemgetter(0))[1]

    def __lt__(self, _):
        return False if self.is_dummy else True
