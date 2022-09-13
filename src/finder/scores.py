from __future__ import annotations

import re
from operator import attrgetter
from typing import NamedTuple, TypeAlias

import pandas as pd
from geopy.distance import distance

from finder.location import Location
from finder.types import StopName, StopNames
from utils import get_edit_distance, replace_abbreviations


DF: TypeAlias = pd.DataFrame


def _normalize_stop(stop: str) -> str:
    return replace_abbreviations(stop).casefold().lower()


def _create_stop_regex(stop: str) -> str:
    return "|".join([re.escape(s) for s in stop.split("|")])


def _compile_regex(regex: str) -> re.Pattern[str]:
    flags = re.IGNORECASE + re.UNICODE
    return re.compile(regex, flags=flags)


def _filter_df_by_stop(stop: str, full_df: DF) -> DF:
    c_regex = _compile_regex(_create_stop_regex(_normalize_stop(stop)))
    df = full_df[full_df["names"].str.contains(c_regex, regex=True)]
    return df.copy()


def split_df(stops: StopNames, full_df: DF) -> DF:
    def name_distance(name) -> int:
        """ Edit distance between name and stop after normalizing both. """
        normal_name = _normalize_stop(name)
        normal_stop = _normalize_stop(stop)
        # TODO: permutations
        if normal_name == normal_stop:
            return 0
        return get_edit_distance(normal_name, normal_stop)

    split = pd.DataFrame()
    for stop in stops:
        df = _filter_df_by_stop(stop, full_df)
        df.loc[:, "name_score"] = df["names"].apply(name_distance)
        df.loc[:, "stop"] = stop
        df.loc[:, "idx"] = df.index
        split = pd.concat([split, df], ignore_index=True)
    return split


def find_shortest_route(stops: StopNames, full_df: DF) -> None:
    df = split_df(stops, full_df)
    dd = DuoDijkstra(stops, df)
    dd.dijkstra()


class DuoDijkstra:
    def __init__(self, stops: StopNames, df: DF) -> None:
        self.df = df
        self.stops = stops
        self.start_node = StartNode(self.stops[-1])
        self.end_node = EndNode(self.stops[0])
        self.nodes: Nodes = Nodes()

    def get_neighbors(self, current_node: DijkstraNode) -> DF | DijkstraNode:
        if isinstance(current_node, EndNode):
            return pd.DataFrame()
        if isinstance(current_node, StartNode):
            stop_idx = -1
        else:
            stop_idx = self.stops.index(current_node.stop)
        if stop_idx == 0:
            return self.end_node
        return self.df[self.df["stop"] == self.stops[stop_idx - 1]]

    def dijkstra(self) -> None:
        current_node: DijkstraNode = self.start_node
        while True:
            # Update neighbors.
            neighbors = self.get_neighbors(current_node)
            if isinstance(neighbors, EndNode):
                self.end_node.parent = current_node
                break
            for neighbor in neighbors.itertuples(False, "StopPosition"):
                neighbor: StopPosition
                # TODO: Check rough distance before creating node.
                neighbor_node = self.nodes.get_or_create(neighbor)
                dist = current_node.distance_to(neighbor_node)
                # TODO: Need to filter nodes with too much distance
                if dist < neighbor_node.dist:
                    neighbor_node.parent = current_node
                    neighbor_node.dist = dist

            current_node.visited = True
            if current_node == self.end_node:
                break

            current_node = self.get_current()

    def get_current(self) -> DijkstraNode:
        min_node = self.nodes.get_min_node()
        if min_node:
            return min_node
        raise Exception("AAA")
        # TODO: Return dummynode with some fix score in case of missing node


class DijkstraNode:
    def __init__(self, stop: str, idx: int, loc: Location | None) -> None:
        self.stop = stop
        self.idx = idx
        self.loc = loc
        self.stop_score = 0
        self.dist = float("inf")
        self.parent = None
        self.visited = False
        self.done = False

    @property
    def score(self) -> float:
        return self.stop_score + self.dist_score

    @property
    def dist(self) -> float:
        return self._dist

    @dist.setter
    def dist(self, dist: float) -> None:
        self._dist = dist
        if dist == float("inf"):
            self._dist_score = dist
            return
        # TODO: Add log and stuff
        self._dist_score = dist

    @property
    def dist_score(self) -> float:
        return self._dist_score

    def distance_to(self, other: DijkstraNode) -> float:
        if isinstance(other, (StartNode, EndNode)):
            return 0
        return distance(tuple(self.loc), tuple(other.loc)).m


class StartNode(DijkstraNode):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, -1, None)
        self.dist = 0

    def distance_to(self, other: DijkstraNode) -> float:
        return 0


class EndNode(DijkstraNode):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, -1, None)
        self.dist = float("inf")

    def distance_to(self, other: DijkstraNode) -> float:
        return 0


StopPosition = NamedTuple("StopPosition", [("idx", int), ("stop", str),
                                           ("lat", float), ("lon", float),
                                           ])


class Nodes:
    def __init__(self) -> None:
        self.nodes: dict[str: dict[int: DijkstraNode]] = {}

    def add(self, node: DijkstraNode) -> None:
        self.nodes.setdefault(node.stop, {}).update({node.idx: node})

    def _create(self, values: StopPosition) -> DijkstraNode:
        loc = Location(values.lat, values.lon)
        node = DijkstraNode(values.stop, values.idx, loc)
        self.add(node)
        return node

    def get_or_create(self, values: StopPosition) -> DijkstraNode:
        stop = values.stop
        idx = values.idx
        node = self.nodes.get(stop, {}).get(idx)
        if not node:
            node = self._create(values)
        return node

    def get_min_node(self) -> DijkstraNode:
        nodes = [node
                 for stop_nodes in self.nodes.values()
                 for node in stop_nodes.values()
                 if not node.visited]
        return min(nodes, key=attrgetter("score"))
