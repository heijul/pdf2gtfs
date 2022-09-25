from __future__ import annotations

import heapq
import logging
import math
import webbrowser
from functools import partial
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
                           ("node_cost", float), ("name_cost", float)])

MISSING_NODE_SCORE = 100


class Distance:
    def __init__(self, *, m: float = None, km: float = None):
        self.distance = abs(m if m is not None else km * 1000)

    @property
    def distance(self) -> float:
        return self._distance

    @distance.setter
    def distance(self, value: float) -> None:
        self._distance = round(value, 0)

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

    def __sub__(self, other: object) -> Distance:
        if isinstance(other, Distance):
            return Distance(m=self.m - other.m)
        if isinstance(other, (float, int)):
            return Distance(m=self.m - other)
        raise TypeError(f"Can only substract Distances, float and int from "
                        f"Distances, not '{type(object)}'.")

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
    return DISTANCE_PER_LAT_DEG * abs(math.cos(math.radians(lat)))


class Stop:
    stops: Stops = None

    def __init__(self, idx: int, stop_id: str, name: str,
                 next_: Stop, stop_cost: int) -> None:
        self.idx = idx
        self.stop_id = stop_id
        self.name = name
        self._next = next_
        self.stop_cost = stop_cost
        self._avg_time_to_next = None
        self._max_dist_to_next = None
        self._set_distance_bounds()

    @property
    def next(self) -> Stop | None:
        return self._next

    @next.setter
    def next(self, value: Stop) -> None:
        self._next = value

    @property
    def avg_time_to_next(self) -> Time:
        def _calculate_avg_time_to_next() -> Time:
            return Stop.stops.get_avg_time_between(self, self.next)

        if self._avg_time_to_next is None and self.next:
            self._avg_time_to_next: Time = _calculate_avg_time_to_next()
        return self._avg_time_to_next

    @staticmethod
    def get_max_dist(avg_time: Time) -> Distance:
        return Distance(km=avg_time.to_float_hours() * Config.average_speed)

    def _set_distance_bounds(self) -> None:
        if self.avg_time_to_next is None:
            self.distance_bounds = Distance(m=0), Distance(m=0)
            return

        lower = self.get_max_dist(self.avg_time_to_next - Time(0, 1))
        upper = self.get_max_dist(self.avg_time_to_next + Time(0, 1))
        self.distance_bounds = lower, upper

    @property
    def max_dist_to_next(self) -> Distance:
        if not self._max_dist_to_next:
            self._max_dist_to_next = self.get_max_dist(self.avg_time_to_next)
        return self._max_dist_to_next

    def before(self, other: Stop) -> bool:
        """ Return True, if this stop occurs before other. """
        return self.idx < other.idx

    def after(self, other: Stop) -> bool:
        """ Return True, if this stop occurs after other. """
        return self.idx > other.idx

    def __hash__(self) -> int:
        return hash(self.stop_id)

    def __repr__(self) -> str:
        return f"Stop({self.stop_id}, '{self.name}')"


class Stops:
    def __init__(self, handler: GTFSHandler,
                 stop_names: list[tuple[str, str]],
                 df: DF) -> None:
        self.handler = handler
        Stop.stops = self
        self.first, self.last = self._create_stops(stop_names, df)

    @property
    def stops(self) -> list[Stop]:
        stops = []
        current = self.first
        while current is not None:
            stops.append(current)
            current = current.next

        return stops

    @staticmethod
    def _create_stops(stop_names: list[tuple[str, str]], df: DF
                      ) -> tuple[Stop, Stop]:
        def _get_min_cost_from_df() -> DF:
            cost_df = pd.DataFrame(df[["stop_id", "node_cost", "name_cost"]])
            cost_df.loc[:, "cost"] = cost_df[
                ["node_cost", "name_cost"]].sum(axis=1)
            grouped = cost_df.groupby("stop_id", sort=False)
            return grouped["cost"].agg("min").cumsum()

        last = None
        stop = None
        stop_costs: DF = _get_min_cost_from_df()
        stop_names_with_index = [
            (idx, s_id, name) for idx, (s_id, name) in enumerate(stop_names)]

        for i, idx, stop_name in reversed(stop_names_with_index):
            try:
                stop_cost = stop_costs.loc[idx]
            except KeyError:
                stop_cost = i * MISSING_NODE_SCORE
            stop = Stop(i, idx, stop_name, stop, stop_cost)
            if not last:
                last = stop

        return stop, last

    def get_avg_time_between(self, stop1: Stop, stop2: Stop) -> Time:
        return self.handler.get_avg_time_between_stops(stop1.stop_id, stop2.stop_id)

    def __iter__(self) -> Generator[Stop, None, None]:
        current = self.first
        while current is not None:
            yield current
            current = current.next


class Cost:
    def __init__(self, parent_cost: float = None, node_cost: float = None,
                 name_cost: float = None, travel_cost: float = None,
                 stop_cost: float = None) -> None:
        def _get_cost(cost: float) -> float:
            return float("inf") if cost is None or cost < 0 else cost

        self.parent_cost = _get_cost(parent_cost)
        self.node_cost = _get_cost(node_cost)
        self.name_cost = _get_cost(name_cost)
        self.travel_cost = _get_cost(travel_cost)
        self.stop_cost = _get_cost(stop_cost)

    @property
    def as_float(self) -> float:
        return sum(self.costs)

    @property
    def travel_cost(self) -> float:
        return self._travel_cost

    @travel_cost.setter
    def travel_cost(self, travel_cost: float) -> None:
        if travel_cost != float("inf"):
            travel_cost = min(round(travel_cost), 100)
        self._travel_cost = travel_cost

    @property
    def costs(self) -> tuple[float, float, float, float, float]:
        return (self.parent_cost, self.node_cost,
                self.name_cost, self.travel_cost, self.stop_cost)

    @staticmethod
    def from_cost(cost: Cost) -> Cost:
        return Cost(cost.parent_cost, cost.node_cost,
                    cost.name_cost, cost.travel_cost,
                    cost.stop_cost)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cost) and self.as_float == other.as_float

    def __lt__(self, other: Cost) -> bool:
        if not isinstance(other, Cost):
            raise TypeError(
                f"Can only compare Cost to Cost, not {type(object)}.")
        return self.as_float < other.as_float

    def __le__(self, other: Cost) -> bool:
        return self == other or self < other

    def __gt__(self, other: Cost) -> bool:
        return not self <= other

    def __ge__(self, other: Cost) -> bool:
        return not self < other

    def __repr__(self) -> str:
        fmt = ">3.0f"
        return (f"Cost("
                f"total: {self.as_float:{fmt}}, "
                f"parent: {self.parent_cost:{fmt}}, "
                f"node: {self.node_cost:{fmt}}, "
                f"name: {self.name_cost:{fmt}}, "
                f"travel: {self.travel_cost:{fmt}})")


class StartCost(Cost):
    @staticmethod
    def from_cost(cost: Cost) -> Cost:
        s = Cost.from_cost(cost)
        s.parent_cost = 0
        s.travel_cost = 0
        return s


def calculate_travel_cost_between(from_node: Node, to_node: Node) -> float:
    step_count = 5
    if isinstance(from_node, MissingNode) or isinstance(to_node, MissingNode):
        return MissingNode.default_travel_cost

    lower, upper = from_node.stop.distance_bounds
    actual_distance: Distance = from_node.dist_exact(to_node)
    # Too far away from either bound. Lower is >= 0
    if not (lower < actual_distance <= upper):
        return float("inf")
    # Discrete function.
    expected_distance = upper - lower
    distance_diff = (actual_distance - expected_distance).m
    step_distance = (expected_distance - lower).m / step_count
    return (distance_diff // step_distance) + 1


class Node:
    nodes: Nodes = None

    def __init__(self, stop: Stop, index: int, names: str,
                 loc: Location, cost: Cost) -> None:
        self.stop = stop
        self.index = index
        self.names = names
        self.loc = loc
        self.parent = None
        self.has_children = False
        self.cost: Cost = cost
        self.has_neighbors = False
        self.visited = False
        if Node.nodes is None:
            raise Exception("Nodes needs to be set, before creating a node.")

    def get_neighbors(self) -> Generator[Node, None, None]:
        next_stop = self.stop.next
        df = Node.nodes.get_df_close_to_next(self)
        if (df.index.values < 0).any():
            return Node.nodes.missing_node_factory(df, next_stop)
        return Node.nodes.node_factory(df, next_stop)

    def dist_exact(self, node: Node) -> Distance:
        lat_mid = mean((self.loc.lat, node.loc.lat))
        distance_per_lon_deg = get_distance_per_lon_deg(lat_mid)
        lat_dist = abs(self.loc.lat - node.loc.lat) * DISTANCE_PER_LAT_DEG
        lon_dist = abs(self.loc.lon - node.loc.lon) * distance_per_lon_deg
        dist = math.sqrt(lat_dist.m ** 2 + lon_dist.m ** 2)
        return Distance(m=dist)

    def _is_close(self, lat: float, lon: float, max_dist: Distance) -> bool:
        """ Checks if the vertical/horizontal distances to lat/lon are
        less than max_dist. Faster than calculating the exact distance. """
        # TODO: Maybe use self.loc.lat instead of lat_mid
        lat_mid = self.loc.lat + lat
        lat_diff = abs(self.loc.lat - lat)
        lon_diff = abs(self.loc.lon - lon)
        lat_dist = lat_diff * DISTANCE_PER_LAT_DEG
        lon_dist = lon_diff * get_distance_per_lon_deg(lat_mid)
        return lat_dist < max_dist and lon_dist < max_dist

    def is_close(self, array: np.ndarray, max_dist: float = None) -> bool:
        if array[0] == 0 and array[1] == 0:
            return True
        if max_dist is None:
            max_dist = self.stop.max_dist_to_next
        return self._is_close(array[0], array[1], max_dist)

    def cost_with_parent(self, parent_node: Node) -> Cost:
        """ Return the cost of self, if parent_node was its parent. """

        travel_cost = calculate_travel_cost_between(self, parent_node)
        cost = Cost(parent_node.cost.as_float, self.cost.node_cost,
                    self.cost.name_cost, travel_cost)
        cost.parent_cost = parent_node.cost.as_float
        return cost

    def construct_route(self) -> list[Node]:
        if not self.parent:
            return [self]
        return self.parent.construct_route() + [self]

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Node) and
                self.stop == other.stop and self.index == other.index and
                self.loc == other.loc and self.cost == other.cost)

    def __lt__(self, other: Node) -> bool:
        if not isinstance(other, Node):
            raise TypeError(
                f"Can only compare Node to Node, not {type(object)}.")
        return self.stop.before(other.stop) and self.cost < other.cost

    def __le__(self, other: Node) -> bool:
        return ((self == other or self < other) and
                not self.stop.after(other.stop))

    def __gt__(self, other: Node):
        return not self <= other

    def __ge__(self, other: Node) -> bool:
        return not self < other

    def __repr__(self) -> str:
        base = (f"Node('{self.stop.name}', cost: {self.cost.as_float:.2f}, "
                f"loc: {self.loc}")
        if self.parent:
            dist_to_parent = self.dist_exact(self.parent)
            base += f", to_parent: {dist_to_parent.km:.3f}km"
        return base + ")"

    def __hash__(self) -> int:
        return hash(repr(self))

    @property
    def has_parent(self) -> bool:
        return self.parent is not None

    def update_parent_if_lower_cost(self, new_parent: Node) -> None:
        cost_to_new_parent = self.cost_with_parent(new_parent)
        if not self.has_parent:
            msg = (f"Found parent for {self}:\n"
                   f"\t{new_parent}\n"
                   f"\t\twith cost: {cost_to_new_parent}")
            logger.info(msg)
            self.nodes.update_parent(new_parent, self, cost_to_new_parent)
            return

        force_no_update = (isinstance(new_parent, MissingNode) and
                           not isinstance(self.parent, MissingNode))
        if force_no_update:
            return

        better_cost = cost_to_new_parent.as_float < self.cost.as_float
        force_update = (isinstance(self.parent, MissingNode) and
                        not isinstance(new_parent, MissingNode))
        if not better_cost and not force_update:
            return
        if better_cost and not force_update:
            msg = (f"Found parent with lower cost for {self}.\n"
                   f"\tCurrent: {self.parent}\n"
                   f"\t\twith cost: {self.cost}\n"
                   f"\tBetter:  {new_parent}\n"
                   f"\t\twith cost: {cost_to_new_parent}\n")
            logger.info(msg)

        self.nodes.update_parent(new_parent, self, cost_to_new_parent)


class MissingNode(Node):
    default_travel_cost = 30

    def __init__(self, stop: Stop, index: int, names: str, loc: Location,
                 parent_cost: float) -> None:
        cost = Cost(parent_cost, MISSING_NODE_SCORE, 0, 0)
        super().__init__(stop, index, names, loc, cost)

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

    def cost_with_parent(self, parent_node: Node) -> Cost:
        cost = Cost(parent_node.cost.as_float, MISSING_NODE_SCORE, 0,
                    MissingNode.default_travel_cost)
        return cost

    def __repr__(self) -> str:
        return "Missing" + super().__repr__()


class Nodes:
    def __init__(self, df: DF, stops: Stops) -> None:
        self.df = df
        self.node_map: dict[tuple[Stop, int]: Node] = {}
        self.node_heap: Heap[Node] = []
        self.next_missing_node_idx = -1
        self.higher_cost_dfs: dict[Stop: df] = {}
        Node.nodes = self
        self._initialize_dfs(stops)
        self._initialize_nodes(stops)

    def _initialize_dfs(self, stops: Stops) -> None:
        self.dfs: dict[Stop: DF] = {}

        stop = stops.first

        while True:
            self.dfs[stop] = self.filter_df_by_stop(stop)
            stop = stop.next
            if stop is None:
                break

    def _initialize_nodes(self, stops: Stops) -> None:
        stop = stops.first
        while True:
            df = self.filter_df_by_stop(stop)
            for values in df.itertuples(False, "StopPosition"):
                values: StopPosition
                node = self.get_or_create(stop, values)
                if stop == stops.first:
                    node.cost = StartCost.from_cost(node.cost)
            stop = stop.next
            if stop is None:
                break

    def _add(self, node: Node) -> None:
        self.node_map[(node.stop, node.index)] = node
        heapq.heappush(self.node_heap, node)

    def _create_node(self, stop: Stop, values: StopPosition) -> Node:
        loc = Location(values.lat, values.lon)
        cost = Cost(float("inf"), values.node_cost, values.name_cost,
                    stop_cost=stop.stop_cost)
        node = Node(stop, values.idx, values.names, loc, cost)
        self._add(node)
        return node

    def _create_missing_node(self, stop: Stop, values: StopPosition
                             ) -> MissingNode:
        loc = Location(values.lat, values.lon)
        node = MissingNode(
            stop, values.idx, values.names, loc, values.node_cost)
        node.cost.stop_cost = stop.stop_cost
        self._add(node)
        return node

    def get_or_create(self, stop: Stop, values: StopPosition) -> Node:
        node = self.node_map.get((stop, values.idx))
        if node is None:
            node = self._create_node(stop, values)
        return node

    def create_missing_neighbor_for_node(self, parent_node: Node) -> None:
        stop: Stop = parent_node.stop.next
        node_cost: float = parent_node.cost.as_float
        values = StopPosition(self.next_missing_node_idx, stop.name,
                              stop.name, 0, 0, node_cost, 0)
        neighbor = self._create_missing_node(stop, values)
        self.next_missing_node_idx -= 1
        neighbor.update_parent_if_lower_cost(parent_node)

    def get_or_create_missing(self, stop: Stop, values: StopPosition,
                              ) -> MissingNode:
        node = self.node_map.get((stop, values.idx))
        if node is None:
            node = self._create_missing_node(stop, values)
        return node

    def filter_df_by_stop(self, stop: Stop) -> DF:
        df = self.df.loc[self.df["stop_id"] == stop.stop_id]
        if df.empty:
            data = {"idx": self.next_missing_node_idx, "stop_id": stop.stop_id,
                    "names": stop.name, "lat": 0, "lon": 0,
                    "node_cost": MISSING_NODE_SCORE, "name_cost": 0}
            index = pd.Index([self.next_missing_node_idx])
            df = pd.DataFrame(data, index=index, columns=df.columns)
            self.next_missing_node_idx -= 1
        return df

    def get_df_close_to_next(self, node: Node) -> DF:
        next_stop = node.stop.next
        df = self.dfs.setdefault(next_stop, self.filter_df_by_stop(next_stop))
        return df[df[["lat", "lon"]].apply(node.is_close, raw=True, axis=1)]

    def get_missing_from_stop(self, stop: Stop) -> list[StopPosition]:
        stop_positions = []
        for i in range(self.next_missing_node_idx, 0):
            if (stop, i) not in self.node_map:
                continue
            stop_positions.append(StopPosition(
                i, stop.name, stop.name, 0, 0, MISSING_NODE_SCORE, 0))
        return stop_positions

    def node_factory(self, df: DF, stop: Stop) -> Generator[Node, None, None]:
        create_node_partial: Callable[[StopPosition], Node]
        create_node_partial = partial(self.get_or_create, stop)
        stop_positions = list(df.itertuples(False, "StopPosition"))
        stop_positions += self.get_missing_from_stop(stop)
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

    def update_parent(self, parent: Node, node: Node, cost: Cost) -> None:
        try:
            self.node_heap.remove(node)
        except ValueError:
            pass

        node.parent = parent
        node.cost = cost
        parent.has_children = True
        heapq.heappush(self.node_heap, node)

    def duplicate_missing_node(self, node: MissingNode) -> None:
        duplicate = MissingNode(node.stop, self.next_missing_node_idx,
                                node.names, node.loc, node.cost.node_cost)
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
        self.stops = Stops(handler, stop_names, df)
        self.nodes = Nodes(df, self.stops)

    def find_dijkstra(self) -> list[Node]:
        self._initialize_start()
        self._initialize_nodes()
        while True:
            node: Node = self.nodes.get_min()
            if node.stop == self.stops.last:
                break
            for neighbor in node.get_neighbors():
                neighbor.update_parent_if_lower_cost(node)
            if not node.has_children:
                self.nodes.create_missing_neighbor_for_node(node)
            node.visited = True

        route = node.construct_route()
        return route

    def _initialize_start(self) -> None:
        stop = self.stops.first
        df = self.nodes.filter_df_by_stop(stop)
        for values in df.itertuples(False, "StopPosition"):
            values: StopPosition
            node = self.nodes.get_or_create(stop, values)
            node.cost = StartCost.from_cost(node.cost)

    def _initialize_nodes(self) -> None:
        stop = self.stops.first
        while True:
            stop = stop.next
            if stop is None:
                break
            df = self.nodes.filter_df_by_stop(stop)
            for values in df.itertuples(False, "StopPosition"):
                values: StopPosition
                self.nodes.get_or_create(stop, values)


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
                 f"Cost: {node.cost.as_float:>7.2f}<br>"
                 f"Node:  {node.cost.node_cost:>7.2f}<br>"
                 f"Name:  {node.cost.name_cost:>7.2f}<br>"
                 f"Dist:  {node.cost.travel_cost:>7.2f}<br>"
                 f"Lat:   {loc[0]:>7.4f}<br>"
                 f"Lon:   {loc[1]:>7.4f}")
        folium.Marker(loc, popup=popup, icon=icon).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


def find_shortest_route(handler: GTFSHandler,
                        stop_names: list[tuple[str, str]], df: DF
                        ) -> dict[str: Node]:
    logger.info("Starting location detection...")
    t = time()
    route_finder = RouteFinder(handler, stop_names, df.copy())
    route = route_finder.find_dijkstra()
    update_missing_locations(route)
    logger.info(f"Done. Took {time() - t:.2f}s")

    if Config.display_route in [4, 5, 6, 7]:
        nodes = [node for node in route_finder.nodes.node_map.values()
                 if not isinstance(node, MissingNode)
                 and node.cost.as_float != float("inf")]
        display_route(nodes)

    if Config.display_route in [2, 3, 6, 7]:
        display_route(route)

    return {node.stop.stop_id: node
            for node in route if not isinstance(node, MissingNode)}
