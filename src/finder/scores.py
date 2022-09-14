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
    dijkstra.calculate_node_scores()
    logger.info(f"Done. Took {time() - t:.2f}s")
    route = dijkstra.get_shortest_route()
    if Config.display_route in [1, 3]:
        display_route(route)
    return route


class Dijkstra:
    def __init__(self, stops: StopNames, df: DF) -> None:
        self.df = df
        self.stops = stops
        self.last_node = StartNode(self.stops[-1])
        self.nodes: Nodes = Nodes()

    def _get_df_with_stop(self, stop: str = "", stop_index: int = None) -> DF:
        if stop_index is not None:
            stop = self.stops[stop_index]
        return self.df[self.df["stop"] == stop]

    def calculate_node_scores(self) -> None:
        for i, stop in reversed(list(enumerate(self.stops))):
            self._calculate_node_score_for_stop(stop)

    def _calculate_node_score_for_stop(self, stop: str) -> None:
        df = self._get_df_with_stop(stop)
        for entry in df.itertuples(False, "StopPosition"):
            entry: StopPosition
            node = self.nodes.get_or_create(entry)
            if node.parent:
                continue
            node.parent = self._get_node_parent(node)
        if df.empty:
            self.nodes.get_or_create_missing(stop)

    def _get_node_parent(self, node: DijkstraNode) -> DijkstraNode:
        if node.stop == self.stops[-1]:
            return self.last_node

        stop = self.stops[self.stops.index(node.stop) + 1]
        neighbors = self._get_df_with_stop(stop)
        return self._get_closest_neighbor(node, stop, neighbors)

    def _get_closest_neighbor(self, node: DijkstraNode, stop: StopName,
                              neighbors: DF) -> DijkstraNode:
        def get_node_score() -> float:
            # Check rough distance first, to improve performance.
            dist = get_rough_distance(node.loc.lat, node.loc.lon,
                                      neighbor.lat, neighbor.lon)
            max_dist = Config.max_stop_distance * 1000
            if dist * 2 > max_dist:
                return float("inf")

            neighbor_node = self.nodes.get_or_create(neighbor)
            dist = node.distance_to(neighbor_node)
            if dist > max_dist:
                return float("inf")

            return node.score_to(neighbor_node, dist)

        min_node = None
        min_score = float("inf")

        for neighbor in neighbors.itertuples(False, "StopPosition"):
            neighbor: StopPosition

            score = get_node_score()
            if score == float("inf"):
                continue

            if not min_node or min_score > score:
                min_node = self.nodes.get_or_create(neighbor)
                min_score = score

        if min_node:
            return min_node
        return self.nodes.get_or_create_missing(stop, node)

    def get_shortest_route(self) -> list[DijkstraNode]:
        node: DijkstraNode = self.nodes.get_min(self.stops[0])
        route: list[DijkstraNode] = []

        while node != self.last_node:
            route.append(node)
            node = node.parent

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
    def __init__(self, stop: StopName, ref_node: DijkstraNode | None) -> None:
        super().__init__(stop, -1, None, 0)
        self.dist = float("inf")
        self.ref_node = ref_node

    @property
    def score(self) -> int:
        return 10

    def distance_to(self, other: DijkstraNode) -> float:
        if isinstance(other, (StartNode, EndNode)):
            return super().distance_to(other)
        # TODO NOW:
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

    def get_or_create_missing(self, stop: StopName,
                              ref_node: DijkstraNode | None = None) -> MissingNode:
        node = MissingNode(stop, ref_node)
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

    def get_min(self, stop: str) -> DijkstraNode:
        nodes = self.nodes[stop].values()
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
