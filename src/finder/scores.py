from __future__ import annotations

import logging
import re
import webbrowser
from math import cos, log
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

    dfs = []
    for stop in stops:
        df = _filter_df_by_stop(stop, full_df)
        if df.empty:
            continue
        df.loc[:, "name_score"] = df["names"].apply(name_distance)
        df.loc[:, "stop"] = stop
        df.loc[:, "idx"] = df.index
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def find_shortest_route(stops: StopNames, full_df: DF) -> list[DijkstraNode]:
    logger.info("Splitting DataFrame based on stop names...")
    t = time()
    df = split_df(stops, full_df)
    logger.info(f"Done. Took {time() - t:.2f}s")
    logger.info("Starting location detection using dijkstra...")
    t = time()
    dijkstra = Dijkstra(stops, df.copy())
    dijkstra.calculate_shortest_route_scores2()
    logger.info(f"Done. Took {time() - t:.2f}s")
    route = dijkstra.get_shortest_route()
    if Config.display_route in [1, 3]:
        display_route(route)
    return route


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
            score = neighbor_node.score_to(node, dist)
            if score >= neighbor_node.score:
                continue

            logger.info(f"Found better node with score "
                        f"{score} and dist {dist:.2f}.")
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

    def get_df_with_stop(self, stop: str = "", stop_index: int = None) -> DF:
        if stop_index is not None:
            stop = self.stops[stop_index]
        return self.df[self.df["stop"] == stop]

    def calculate_shortest_route_scores2(self) -> None:
        for i, stop in reversed(list(enumerate(self.stops))):
            self.calculate_shortest_route_scores3(stop)

    def calculate_shortest_route_scores3(self, stop: str) -> None:
        df = self.get_df_with_stop(stop)
        for entry in df.itertuples(False, "StopPosition"):
            entry: StopPosition
            node = self.nodes.get_or_create(entry)
            if stop == self.stops[-1]:
                node.parent = self.start_node
                continue
            if not node.parent:
                self.calculate_shortest_route_from_node(node)
            print(node.score)
            if node.score < 20:
                break

    def calculate_shortest_route_from_node(self, node: DijkstraNode) -> None:
        if node.parent:
            return
        stop = self.stops[self.stops.index(node.stop) + 1]
        neighbors = self.get_df_with_stop(stop)
        node.parent = self.get_closest_neighbor(node, stop, neighbors)

    def get_closest_neighbor(self, node: DijkstraNode, stop: StopName,
                             neighbors: DF) -> DijkstraNode:
        min_node = None
        min_score = float("inf")
        for neighbor in neighbors.itertuples(False, "StopPosition"):
            neighbor: StopPosition
            rough_dist = get_rough_distance(node.loc.lat, node.loc.lon,
                                            neighbor.lat, neighbor.lon)
            if rough_dist * 2 > Config.max_stop_distance * 1000:
                continue
            neighbor_node = self.nodes.get_or_create(neighbor)
            dist = node.distance_to(neighbor_node)
            if dist > Config.max_stop_distance * 1000:
                continue
            score = node.score_to(neighbor_node, dist)
            if not min_node or min_score > score:
                min_node = neighbor_node
                min_score = score
        return min_node if min_node else MissingNode(stop)

    def get_shortest_route(self) -> list[DijkstraNode]:
        current: DijkstraNode = self.nodes.get_min(self.stops[0])
        route: list[DijkstraNode] = []
        while current != self.start_node:
            route.append(current)
            current = current.parent
        return route


def get_rough_distance(lat1, lon1, lat2, lon2) -> float:
    lat_dist = abs(lat1 - lat2) * 111
    lon_dist = abs(abs(lon1 - lon2) * cos(mean((lat1, lat2))) * 111)
    return 1000 * (lat_dist + lon_dist)


def _get_dist_score(dist: float) -> float:
    if dist == -1:
        return 0
    try:
        return log(dist, 4) * 0.3 * log(dist, 20)
    except ValueError:
        # Two different stops should not use the same location.
        return float("inf")


class DijkstraNode:
    def __init__(self, stop: str, idx: int,
                 loc: Location | None, score: float) -> None:
        self.stop = stop
        self.idx = idx
        self.loc = loc
        self._parent = None
        self._score = 1000
        self.stop_score = score
        self.dist = float("inf")
        self.visited = False
        self.done = False

    @property
    def parent(self) -> DijkstraNode:
        return self._parent

    @parent.setter
    def parent(self, parent) -> None:
        self._parent = parent
        self._score = self.calculate_score(parent)

    @property
    def score(self) -> int:
        return self._score

    def calculate_score(self, parent: DijkstraNode, dist_score: float = None) -> int:
        if dist_score is None:
            return self.score_to(parent)
        score = self.stop_score + dist_score + parent.score
        try:
            return int(score)
        except (ValueError, OverflowError):
            return 1000

    @property
    def dist(self) -> float:
        return self._dist

    @dist.setter
    def dist(self, dist: float) -> None:
        self._dist = dist
        self._dist_score = _get_dist_score(dist)

    @property
    def dist_score(self) -> float:
        return self._dist_score

    def distance_to(self, other: DijkstraNode) -> float:
        if isinstance(other, (StartNode, EndNode)):
            return -1
        if isinstance(other, MissingNode):
            return other.distance_to(self)
        return distance(tuple(self.loc), tuple(other.loc)).m

    def score_to(self, other: DijkstraNode, dist: float = None) -> float:
        if dist is None:
            dist = self.distance_to(other)
        return self.calculate_score(other, _get_dist_score(dist))


class StartNode(DijkstraNode):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, -1, None, 0)
        self.dist = 0

    @property
    def parent(self) -> DijkstraNode:
        return self

    @property
    def score(self) -> int:
        return 0

    def distance_to(self, other: DijkstraNode) -> float:
        return 1


class EndNode(DijkstraNode):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, -1, None, 0)
        self.dist = float("inf")

    @property
    def score(self) -> int:
        return 0

    def distance_to(self, other: DijkstraNode) -> float:
        return 1


class MissingNode(DijkstraNode):
    def __init__(self, stop: StopName) -> None:
        super().__init__(stop, -1, None, 0)
        self.dist = float("inf")

    @property
    def score(self) -> int:
        return 10

    def distance_to(self, other: DijkstraNode) -> float:
        if isinstance(other, (StartNode, EndNode)):
            return super().distance_to(other)
        return 1000


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

    def create_missing(self, stop: StopName) -> MissingNode:
        ...

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

    def get_min(self, stop: str) -> DijkstraNode:
        nodes = self.nodes[stop]
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
