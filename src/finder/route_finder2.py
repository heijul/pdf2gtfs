from __future__ import annotations

import heapq
import logging
from collections import abc
from functools import partial
from math import cos, log, pi, sqrt
from statistics import mean
from typing import Callable, Generator, TypeAlias

import pandas as pd

from config import Config
from datastructures.gtfs_output.handler import GTFSHandler
from datastructures.gtfs_output.stop_times import Time
from finder.location import Location


logger = logging.getLogger(__name__)

Heap: TypeAlias = list["Node"]
DF: TypeAlias = pd.DataFrame
S: TypeAlias = pd.Series


class Distance:
    def __init__(self, *, m: float = -1, km: float = -1):
        assert m >= 0 or km >= 0
        self.distance = m if m >= 0 else km * 1000

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


DISTANCE_PER_LAT_DEG = Distance(km=111.32)


def get_distance_per_lon_deg(lat: float) -> Distance:
    lat_in_rad = pi * lat / 180
    return DISTANCE_PER_LAT_DEG * cos(lat_in_rad)


class Stop:
    speed_in_km_h: float = None
    stops: Stops = None

    def __init__(self, idx: int, name: str) -> None:
        self.idx = idx
        self.name = name
        self._next = None
        self._avg_time_to_next = None
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
            self._avg_time_to_next = _calculate_avg_time_to_next().to_float()
        return self._avg_time_to_next

    @property
    def max_dist_to_next(self) -> Distance:
        if not self.next:
            return Distance(m=0)
        return Distance(km=self.avg_time_to_next_in_h * Stop.speed_in_km_h)

    def __hash__(self) -> int:
        return hash(self.idx)


class Stops(abc.Iterator):
    def __init__(self, handler: GTFSHandler, stop_names: list[str]) -> None:
        self.handler = handler
        Stop.stops = self
        self.first: Stop = self._create_stops(stop_names)

    @staticmethod
    def _create_stops(stop_names: list[str]) -> Stop:
        next_ = None
        for idx, stop_name in reversed(list(enumerate(stop_names))):
            stop = Stop(idx, stop_name)
            stop.next = next_
            next_ = stop
        return next_

    def get_avg_time_between(self, stop1: Stop, stop2: Stop) -> Time:
        return self.handler.get_avg_time_between_stops(stop1.idx, stop2.idx)

    @property
    def stops(self) -> list[Stop]:
        stops = []
        current = self.first
        while current is not None:
            stops.append(current)
            current = current.next

        return stops

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
        dist_to_expected = abs(node.stop.max_dist_to_next.m - dist.m)
        self.dist_score = self.get_dist_score_from_dist(dist_to_expected)

    @staticmethod
    def get_dist_score_from_dist(dist: float) -> float:
        if dist == -1:
            return 0
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


class Node:
    nodes: Nodes = None

    def __init__(self, stop: Stop, index: int, names: str, loc: Location
                 ) -> None:
        self.stop = stop
        self.index = index
        self.names = names
        self.loc = loc
        self.score: Score = Score()
        if Node.nodes is None:
            raise Exception("Nodes needs to be set, before creating a node.")

    def get_neighbors(self) -> Generator[Node, None, None]:
        return Node.nodes.get_close_to_next(self)

    def dist_exact(self, node: Node) -> Distance:
        lat_mid = mean((self.loc.lat, node.loc.lat))
        distance_per_lon_deg = get_distance_per_lon_deg(lat_mid)
        lat_dist = abs(self.loc.lat - node.loc.lat) * DISTANCE_PER_LAT_DEG
        lon_dist = abs(self.loc.lon - node.loc.lon) * distance_per_lon_deg
        dist = sqrt(lat_dist.m ** 2 + lon_dist.m ** 2)
        return Distance(m=dist)

    def _is_close(self, lat, lon) -> bool:
        # TODO: Maybe use self.loc.lat instead of lat_mid
        lat_mid = self.loc.lat + lat
        lat_diff = abs(self.loc.lat - lat)
        lon_diff = abs(self.loc.lon - lon)
        max_dist = self.stop.max_dist_to_next
        return (lat_diff * DISTANCE_PER_LAT_DEG <= max_dist and
                lon_diff * get_distance_per_lon_deg(lat_mid) <= max_dist)

    def is_close(self, series: pd.Series) -> bool:
        return self._is_close(series.lat, series.lon)

    def score_to(self, node: Node) -> Score:
        score = Score.from_score(self.score)
        score.set_dist_score_from_dist(self, self.dist_exact(node))
        return score

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


class Nodes:
    def __init__(self, df: DF) -> None:
        self.df = df
        self.dfs: dict[Stop: DF] = {}
        self.node_map: dict[tuple[Stop, int]: Node] = {}
        self.node_heap: Heap[Node] = []

    def _add(self, node: Node) -> None:
        self.node_map[(node.stop, node.index)] = node
        heapq.heappush(self.node_heap, node)

    def _create_node(self, stop: Stop, values: S) -> Node:
        idx = values.idx
        loc = Location(values.lat, values.lon)
        node = Node(stop, idx, values.names, loc)
        self._add(node)
        return node

    def get_or_create(self, stop: Stop, values: S) -> Node:
        node = self.node_map.get((stop, values.idx))
        if node is None:
            node = self._create_node(stop, values)
        return node

    def _filter_df_by_stop(self, stop: Stop) -> DF:
        df = self.df.filter(self.df["stop_idx"] == stop.idx)
        self.dfs[stop] = df
        return df

    def get_close_to_next(self, node: Node) -> Generator[Node, None, None]:
        next_stop = node.stop.next
        df = self.dfs.get(next_stop)
        if not df:
            df = self._filter_df_by_stop(next_stop)

        create_node_partial: Callable[[S], Node]
        create_node_partial = partial(self.get_or_create, next_stop)
        close_df = df[df[["lat", "lon"]].apply(node.is_close, axis=1)]

        return (create_node_partial(values)
                for values in close_df.itertuples(False, "StopPosition"))

    def get_min(self) -> Node:
        return heapq.heappop(self.node_heap)
