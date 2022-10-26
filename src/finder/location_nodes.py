""" Provide functions/classes to enable location detection. """

from __future__ import annotations

import logging
import webbrowser
from functools import partial
from math import inf, sqrt
from statistics import mean, StatisticsError
from typing import Callable, Generator

import folium
import numpy as np
import pandas as pd

from config import Config
from finder import Location
from finder.cost import Cost, StartCost
from finder.distance import (
    Distance, DISTANCE_PER_LAT_DEG, get_distance_per_lon_deg)
from finder.stops import Stop, Stops
from finder.types import DF, StopPosition


logger = logging.getLogger(__name__)


class Node:
    """ Provide comparable Nodes, which combine stops, locs, and costs. """
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
        self.visited = False
        if Node.nodes is None:
            raise Exception("Nodes needs to be set, before creating a node.")

    def get_neighbors(self) -> Generator[Node, None, None]:
        """ Return the neighbors of the node, that are within the
        maximum travel distance of the Nodes stop. """
        df = Node.nodes.get_df_close_to_next(self)
        if (df.index.values < 0).any():
            return Node.nodes.missing_node_factory(df, self.stop.next)
        return Node.nodes.node_factory(df, self.stop.next)

    def dist_exact(self, node: Node) -> Distance:
        """ Return our exact distance (up to a few m) to the given node. """
        # TODO NOW: Use geopy.
        lat_mid = mean((self.loc.lat, node.loc.lat))
        distance_per_lon_deg = get_distance_per_lon_deg(lat_mid)
        lat_dist = abs(self.loc.lat - node.loc.lat) * DISTANCE_PER_LAT_DEG
        lon_dist = abs(self.loc.lon - node.loc.lon) * distance_per_lon_deg
        dist = sqrt(lat_dist.m ** 2 + lon_dist.m ** 2)
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

    def is_close(self, array: np.ndarray, max_dist: float = None,
                 add_self: bool = False) -> bool:
        """ Whether the lat/lon given by the array are close to our location.
        If add_self is given, add our stops max_dist_to_next """
        if array[0] == 0 and array[1] == 0:
            return True
        if max_dist is None:
            max_dist = Distance(m=0)
            add_self = True
        if add_self:
            # TODO NOW: This '* 3' should be done elsewhere.
            max_dist += self.stop.max_dist_to_next * 3
        return self._is_close(array[0], array[1], max_dist)

    def cost_with_parent(self, parent_node: Node) -> Cost:
        """ Return the cost of self, if parent_node was its parent. """

        travel_cost = calculate_travel_cost_between(parent_node, self)
        cost = Cost(parent_node.cost.as_float, self.cost.node_cost,
                    self.cost.name_cost, travel_cost)
        return cost

    def construct_route(self) -> list[Node]:
        """ Construct the full route.

        In the full route, each entry is the parent of the next entry.
        """
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
        return self.cost < other.cost

    def __le__(self, other: Node) -> bool:
        return self < other or self == other

    def __gt__(self, other: Node):
        return not self <= other

    def __ge__(self, other: Node) -> bool:
        return not self < other

    def __repr__(self) -> str:
        base = (f"Node('{self.stop.name}', cost: {self.cost.as_float:.0f}, "
                f"loc: {self.loc}")
        valid_parent = (self.parent and
                        not isinstance(self.parent, MissingNode) and
                        not isinstance(self, MissingNode))
        if valid_parent:
            dist_to_parent = self.dist_exact(self.parent)
            base += f", to_parent: {dist_to_parent.km:.3f}km"
        return base + ")"

    def __hash__(self) -> int:
        return id(self)

    @property
    def has_parent(self) -> bool:
        """ If the node has a parent. """
        return self.parent is not None

    def update_parent_if_lower_cost(self, new_parent: Node) -> None:
        """ If the new_parent is a better parent than the current one, change
        our parent to new_parent.
        A parent A is better than another B, if
         - B is None (i.e. Node has no parent)
         - B is a MissingNode and A is not
         - the cost from Node to A are lower than the cost from Node to B.
        """
        cost_to_new_parent = self.cost_with_parent(new_parent)
        if not self.has_parent:
            msg = (f"Found parent for {self}:\n"
                   f"\t{new_parent}\n"
                   f"\t\twith cost: {cost_to_new_parent}\n")
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
    """ Describes a node, we know exists, but do not have the location for.
    It has a high node_score, to prevent MissingNodes to be better than
    normal ones. """

    def __init__(self, stop: Stop, index: int, names: str, loc: Location,
                 parent_cost: float) -> None:
        cost = Cost(parent_cost, 0, 0, 0)
        super().__init__(stop, index, names, loc, cost)

    def dist_exact(self, node: Node) -> Distance:
        """ The exact distance of a MissingNode to another Node
        is only defined, if its parent is. """
        if self.parent:
            return self.parent.dist_exact(node)
        raise NotImplementedError(
            "Can't calculate distance to missing node without parent.")

    def is_close(self, array: np.ndarray,
                 max_dist: float = None, add_self: bool = True) -> bool:
        """ MissingNodes without parent are always close to other Nodes.
        MissingNodes with parent use their parents is_close method,
        with increased max_dist. """
        if not self.parent:
            # We don't know where the missing node is, so we have to assume
            # it is close. Only relevant if there are no start nodes.
            return True

        if max_dist is None:
            max_dist = Distance(m=0)
        if add_self:
            max_dist += self.stop.max_dist_to_next * 3
        return self.parent.is_close(array, max_dist, add_self)

    def cost_with_parent(self, parent: Node) -> Cost:
        """ Calculate the cost the Node would have to the given node. """
        cost = Cost(parent.cost.as_float, 0, 0, 0)
        return cost

    def __repr__(self) -> str:
        return "Missing" + super().__repr__()


class Nodes:
    """ Container for Nodes. Provides methods to query and create nodes. """

    def __init__(self, df: DF, stops: Stops) -> None:
        self.df = df
        self._node_map: dict[tuple[Stop, int]: Node] = {}
        self._node_heap: NodeHeap = NodeHeap()
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
                if values.lat == 0 or values.lon == 0:
                    node = self.get_or_create_missing(stop, values)
                else:
                    node = self.get_or_create(stop, values)
                if stop == stops.first:
                    node.cost = StartCost.from_cost(node.cost)
                    self._node_heap.add_node(node)
            if stop.is_last:
                break
            stop = stop.next

    def _add(self, node: Node) -> None:
        self._node_map[(node.stop, node.index)] = node
        if node.cost.as_float == inf:
            return
        self._node_heap.add_node(node)

    def _create_node(self, stop: Stop, values: StopPosition) -> Node:
        loc = Location(values.lat, values.lon)
        cost = Cost(inf, values.node_cost, values.name_cost, None)
        node = Node(stop, values.idx, values.names, loc, cost)
        self._add(node)
        return node

    def _create_missing_node(self, stop: Stop, values: StopPosition
                             ) -> MissingNode:
        loc = Location(values.lat, values.lon)
        node = MissingNode(stop, values.idx, values.names, loc, inf)
        self._add(node)
        return node

    def get_or_create(self, stop: Stop, values: StopPosition) -> Node:
        """ Checks if a Node with the given stop and values exist,
        and returns it. If it does not exist, it will first be created. """
        node = self._node_map.get((stop, values.idx))
        if node is None:
            node = self._create_node(stop, values)
        return node

    def create_missing_neighbor_for_node(self, parent: Node) -> None:
        """ Create a MissingNode with parent_node as its parent. """
        stop: Stop = parent.stop.next
        values: StopPosition = StopPosition(
            self.next_missing_node_idx, stop.name, stop.name,
            0, 0, parent.cost.as_float, 0)
        neighbor = self._create_missing_node(stop, values)
        self.next_missing_node_idx -= 1
        neighbor.update_parent_if_lower_cost(parent)

    def get_or_create_missing(self, stop: Stop, values: StopPosition,
                              ) -> MissingNode:
        """ Checks if a MissingNode with the given stop and values exist,
        and returns it. If it does not exist, it will first be created. """
        node = self._node_map.get((stop, values.idx))
        if node is None:
            node = self._create_missing_node(stop, values)
        return node

    def filter_df_by_stop(self, stop: Stop) -> DF:
        """ Return a dataframe containing only
        entries with the given stop's stop_id. """
        df = self.df.loc[self.df["stop_id"] == stop.stop_id]
        if df.empty:
            data = {"idx": self.next_missing_node_idx, "stop_id": stop.stop_id,
                    "names": stop.name, "lat": 0, "lon": 0,
                    "node_cost": 0, "name_cost": 0}
            index = pd.Index([self.next_missing_node_idx])
            df = pd.DataFrame(data, index=index, columns=df.columns)
            self.next_missing_node_idx -= 1
        return df

    def get_df_close_to_next(self, node: Node) -> DF:
        """ Return a dataframe of nodes close to the given node. """
        next_stop = node.stop.next
        df = self.dfs.setdefault(next_stop, self.filter_df_by_stop(next_stop))
        return df[df[["lat", "lon"]].apply(node.is_close, raw=True, axis=1)]

    def get_missing_from_stop(self, stop: Stop) -> list[StopPosition]:
        """ Return all existing MissingNodes using the given stop. """
        stop_positions = []
        for i in range(self.next_missing_node_idx, 0):
            if (stop, i) not in self._node_map:
                continue
            stop_position = StopPosition(i, stop.name, stop.name, 0, 0, 0, 0)
            stop_positions.append(stop_position)
        return stop_positions

    def node_factory(self, df: DF, stop: Stop) -> Generator[Node, None, None]:
        """ Return a function, which when called will return a new Node,
        with the given stop and the next values in df. """
        create_node_partial: Callable[[StopPosition], Node]
        create_node_partial = partial(self.get_or_create, stop)
        stop_positions = list(df.itertuples(False, "StopPosition"))
        stop_positions += self.get_missing_from_stop(stop)
        return (create_node_partial(pos) for pos in stop_positions)

    def missing_node_factory(self, df: DF, stop: Stop
                             ) -> Generator[Node, None, None]:
        """ Return a function, which when called will return a new MissingNode,
        with the given stop and the next values in df. """
        create_missing_partial: Callable[[StopPosition], Node]
        create_missing_partial = partial(self.get_or_create_missing, stop)
        stop_positions = df.itertuples(False, "StopPosition")
        return (create_missing_partial(pos) for pos in stop_positions)

    def pop(self) -> Node:
        """ Return the unvisited node with the lowest Cost. """
        return self._node_heap.pop()

    def update_parent(self, parent: Node, node: Node, cost: Cost) -> None:
        """ Update the parent and cost of the node. """
        node.parent = parent
        node.cost = cost
        parent.has_children = True
        self._node_heap.update(node)

    def duplicate_missing_node(self, node: MissingNode) -> None:
        """ Creates a new MissingNode, with the same values of node,
        but with a different index. """
        duplicate = MissingNode(node.stop, self.next_missing_node_idx,
                                node.names, node.loc, node.cost.node_cost)
        self._add(duplicate)
        self.next_missing_node_idx -= 1

    def __repr__(self) -> str:
        num_stops = len(set([nodes for nodes, _ in self._node_map]))
        return (f"Nodes(# stops: {num_stops}, "
                f"# nodes: {len(self._node_map)}, "
                f"# unvisited nodes: {self._node_heap.count})")

    def display_all_nodes(self) -> None:
        """ Display all nodes, that are not MissingNodes. """
        all_nodes = [node for node in self._node_map.values()
                     if not isinstance(node, MissingNode)
                     and node.cost.as_float != inf]
        display_nodes(all_nodes)


def calculate_travel_cost_between(from_node: Node, to_node: Node) -> float:
    """ Return the travel cost between from_node and to_node. """
    if isinstance(from_node, MissingNode) or isinstance(to_node, MissingNode):
        return 0
    # TODO: Currently does not use lower/upper bounds,
    #  other than getting expected distance.
    lower, upper = from_node.stop.distance_bounds
    actual_distance: Distance = from_node.dist_exact(to_node)
    # Too far away from either bound. Lower is >= 0
    if actual_distance.m == 0:
        return inf
    step_count = 5
    # Discrete function, to prevent values close to each other
    # having vastly different scores.
    expected_distance = upper - lower
    distance_diff = (actual_distance - expected_distance).m
    step_distance = (expected_distance - lower).m / step_count
    if step_distance < 1:
        return 1
    return (distance_diff // (step_distance + 1)) + 1


def display_nodes(nodes: list[Node]) -> None:
    """ Display the given nodes in the default webbrowser. """

    def get_map_location() -> tuple[float, float]:
        """ Calculate the location of the map upon opening it.

        Returns the average location of all Nodes, which are not Missing.
        """
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
        text = (f"Stop: '{node.stop.name}'<br>"
                f"Names: '{node.names}'<br>"
                f"Lat: {loc[0]:>7.4f}<br>"
                f"Lon: {loc[1]:>7.4f}<br>"
                f"Total cost : {node.cost.as_float:>7.2f}<br>"
                f"Node cost  : {node.cost.node_cost:>7.2f}<br>"
                f"Name cost  : {node.cost.name_cost:>7.2f}<br>"
                f"Travel cost: {node.cost.travel_cost:>7.2f}<br>")
        max_width = max(map(len, text.split("<br>"))) * 20
        popup = folium.Popup(text, max_width=max_width)
        folium.Marker(loc, popup=popup, icon=icon).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


class NodeHeap:
    """ Min heap. """

    def __init__(self) -> None:
        self.first: HeapNode | None = None
        self.node_map: dict[Node: HeapNode] = {}

    @property
    def count(self) -> int:
        """ The number of nodes that are in the heap. """
        return len(self.node_map)

    def add_node(self, node: Node) -> None:
        """ Add the node to the heap, based on its cost.

        If the cost is equal to another node's cost in the heap, insert at the
        last position, such that the previous node's cost are equal and the
        next (it it exists) are higher.
        """

        heap_node = HeapNode(node)
        self.node_map[node] = heap_node
        # Heap is empty.
        if self.first is None:
            self.first = heap_node
            return

        self.insert_after(self._find_previous(heap_node), heap_node)

    def _find_previous(self, heap_node: HeapNode) -> HeapNode | None:
        """ Find the last node, with lower or equal score to heap_node.

        Return a node, such that heap_node has higher or equal cost to node,
        but lower cost than node.next, if it exists.
        Also ensure that node is the last node with that cost.
        """
        node_cost = heap_node.node_cost
        if node_cost < self.first.node_cost:
            return None

        previous = self.first
        while True:
            if previous.next is None or node_cost < previous.node_cost:
                break
            if node_cost > previous.node_cost:
                previous = previous.next
                continue
            # Only break, if the previous's cost are equal to
            #  node's cost and the next node has higher cost.
            if previous.next.node_cost > previous.node_cost:
                break
            previous = previous.next
        return previous

    def insert_after(self, prev: HeapNode | None, heap_node: HeapNode) -> None:
        """ Insert the given heap_node after prev.

        If prev is None, heap_node will be set to first.
        """
        if prev is None:
            self.first.prev = heap_node
            heap_node.next = self.first
            self.first = heap_node
            return

        if prev.next:
            prev.next.prev = heap_node
            heap_node.next = prev.next
        prev.next = heap_node
        heap_node.prev = prev

    def pop(self) -> Node | None:
        """ Return the current min node, without removing it. """
        node = self.first.node
        self.remove(self.first)
        return node

    def update(self, node: Node) -> None:
        """ Removes and re-adds the node, if its cost has changed. """
        if node not in self.node_map:
            self.add_node(node)
            return
        heap_node: HeapNode = self.node_map[node]
        if heap_node.valid_position:
            return
        self.remove(heap_node)
        self.add_node(node)

    def remove(self, heap_node: HeapNode) -> None:
        """ Remove the given node from the heap, updating its neighbors. """
        if self.first == heap_node:
            self.first = heap_node.next
        if heap_node.next:
            heap_node.next.prev = heap_node.prev
        if heap_node.prev:
            heap_node.prev.next = heap_node.next
        del self.node_map[heap_node.node]


class HeapNode:
    """ Linked list node for the NodeHeap. """

    def __init__(self, node: Node) -> None:
        self.node: Node = node
        self.prev: HeapNode | None = None
        self.next: HeapNode | None = None

    @property
    def node_cost(self) -> float:
        """ Return the node's cost. """
        return self.node.cost.as_float

    @property
    def valid_position(self) -> bool:
        """ Check if our node's cost are between prev's and next's costs. """
        if self.prev and self.prev.node_cost > self.node_cost:
            return False
        if self.next and self.next.node_cost < self.node_cost:
            return False
        return True
