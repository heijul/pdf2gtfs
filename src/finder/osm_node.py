from __future__ import annotations

from math import log
from operator import itemgetter
from typing import Callable, cast, Optional

import pandas as pd

from config import Config
from datastructures.gtfs_output.gtfsstop import GTFSStop
from finder.location import Location
from finder.osm_values import get_osm_value, OSMValue
from finder.public_transport import TransportType
from finder.types import StopName
from utils import get_edit_distance, replace_abbreviations


class OSMNode:
    def __init__(self, name: StopName, stop: StopName, loc: Location,
                 typ: TransportType, values: dict[str: str]) -> None:
        self.name: StopName = name
        self.stop: StopName = stop
        self.loc: Location = loc
        self.type: TransportType = typ
        self.scores: dict[OSMNode: int] = {}
        self.osm_value: OSMValue = get_osm_value()
        self.values: dict[str: str] = values
        # Only calculate the scores that are not dependent on next_node once.
        self.base_scores: dict[str: int] = {
            "name": self._score_name_distance(),
            "transport_type": self._score_transport_type(),
            "stop_score": self._score_stop_type()}

    @staticmethod
    def from_series(s: pd.Series, stop: StopName) -> OSMNode:
        from finder import KEYS_OPTIONAL

        location = Location(s["lat"], s["lon"])
        typ = TransportType.get(s["public_transport"])
        values = {key: value for key, value in s.items()
                  if key in KEYS_OPTIONAL}
        return OSMNode(s["names"], stop, location, typ, values)

    def distance(self, other: OSMNode) -> float:
        """ Return the distance between the locations of two Nodes. """
        return self.loc.distance(other.loc)

    def _calculate_score(self, next_node: OSMNode, min_dist: float) -> int:
        """ Calculates the score of the node, depending on the next node in
         the route and the minimal distance of the nodes with the same stop
         to the next node. Lower is better. """
        distance_score = self._score_distance(next_node, min_dist)
        return distance_score + sum(self.base_scores.values())

    def _score_name_distance(self) -> int:
        """ Score of the name, depending on the edit distance. """
        name_distance = self.name_distance(self.stop)
        if name_distance == 0:
            return 0
        return int(log(name_distance, 1.5))

    def _score_distance(self, next_node: OSMNode, min_dist: float) -> int:
        """ Scores the node based on the difference in distance to next node
        to the minimum distance. """
        dist_diff = self.distance(next_node) - min_dist
        if dist_diff == 0:
            return 0
        # Flatten the curve, so higher distances do not increase the score
        # too much, which would result in distance being the only deciding factor.
        return int(log(dist_diff, 4) * 0.3 * log(dist_diff, 20))

    def _score_transport_type(self) -> int:
        return cast(int, self.type.value)

    def _score_stop_type(self) -> int:
        """ Score the Node based on its additional attributes. """
        return self.osm_value.score(self.values)

    def name_distance(self, stop) -> int:
        """ Edit distance between name and stop after normalizing both. """
        name = replace_abbreviations(self.name).casefold().lower()
        stop = replace_abbreviations(stop).casefold().lower()
        # TODO: permutations
        if name == stop:
            return 0
        return get_edit_distance(name, stop)

    def __repr__(self) -> str:
        return f"OSMNode({self.name}, {self.loc}, {self.type})"

    def calculate_score(self, current: OSMNode, min_dist: float) -> None:
        if current in self.scores:
            return self.scores[current]
        self.scores[current] = self._calculate_score(current, min_dist)

    def __lt__(self, other: OSMNode) -> bool:
        ours = self.base_scores
        theirs = other.base_scores
        return (ours["name"] < theirs["name"] or
                ours["stop_score"] < theirs["stop_score"] or
                ours["transport_type"] < theirs["transport_types"])


class ExistingOSMNode(OSMNode):
    def _calculate_score(self, next_node: OSMNode, min_dist: float) -> int:
        if not self.loc.valid():
            return 1000
        return super()._calculate_score(next_node, min_dist)

    @staticmethod
    def from_gtfsstop(stop: GTFSStop) -> ExistingOSMNode:
        loc = Location(stop.stop_lat, stop.stop_lon)
        name = stop.stop_name
        return ExistingOSMNode(name, name, loc, TransportType(-1), {})


class DummyOSMNode(OSMNode):
    def __init__(self, stop: StopName):
        super().__init__(stop, stop, Location(-1, -1), TransportType.Dummy, {})

    def __repr__(self) -> str:
        return f"DummyOSMNode({self.name})"


def get_min_node(nodes: list[OSMNode], parent: OSMNode) -> OSMNode:
    """ Return the node out of nodes with minimal distance to parent. """
    scores = [(node.scores.get(parent, 1000), node) for node in nodes]
    return min(scores, key=itemgetter(0))[1]


class Route3:
    def __init__(self, nodes: list[OSMNode]) -> None:
        self.nodes = nodes

    @staticmethod
    def from_nodes(stops: list[StopName], end: OSMNode,
                   nodes: dict[StopName: tuple[list[OSMNode], bool]],
                   extended_node_generator: Callable[[str], list[OSMNode]]
                   ) -> Route3:
        def get_min_dist() -> float:
            valid_stop_nodes = [n for n in stop_nodes
                                if not isinstance(n, DummyOSMNode)]
            return min([current.distance(n) for n in valid_stop_nodes],
                       default=-1)

        def has_no_valid_nodes() -> bool:
            return min_dist < 0 or min_dist > Config.max_stop_distance * 1000

        current = end
        route = [end]
        for stop in list(reversed(stops))[1:]:
            stop_nodes, extended_regex = nodes[stop]
            min_dist = get_min_dist()
            # Create nodes with extended regex, if no valid nodes are found.
            if has_no_valid_nodes() and not extended_regex:
                nodes[stop] = extended_node_generator(stop), True
                min_dist = get_min_dist()

            if has_no_valid_nodes():
                # CHECK: Maybe current needs to be updated?! If yes, how?
                route.insert(0, DummyOSMNode(stop))
                continue
            for node in stop_nodes:
                node.calculate_score(current, min_dist)
            current = get_min_node(stop_nodes, current)
            route.insert(0, current)

        return Route3(route)

    @property
    def length(self) -> float:
        """ Return the cumulative distance between each node. """
        def get_first_valid_node() -> Optional[OSMNode]:
            """ Return the first node that is not a dummy node. """
            for n in self.nodes:
                if isinstance(n, DummyOSMNode):
                    continue
                return n
            return None

        last = get_first_valid_node()
        if not last:
            return 0

        dist = 0
        for node in self.nodes[1:]:
            if isinstance(node, DummyOSMNode):
                continue
            dist += last.distance(node)
            last = node

        return dist

    @property
    def invalid_node_count(self) -> int:
        return sum([1 for node in self.nodes
                    if isinstance(node, DummyOSMNode)])

    def __lt__(self, other: Route3) -> bool:
        if self.invalid_node_count == other.invalid_node_count:
            return self.length < other.length
        return self.invalid_node_count < other.invalid_node_count
