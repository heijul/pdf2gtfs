from __future__ import annotations

import logging
import webbrowser
from math import cos, log
from statistics import mean, StatisticsError
from time import time
from typing import NamedTuple, TypeAlias

import pandas as pd
import folium

from config import Config
from finder.location import Location
from finder.types import StopName, StopNames


logger = logging.getLogger(__name__)
DF: TypeAlias = pd.DataFrame


def find_shortest_route(stops: StopNames, df: DF) -> list[Node]:
    logger.info("Starting location detection...")
    t = time()
    route_finder = RouteFinder(stops, df.copy())
    route_finder.calculate_node_scores()
    logger.info(f"Done. Took {time() - t:.2f}s")

    route = route_finder.get_shortest_route()
    display_route(route)
    return route


class RouteFinder:
    def __init__(self, stops: StopNames, df: DF) -> None:
        self.df = df
        self.stops = stops
        self.end_node = EndNode()
        self.nodes: Nodes = Nodes()

    def _get_df_with_stop(self, stop: str = "", stop_index: int = None) -> DF:
        if stop_index is not None:
            stop = self.stops[stop_index]
        return self.df[self.df["stop"] == stop]

    def calculate_node_scores(self) -> None:
        for i, stop in enumerate(self.stops):
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
            node = self.nodes.get_or_create_missing(stop)
            node.parent = self._get_node_parent(node)

    def _get_node_parent(self, node: Node) -> Node:
        # TODO: This assumes the end stopname is unique.
        if node.stop == self.stops[-1]:
            return self.end_node

        # TODO: This assumes stop names are unique.
        next_stop = self.stops[self.stops.index(node.stop) + 1]
        neighbors = self._get_df_with_stop(next_stop)
        return self._get_closest_neighbor(node, next_stop, neighbors)

    def _get_closest_neighbor(self, node: Node, stop: StopName,
                              neighbors: DF) -> Node:
        def get_node_score() -> float:
            # Check rough distance first, to improve performance.
            dist = node.get_rough_distance(neighbor.lat, neighbor.lon)
            max_dist = Config.max_stop_distance * 1000
            if dist > 2 * max_dist:
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

    def _get_route_with_start(self, node: Node) -> list[Node]:
        route: list[Node] = []

        while True:
            route.append(node)
            node = node.parent
            if node is None or node == self.end_node:
                break

        return route

    def get_shortest_route(self) -> list[Node]:
        routes: list[list[Node]] = []
        for start in self.nodes.nodes[self.stops[0]].values():
            routes.append(self._get_route_with_start(start))

        max_len = max([len(r) for r in routes])
        max_len_routes = [r for r in routes if len(r) == max_len]
        scores = [sum([node.score for node in route])
                  for route in max_len_routes]
        return max_len_routes[scores.index(min(scores))]


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


class Node:
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
    def parent(self) -> Node:
        return self._parent

    @parent.setter
    def parent(self, parent) -> None:
        self._parent = parent
        self._score = self.calculate_score(parent)

    @property
    def score(self) -> int:
        return self._score

    def calculate_score(self, parent: Node, dist_score: float = None) -> int:
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

    def distance_to(self, other: Node) -> float:
        if isinstance(other, EndNode):
            return -1
        if isinstance(other, MissingNode):
            return other.distance_to(self)
        return self.loc.distance(other.loc)

    def score_to(self, other: Node, dist: float = None) -> int:
        if dist is None:
            dist = self.distance_to(other)
        return self.calculate_score(other, _get_dist_score(dist))

    def get_rough_distance(self, lat: float, lon: float) -> float:
        return get_rough_distance(self.loc.lat, self.loc.lon, lat, lon)


class EndNode(Node):
    def __init__(self) -> None:
        super().__init__("", -1, None, 0)
        self.dist = float("inf")

    @property
    def score(self) -> int:
        return 0

    def distance_to(self, other: Node) -> float:
        return 1


class MissingNode(Node):
    def __init__(self, stop: StopName, ref_node: Node) -> None:
        super().__init__(stop, -1, None, 0)
        self.dist = float("inf")
        self.reference_node = ref_node

    def get_rough_distance(self, lat: float, lon: float) -> float:
        if not self.reference_node:
            return 1
        return self.reference_node.get_rough_distance(lat, lon) / 2

    @property
    def score(self) -> int:
        return 10

    def distance_to(self, other: Node) -> float:
        if isinstance(other, EndNode):
            return super().distance_to(other)
        # TODO: dist -> 0 if MissingNode has MissingNode as reference_node
        dist = self.reference_node.distance_to(other)
        # Assume the missing node is in the middle of its two neighbors.
        return dist / 2


StopPosition = NamedTuple("StopPosition", [("idx", int), ("stop", str),
                                           ("lat", float), ("lon", float),
                                           ("node_score", float),
                                           ])


class Nodes:
    def __init__(self) -> None:
        self.nodes: dict[str: dict[int: Node]] = {}

    def add(self, node: Node) -> None:
        self.nodes.setdefault(node.stop, {}).update({node.idx: node})

    def _create(self, values: StopPosition) -> Node:
        loc = Location(values.lat, values.lon)
        node = Node(values.stop, values.idx, loc, values.node_score)
        self.add(node)
        return node

    def _create_missing(self, stop, ref_node) -> MissingNode:
        node = MissingNode(stop, ref_node)
        self.add(node)
        return node

    def get_or_create_missing(self, stop: StopName,
                              ref_node: Node | None = None) -> MissingNode:
        node = self.nodes.get(stop, {}).get(-1)
        if not node:
            node = self._create_missing(stop, ref_node)
        return node

    def get_or_create(self, values: StopPosition) -> Node:
        stop = values.stop
        idx = values.idx
        node = self.nodes.get(stop, {}).get(idx)
        if not node:
            node = self._create(values)
        return node


def display_route(nodes: list[Node]) -> None:
    def get_map_location() -> tuple[float, float]:
        try:
            valid_nodes = [n for n in nodes if not isinstance(n, MissingNode)]
            return (mean([n.loc.lat for n in valid_nodes]),
                    mean([n.loc.lon for n in valid_nodes]))
        except StatisticsError:
            return 0, 0

    # FEATURE: Add info about missing nodes.
    # FEATURE: Adjust zoom/location depending on lat-/lon-minimum
    location = get_map_location()
    if location == (0, 0):
        logger.warning("Nothing to display, route is empty.")
        return
    m = folium.Map(location=location)
    for i, node in enumerate(nodes):
        if isinstance(node, MissingNode):
            continue
        loc = [node.loc.lat, node.loc.lon]
        folium.Marker(loc, popup=f"{node.stop}\n{node.score}\n{loc}"
                      ).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))
