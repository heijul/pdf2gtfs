from __future__ import annotations

import logging
import re
import webbrowser
from operator import attrgetter
from statistics import mean, StatisticsError
from time import time
from typing import NamedTuple, TypeAlias

import pandas as pd
import folium
from geopy.distance import distance

from config import Config
from finder.location import Location
from finder.types import StopName, StopNames
from utils import get_edit_distance, replace_abbreviations


logger = logging.getLogger(__name__)
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
    logger.info("Starting location detection using dijkstra...")
    df = split_df(stops, full_df)
    t = time()
    dijkstra = Dijkstra(stops, df.copy())
    dijkstra.calculate_shortest_route_scores()
    route = dijkstra.get_shortest_route()
    logger.info(f"Done. Took {time() - t:4f}s")
    display_route(route)


class Dijkstra:
    def __init__(self, stops: StopNames, df: DF) -> None:
        self.df = df
        self.stops = stops
        self.start_node = StartNode(self.stops[-1])
        self.end_node = EndNode(self.stops[0])
        self.nodes: Nodes = Nodes()

    def _update_neighbors(self, node: DijkstraNode, neighbors: DF) -> None:
        for neighbor in neighbors.itertuples(False, "StopPosition"):
            neighbor: StopPosition
            # TODO: Check rough distance before creating node.
            # TODO: Use distance score instead of actual distance?.
            neighbor_node = self.nodes.get_or_create(neighbor)
            dist = node.distance_to(neighbor_node)
            if dist >= neighbor_node.dist:
                continue
            # TODO: Need to filter nodes with too much distance
            neighbor_node.parent = node
            neighbor_node.dist = dist

    def calculate_shortest_route_scores(self) -> None:
        def get_current() -> DijkstraNode:
            min_node = self.nodes.get_min_node()
            if min_node:
                return min_node
            raise Exception("AAA")
            # TODO: Return dummynode with some fix score in case of missing node

        def current_stop_index() -> int:
            """ Returns the index of the current nodes' stop. """
            if isinstance(current, StartNode):
                return len(self.stops)
            return self.stops.index(current.stop)

        def get_neighbors() -> DF:
            return self.df[self.df["stop"] == self.stops[stop_index - 1]]

        current: DijkstraNode = self.start_node
        while True:
            stop_index = current_stop_index()
            # Check: if we are stopping too early.
            if stop_index == 0:
                self.end_node.parent = current
                break

            neighbors = get_neighbors()
            if neighbors.empty:
                # TODO: Probably need to increase score of node in some way.
                ...
            self._update_neighbors(current, neighbors)

            # Done with current node.
            current.visited = True
            current = get_current()

    def get_shortest_route(self) -> list[DijkstraNode]:
        current: DijkstraNode = self.end_node.parent
        route: list[DijkstraNode] = []
        while current != self.start_node:
            route.append(current)
            current = current.parent
        return route


class DijkstraNode:
    def __init__(self, stop: str, idx: int,
                 loc: Location | None, score: float) -> None:
        self.stop = stop
        self.idx = idx
        self.loc = loc
        self.stop_score = score
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
        super().__init__(stop, -1, None, 0)
        self.dist = 0

    def distance_to(self, other: DijkstraNode) -> float:
        return 0


class EndNode(DijkstraNode):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, -1, None, 0)
        self.dist = float("inf")

    def distance_to(self, other: DijkstraNode) -> float:
        return 0


StopPosition = NamedTuple("StopPosition", [("idx", int), ("stop", str),
                                           ("lat", float), ("lon", float),
                                           ("node_score", float),
                                           ])


class Nodes:
    def __init__(self) -> None:
        self.nodes: dict[str: dict[int: DijkstraNode]] = {}

    def add(self, node: DijkstraNode) -> None:
        self.nodes.setdefault(node.stop, {}).update({node.idx: node})

    def _create(self, values: StopPosition) -> DijkstraNode:
        loc = Location(values.lat, values.lon)
        node = DijkstraNode(values.stop, values.idx, loc, values.node_score)
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


def display_route(nodes: list[DijkstraNode]) -> None:
    def get_map_location() -> tuple[float, float]:
        try:
            return (mean([n.loc.lat for n in nodes]),
                    mean([n.loc.lon for n in nodes]))
        except StatisticsError:
            return 0, 0

    # FEATURE: Add cluster/nodes to Config.
    # FEATURE: Add info about missing nodes.
    # TODO: Adjust zoom/location depending on lat-/lon-minimum
    location = get_map_location()
    if location == (0, 0):
        logger.warning("Nothing to display, route is empty.")
        return
    m = folium.Map(location=location)
    for i, node in enumerate(nodes):
        loc = [node.loc.lat, node.loc.lon]
        folium.Marker(loc, popup=f"{node.stop}\n{node.score}\n{loc}"
                      ).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))
