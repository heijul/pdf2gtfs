from __future__ import annotations

import heapq
import logging
import webbrowser
from collections import abc
from functools import partial
from math import cos, log, pi, sqrt
from statistics import mean, StatisticsError
from time import time
from typing import Callable, Generator, NamedTuple, TYPE_CHECKING, TypeAlias

import numpy as np
import pandas as pd
import folium

from config import Config
from datastructures.gtfs_output.stop_times import Time
from finder.location import Location


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

logger = logging.getLogger(__name__)

Heap: TypeAlias = list["Node"]
DF: TypeAlias = pd.DataFrame
StopPosition = NamedTuple("StopPosition",
                          [("idx", int), ("stop", str), ("names", str),
                           ("lat", float), ("lon", float),
                           ("node_score", float), ("name_score", float)])

MISSING_NODE_SCORE = 100


class Distance:
    def __init__(self, *, m: float = None, km: float = None):
        self.distance = abs(m if m is not None else km * 1000)

    @property
    def m(self) -> float:
        return self.distance

    @property
    def km(self) -> float:
        return self.distance / 1000

    def __rmul__(self, other: object) -> Distance:
        if isinstance(other, (float, int)):
            return Distance(m=self.m * other)
        if isinstance(other, Distance):
            return Distance(m=self.m * other.m)
        raise TypeError(f"Can only multiply Distances with Distances or "
                        f"Distances with int/float, not '{type(object)}'.")

    def __mul__(self, other: object) -> Distance:
        return self.__rmul__(other)

    def __add__(self, other: object):
        if isinstance(other, Distance):
            return Distance(m=self.m + other.m)
        raise TypeError(f"Can only add Distances to Distances, "
                        f"not '{type(object)}'.")

    def __truediv__(self, other: object) -> Distance:
        if isinstance(other, Distance):
            return Distance(m=self.m / other.m)
        raise TypeError(f"Can only divide Distances by Distances, "
                        f"not '{type(object)}'.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Distance):
            return False
        return self.distance == other.distance

    def __lt__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            raise TypeError(
                f"Can only compare Distance to Distance, not {type(object)}.")
        return self.distance < other.distance

    def __le__(self, other: Distance) -> bool:
        return self == other or self < other

    def __gt__(self, other: Distance) -> bool:
        return not self <= other

    def __ge__(self, other: Distance) -> bool:
        return not self < other

    def __repr__(self) -> str:
        return f"Dist({self.m}m)"


DISTANCE_PER_LAT_DEG = Distance(km=111.32)


def get_distance_per_lon_deg(lat: float) -> Distance:
    lat_in_rad = pi * lat / 180
    return DISTANCE_PER_LAT_DEG * abs(cos(lat_in_rad))


class Stop:
    speed_in_km_h: float = None
    stops: Stops = None

    def __init__(self, stop_id: str, name: str, next_: Stop = None) -> None:
        self.stop_id = stop_id
        self.name = name
        self._next = next_
        self._avg_time_to_next = None
        self._max_dist_to_next = None
        if Stop.speed_in_km_h is None:
            Stop.set_speed()

    @staticmethod
    def set_speed() -> None:
        Stop.speed_in_km_h = Config.average_speed

    @property
    def next(self) -> Stop | None:
        return self._next

    @next.setter
    def next(self, value: Stop) -> None:
        self._next = value

    @property
    def avg_time_to_next_in_h(self) -> float:
        def _calculate_avg_time_to_next() -> Time:
            return Stop.stops.get_avg_time_between(self, self.next)

        if self._avg_time_to_next is None:
            self._avg_time_to_next = _calculate_avg_time_to_next().to_float_hours()
        return self._avg_time_to_next

    @property
    def max_dist_to_next(self) -> Distance:
        if not self._max_dist_to_next:
            if not self.next:
                dist = 0
            else:
                dist = self.avg_time_to_next_in_h * Stop.speed_in_km_h
            self._max_dist_to_next = Distance(km=dist)
        return self._max_dist_to_next

    def __hash__(self) -> int:
        return hash(self.stop_id)

    def __repr__(self) -> str:
        return f"Stop({self.stop_id}, '{self.name}')"


class Stops(abc.Iterator):
    def __init__(self, handler: GTFSHandler, stop_names: list[tuple[str, str]]) -> None:
        self.handler = handler
        Stop.stops = self
        self.first, self.last = self._create_stops(stop_names)

    @property
    def stops(self) -> list[Stop]:
        stops = []
        current = self.first
        while current is not None:
            stops.append(current)
            current = current.next

        return stops

    @staticmethod
    def _create_stops(stop_names: list[tuple[str, str]]) -> tuple[Stop, Stop]:
        last = None
        stop = None

        for idx, stop_name in reversed(list(stop_names)):
            stop = Stop(idx, stop_name, stop)
            if not last:
                last = stop

        return stop, last

    def get_avg_time_between(self, stop1: Stop, stop2: Stop) -> Time:
        return self.handler.get_avg_time_between_stops(stop1.stop_id, stop2.stop_id)

    def __next__(self) -> Generator[Stop]:
        current = self.first
        while current is not None:
            yield current
        raise StopIteration


class Score:
    def __init__(self, node_score: float = None, name_score: float = None,
                 dist_score: float = None) -> None:
        self.node_score = self._get_score(node_score)
        self.name_score = self._get_score(name_score)
        self.dist_score = self._get_score(dist_score)

    @property
    def score(self) -> float:
        return sum(self.scores)

    @property
    def scores(self) -> tuple[float, float, float]:
        return self.node_score, self.name_score, self.dist_score

    @property
    def invalid(self) -> bool:
        def invalid_score(score: float) -> bool:
            return score is None or score == float("inf")

        return any(map(invalid_score, self.scores))

    def set_dist_score_from_dist(self, node: Node, dist: Distance) -> None:
        diff_to_expected = abs(node.stop.max_dist_to_next.m - dist.m)
        self.dist_score = self.get_dist_score_from_dist(diff_to_expected)

    @staticmethod
    def get_dist_score_from_dist(dist: float) -> float:
        try:
            return log(dist, 4) * 0.3 * log(dist, 20)
        except ValueError:
            # Two different stops should not use the same location.
            return float("inf")

    @staticmethod
    def _get_score(score: float) -> float:
        return float("inf") if score is None or score < 0 else score

    @staticmethod
    def from_score(score: Score) -> Score:
        return Score(*score.scores)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Score) and self.score == other.score

    def __lt__(self, other: Score) -> bool:
        if not isinstance(other, Score):
            raise TypeError(
                f"Can only compare Score to Score, not {type(object)}.")
        if other.invalid:
            return True
        if self.invalid:
            return False
        return self.score < other.score

    def __le__(self, other: Score) -> bool:
        return self == other or self < other

    def __gt__(self, other: Score) -> bool:
        return not self <= other

    def __ge__(self, other: Score) -> bool:
        return not self < other

    def __repr__(self) -> str:
        return (f"Score(total: {self.score:.2f}, node: {self.node_score:.2f},"
                f" name: {self.name_score:.2f}, dist: {self.dist_score:.2f})")


class StartScore(Score):
    @staticmethod
    def from_score(score: Score) -> Score:
        s = Score.from_score(score)
        s.dist_score = 0
        return s

    def set_dist_score_from_dist(self, node: Node, dist: Distance) -> None:
        raise NotImplementedError("Can not set dist score for start nodes.")


class Node:
    nodes: Nodes = None

    def __init__(self, stop: Stop, index: int, names: str,
                 loc: Location, score: Score) -> None:
        self.stop = stop
        self.index = index
        self.names = names
        self.loc = loc
        self.parent = None
        self.has_children = False
        self.score: Score = score
        self.has_neighbors = False
        self.visited = False
        if Node.nodes is None:
            raise Exception("Nodes needs to be set, before creating a node.")

    def get_neighbors(self) -> Generator[Node, None, None]:
        next_stop = self.stop.next
        df = Node.nodes.get_df_close_to_next(self)
        if -1 in df.index.values:
            return Node.nodes.missing_node_factory(df, next_stop)
        return Node.nodes.node_factory(df, next_stop)

    def dist_exact(self, node: Node) -> Distance:
        lat_mid = mean((self.loc.lat, node.loc.lat))
        distance_per_lon_deg = get_distance_per_lon_deg(lat_mid)
        lat_dist = abs(self.loc.lat - node.loc.lat) * DISTANCE_PER_LAT_DEG
        lon_dist = abs(self.loc.lon - node.loc.lon) * distance_per_lon_deg
        dist = sqrt(lat_dist.m ** 2 + lon_dist.m ** 2)
        return Distance(m=dist)

    def _is_close(self, lat: float, lon: float, max_dist: Distance) -> bool:
        """ Checks if the given lat/lon is within a square of
        size 2 * max_dist. Faster than calculating the exact distance. """
        # TODO: Maybe use self.loc.lat instead of lat_mid
        lat_mid = self.loc.lat + lat
        lat_diff = abs(self.loc.lat - lat)
        lon_diff = abs(self.loc.lon - lon)
        return (lat_diff * DISTANCE_PER_LAT_DEG <= max_dist and
                lon_diff * get_distance_per_lon_deg(lat_mid) <= max_dist)

    def is_close(self, array: np.ndarray, max_dist: float = None) -> bool:
        if array[0] == 0 and array[1] == 0:
            return True
        if max_dist is None:
            max_dist = self.stop.max_dist_to_next
        return self._is_close(array[0], array[1], max_dist)

    def score_to(self, node: Node) -> Score:
        score = Score.from_score(node.score)
        score.set_dist_score_from_dist(self, self.dist_exact(node))
        return score

    def update_neighbor(self, node: Node) -> None:
        """ Set the nodes' parent to self, if self has a better score. """
        score = self.score_to(node)

        no_parent = node.parent is None
        missing_parent = (not no_parent and
                          isinstance(node.parent, MissingNode))
        missing_self = isinstance(self, MissingNode)
        better_score = score < node.score
        is_better = no_parent or (missing_parent and not missing_self)
        # Compare score only if both or neither are MissingNode.
        is_better |= missing_parent + missing_self in [0, 2] and better_score
        if not is_better:
            return

        self.nodes.update_parent(self, node, score)

    def construct_route(self) -> list[Node]:
        if not self.parent:
            return [self]
        return self.parent.construct_route() + [self]

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Node) and
                self.stop == other.stop and self.index == other.index and
                self.loc == other.loc and self.score == other.score)

    def __lt__(self, other: Node) -> bool:
        if not isinstance(other, Node):
            raise TypeError(
                f"Can only compare Node to Node, not {type(object)}.")
        return self.score < other.score

    def __le__(self, other: Node) -> bool:
        return self == other or self < other

    def __gt__(self, other: Node):
        return not self <= other

    def __ge__(self, other: Node) -> bool:
        return not self < other

    def __repr__(self) -> str:
        base = (f"Node('{self.stop.name}', score: {self.score.score:.2f}, "
                f"loc: [{self.loc.lat}, {self.loc.lon}]")
        if self.parent:
            dist_to_parent = self.dist_exact(self.parent)
            base += f", to_parent: {dist_to_parent.m:.2f}"
        return base + ")"


class MissingNode(Node):
    def __init__(self, stop: Stop, index: int, names: str, loc: Location
                 ) -> None:
        score = Score(MISSING_NODE_SCORE, 0, 0)
        super().__init__(stop, index, names, loc, score)

    def dist_exact(self, node: Node) -> Distance:
        if self.parent:
            return self.parent.dist_exact(node)
        raise NotImplementedError(
            "Can't calculate distance to missing node without parent.")

    def is_close(self, array: np.ndarray, max_dist: float = None) -> bool:
        if not self.parent:
            # We don't know where the missing node is,
            # so we have to assume it is close.
            return True

        max_dist = (self.stop.max_dist_to_next +
                    self.parent.stop.max_dist_to_next)
        return self.parent.is_close(array, max_dist)

    def score_to(self, node: Node) -> Score:
        if self.parent and node.parent:
            return self.parent.score_to(node)

        score = Score.from_score(self.score)
        score.dist_score = MISSING_NODE_SCORE
        return score

    def __repr__(self) -> str:
        return "Missing" + super().__repr__()


class Nodes:
    def __init__(self, df: DF) -> None:
        self.df = df
        self.dfs: dict[Stop: DF] = {}
        self.node_map: dict[tuple[Stop, int]: Node] = {}
        self.node_heap: Heap[Node] = []
        self.next_missing_node_idx = -1
        Node.nodes = self

    def _add(self, node: Node) -> None:
        self.node_map[(node.stop, node.index)] = node
        heapq.heappush(self.node_heap, node)

    def _create_node(self, stop: Stop, values: StopPosition) -> Node:
        loc = Location(values.lat, values.lon)
        score = Score(values.node_score, values.name_score)
        node = Node(stop, values.idx, values.names, loc, score)
        self._add(node)
        return node

    def _create_missing_node(self, stop: Stop, values: StopPosition
                             ) -> MissingNode:
        loc = Location(values.lat, values.lon)
        node = MissingNode(stop, values.idx, values.names, loc)
        self._add(node)
        return node

    def get_or_create(self, stop: Stop, values: StopPosition) -> Node:
        node = self.node_map.get((stop, values.idx))
        if node is None:
            node = self._create_node(stop, values)
        return node

    def create_missing(self, stop: Stop, node_score: float) -> MissingNode:
        values = StopPosition(self.next_missing_node_idx, stop.name,
                              stop.name, 0, 0, node_score, 0)
        node = self._create_missing_node(stop, values)
        self.next_missing_node_idx -= 1
        return node

    def get_or_create_missing(self, stop: Stop, values: StopPosition,
                              ) -> MissingNode:
        node = self.node_map.get((stop, values.idx))
        if node is None:
            node = self._create_missing_node(stop, values)
        return node

    def filter_df_by_stop(self, stop: Stop) -> DF:
        df = self.df[self.df["stop_id"] == stop.stop_id]
        if df.empty:
            data = {"idx": self.next_missing_node_idx, "stop_id": stop.stop_id,
                    "names": stop.name, "lat": 0, "lon": 0,
                    "node_score": MISSING_NODE_SCORE, "name_score": 0}
            self.next_missing_node_idx -= 1
            df = pd.DataFrame(data, index=pd.Index([-1]), columns=df.columns)
        self.dfs[stop] = df
        return df

    def get_df_close_to_next(self, node: Node) -> DF:
        next_stop = node.stop.next
        df = self.dfs.setdefault(next_stop, self.filter_df_by_stop(next_stop))
        return df[df[["lat", "lon"]].apply(node.is_close, raw=True, axis=1)]

    def node_factory(self, df: DF, stop: Stop) -> Generator[Node, None, None]:
        create_node_partial: Callable[[StopPosition], Node]
        create_node_partial = partial(self.get_or_create, stop)
        stop_positions = df.itertuples(False, "StopPosition")
        return (create_node_partial(pos) for pos in stop_positions)

    def missing_node_factory(self, df: DF, stop: Stop
                             ) -> Generator[Node, None, None]:
        create_missing_partial: Callable[[StopPosition], Node]
        create_missing_partial = partial(self.get_or_create_missing, stop)
        stop_positions = df.itertuples(False, "StopPosition")
        return (create_missing_partial(pos) for pos in stop_positions)

    def get_min(self) -> Node:
        node = heapq.heappop(self.node_heap)
        # Do not return nodes that are already visited.
        if node.visited:
            return self.get_min()
        return node

    def update_parent(self, parent: Node, node: Node, score: Score) -> None:
        try:
            self.node_heap.remove(node)
        except ValueError:
            pass

        node.parent = parent
        node.score = score
        parent.has_children = True
        if False and isinstance(node, MissingNode):
            self.duplicate_missing_node(node)
        heapq.heappush(self.node_heap, node)

    def duplicate_missing_node(self, node: MissingNode) -> None:
        duplicate = MissingNode(node.stop, self.next_missing_node_idx,
                                node.names, node.loc)
        self._add(duplicate)
        self.next_missing_node_idx -= 1

    def __repr__(self) -> str:
        num_stops = len(set([nodes for nodes, _ in self.node_map]))
        return (f"Nodes(# stops: {num_stops}, "
                f"# nodes: {len(self.node_map)}, "
                f"# unvisited nodes: {len(self.node_heap)})")


def update_missing_locations(route) -> None:
    def get_first_node() -> tuple[int, Node | None]:
        for i, n in enumerate(route):
            if isinstance(n, MissingNode):
                continue
            return i + 1, n
        return 0, None

    start_id, prev = get_first_node()
    if prev is None:
        return

    missing_nodes = []
    for node in route[start_id:]:
        if isinstance(node, MissingNode):
            missing_nodes.append(node)
            continue
        if not missing_nodes:
            prev = node
            continue

        delta = Location((node.loc.lat - prev.loc.lat) / (len(missing_nodes) + 1),
                         (node.loc.lon - prev.loc.lon) / (len(missing_nodes) + 1))
        loc = prev.loc + delta

        for m in missing_nodes:
            m.loc = loc
            loc += delta
        missing_nodes = []
        prev = node


class RouteFinder:
    def __init__(self, handler: GTFSHandler, stop_names: list[tuple[str, str]], df: DF) -> None:
        self.handler = handler
        self.stops = Stops(handler, stop_names)
        self.nodes = Nodes(df)

    def find_dijkstra(self) -> list[Node]:
        self._initialize_start()
        while True:
            node: Node = self.nodes.get_min()
            if node.stop == self.stops.last:
                break
            for neighbor in node.get_neighbors():
                node.update_neighbor(neighbor)
                if isinstance(neighbor, MissingNode):
                    continue
            if not node.has_children:
                neighbor = self.nodes.create_missing(node.stop.next,
                                                     node.score.score)
                node.update_neighbor(neighbor)
            node.visited = True

        route = node.construct_route()
        return route

    def _initialize_start(self) -> None:
        stop = self.stops.first
        df = self.nodes.filter_df_by_stop(stop)
        for values in df.itertuples(False, "StopPosition"):
            values: StopPosition
            node = self.nodes.get_or_create(stop, values)
            node.score = StartScore.from_score(node.score)


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
        loc = [node.loc.lat, node.loc.lon]
        if loc[0] == 0 and loc[1] == 0:
            continue
        if isinstance(node, MissingNode):
            icon = folium.Icon(color="red", icon="remove-circle")
        else:
            icon = folium.Icon(color="green", icon="map-marker")
        popup = (f"Stop:  '{node.stop.name}'<br>"
                 f"Score: {node.score.score:.2f}<br>"
                 f"Lat:   {loc[0]:>7.4f}<br>"
                 f"Lon:   {loc[1]:>7.4f}")
        folium.Marker(loc, popup=popup, icon=icon).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


def find_shortest_route(handler: GTFSHandler,
                        stop_names: list[tuple[str, str]], df: DF
                        ) -> dict[str: Location]:
    logger.info("Starting location detection...")
    t = time()
    route_finder = RouteFinder(handler, stop_names, df.copy())
    route = route_finder.find_dijkstra()
    update_missing_locations(route)
    logger.info(f"Done. Took {time() - t:.2f}s")
    display_route(route)
    return {node.stop.stop_id: node.loc for node in route}
