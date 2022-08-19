from __future__ import annotations

from math import log
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
        self.score: int = 1000
        self.name: StopName = name
        self.stop: StopName = stop
        self.loc: Location = loc
        self.type: TransportType = typ
        self.osm_value: OSMValue = get_osm_value()
        self.values: dict[str: str] = values

    @staticmethod
    def from_series(s: pd.Series, stop: StopName) -> OSMNode:
        from finder import KEYS_OPTIONAL

        location = Location(s["lat"], s["lon"])
        typ = TransportType.get(s["public_transport"])
        values = {key: value for key, value in s.items()
                  if key in KEYS_OPTIONAL}
        return OSMNode(s["name"], stop, location, typ, values)

    def distance(self, other: OSMNode) -> float:
        return self.loc.distance(other.loc)

    def _calculate_score(self, next_node: OSMNode, min_dist: float) -> int:
        # TODO: Precalculate name_score and stop_score
        #  + mb transport_type_score
        name_score = self._score_name_distance()
        distance_score = self._score_distance(next_node, min_dist)
        transport_type_score = self._score_transport_type()
        stop_score = self._score_stop_type()
        return name_score + distance_score + transport_type_score + stop_score

    def _score_name_distance(self) -> int:
        name_distance = self.name_distance(self.stop)
        if name_distance == 0:
            return 0
        return int(log(name_distance, 1.5))

    def _score_distance(self, next_node: OSMNode, min_dist: float) -> int:
        dist_diff = self.distance(next_node) - min_dist
        if dist_diff == 0:
            return 0
        return int(log(dist_diff, 4) * 0.3 * log(dist_diff, 20))

    def _score_transport_type(self) -> int:
        return cast(int, self.type.value)

    def _score_stop_type(self) -> int:
        return self.osm_value.score(self.values)

    def name_distance(self, stop) -> int:
        name = replace_abbreviations(self.name).casefold().lower()
        stop = replace_abbreviations(stop).casefold().lower()
        # TODO: permutations
        if name == stop:
            return 0
        return get_edit_distance(name, stop)

    def __repr__(self) -> str:
        return f"OSMNode({self.name}, {self.loc}, {self.type}, {self.score})"

    def calculate_score(self, current: OSMNode, min_dist: float) -> None:
        self.score = self._calculate_score(current, min_dist)

    def __lt__(self, other: OSMNode) -> bool:
        # TODO: Add checks depending on preference (name, etc.)
        return self.score < other.score


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
