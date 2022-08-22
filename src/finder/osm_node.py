from __future__ import annotations

from math import log
from operator import itemgetter
from typing import cast

import pandas as pd

from datastructures.gtfs_output.gtfsstop import GTFSStop
from finder.location import Location
from finder.osm_values import get_osm_value, OSMValue
from finder.public_transport import TransportType
from finder.types import StopName
from utils import get_edit_distance, replace_abbreviations


class OSMNode:
    def __init__(self, name: StopName, stop: StopName, loc: Location,
                 typ: TransportType, values: dict[str: str]) -> None:
        self.scores: dict[OSMNode: int] = {}
        self.name: StopName = name
        self.stop: StopName = stop
        self.loc: Location = loc
        self.type: TransportType = typ
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
        return OSMNode(s["name"], stop, location, typ, values)

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
        # TODO: Add checks depending on preference (name, etc.)
        return False


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


def get_min_node(nodes: list[OSMNode], parent: OSMNode) -> OSMNode:
    """ Return the node out of nodes with minimal distance to parent. """
    scores = [(node.scores.get(parent, 1000), node) for node in nodes]
    return min(scores, key=itemgetter(0))[1]
