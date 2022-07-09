from __future__ import annotations

from operator import itemgetter
from statistics import mean
from typing import Optional

from geopy import distance as _distance


def distance(lat1, lon1, lat2, lon2) -> float:
    """ Distance between two locations. """
    dist = _distance.distance((lat1, lon1), (lat2, lon2)).km
    return dist


class Node2:
    cluster: Cluster2
    lat: float
    lon: float
    # TODO: Maybe add stop.
    name: str

    def __init__(self, cluster, name, lat, lon) -> None:
        # Remove cluster and add it via add_node
        self.cluster = cluster
        self.name = name
        self.lat = lat
        self.lon = lon

    @property
    def cluster(self) -> Cluster2:
        return self._cluster

    @cluster.setter
    def cluster(self, cluster: Cluster2) -> None:
        self._cluster = cluster
        cluster.add_node(self)

    def distance(self, other: Node2 | Cluster2) -> float:
        return distance(self.lat, self.lon, other.lat, other.lon)


class Cluster2:
    nodes: list[Node2]
    lat: float
    lon: float

    def __init__(self, lat: float, lon: float) -> None:
        self.nodes = []
        self.lat = lat
        self.lon = lon
        self._next = None
        self._prev = None

    @property
    def next(self) -> Cluster2:
        return self._next

    @next.setter
    def next(self, other: Cluster2 | list[Cluster2]) -> None:
        if isinstance(other, list) and other:
            other = self.get_closest_cluster(other)
        self._next = other
        if not other.prev == self:
            other.prev = self

    @property
    def prev(self) -> Cluster2:
        return self._prev

    @prev.setter
    def prev(self, other: Cluster2):
        self._prev = other
        if not other.next == self:
            other.next = self

    def get_closest_cluster(self, clusters: list[Cluster2]) -> Cluster2:
        closest = clusters[0]
        min_dist = distance(self.lat, self.lon, closest.lat, closest.lon)
        for cluster in clusters[1:]:
            dist = distance(self.lat, self.lon, cluster.lat, cluster.lon)
            if dist > min_dist:
                continue
            closest = cluster
            min_dist = dist
        return closest

    def add_node(self, node: Node2) -> None:
        if node in self.nodes:
            return
        self.nodes.append(node)

    def get_closest(self) -> Optional[Node2]:
        if not self.nodes:
            return None
        costs: list[tuple[float, Node2]] = []
        for node in self.nodes:
            cost_next = node.distance(self.next) if self.next else 0
            cost_prev = node.distance(self.prev) if self.prev else 0
            cost_self = node.distance(self)
            # Prefer nodes closer to next node, because vehicles
            #  typically stop at the furthest stop position first.
            # Preferring nodes closer to the cluster location seems to lead
            #  to better results as well. TODO: Needs more testing
            cost = 1.05 * cost_next + cost_prev + 0.5 * cost_self
            costs.append((cost, node))
        return min(costs, key=itemgetter(0))[1]

    def adjust_location(self):
        """ Set the location to the mean of the location of the nodes. """
        self.lat = mean([node.lat for node in self.nodes])
        self.lon = mean([node.lon for node in self.nodes])
