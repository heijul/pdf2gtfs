from __future__ import annotations

from abc import ABC, abstractmethod
from statistics import mean
from typing import Optional

from geopy import distance as _distance

from config import Config
from finder.public_transport import PublicTransport, Location
from finder.types import StopName


def distance(lat1, lon1, lat2, lon2) -> float:
    """ Distance between two locations. """
    dist = _distance.distance((lat1, lon1), (lat2, lon2)).km
    return dist


def closer_node(node1: Node2, node2: Node2, cluster: Cluster2) -> Node2:
    if node1.distance(cluster) <= node2.distance(cluster):
        return node1
    return node2


class _Base(ABC):
    @property
    @abstractmethod
    def loc(self) -> Location:
        pass

    def distance(self, other: _Base) -> float:
        return self.loc.distance(other.loc)


class Node2(_Base):
    cluster: Cluster2
    transport: PublicTransport
    # FEATURE: Maybe add stop, could possibly make some things easier.
    name: str

    def __init__(self, cluster: Cluster2, transport: PublicTransport) -> None:
        # Remove cluster and add it via add_node
        self.cluster = cluster
        self.transport = transport
        self.name = transport.name
        super().__init__()

    @property
    def cluster(self) -> Cluster2:
        return self._cluster

    @cluster.setter
    def cluster(self, cluster: Cluster2) -> None:
        self._cluster = cluster
        cluster.add_node(self)

    @property
    def loc(self) -> Location:
        return self.transport.location

    def __lt__(self, other: Node2) -> bool:
        if (self.transport.location.close(other.transport.location) and
                self.transport != other.transport):
            return self.transport <= other.transport
        return self == closer_node(self, other, self.cluster)

    def __repr__(self):
        return f"Node2('{self.name}', ({self.loc}))"


class Cluster2(_Base):
    stop: StopName
    nodes: list[Node2]

    def __init__(self, stop: StopName, location: Location) -> None:
        self.nodes = []
        self.stop = stop
        self._loc = location
        self._next = None
        self._prev = None
        super().__init__()

    @property
    def loc(self) -> Location:
        return self._loc

    @loc.setter
    def loc(self, value: Location) -> None:
        self._loc = value

    @property
    def next(self) -> Cluster2:
        return self._next

    @next.setter
    def next(self, other: Cluster2 | list[Cluster2]) -> None:
        # TODO: Raise error if other is list and empty
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
        def get_dist_modifier(_cluster) -> float:
            return (1 + 0.2 * min([node.transport.name_dist()
                                   for node in _cluster.nodes]))

        closest = clusters[0]
        min_dist = self.distance(closest)
        min_dist *= get_dist_modifier(closest)
        for cluster in clusters[1:]:
            dist = self.distance(cluster)
            # TODO: Need to check this for min_dist as well
            if dist > Config.max_stop_distance:
                continue
            dist *= get_dist_modifier(cluster)
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
        min_node = self.nodes[0]
        for node in self.nodes[1:]:
            if node < min_node:
                min_node = node
        return min_node

    def adjust_location(self):
        """ Set the location to the mean of the location of the nodes. """
        lat = mean([node.loc.lat for node in self.nodes])
        lon = mean([node.loc.lon for node in self.nodes])
        self.loc = Location(lat, lon)

    def __repr__(self):
        return f"Cluster({self.stop}, ({self.loc}))"


class DummyCluster2(Cluster2):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, Location(-1, -1))
