""" Provide functions/classes to enable location detection. """

from __future__ import annotations

import logging
import sys
import webbrowser
from math import inf, log, sqrt
from statistics import mean, StatisticsError
from typing import Type

import folium
import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.locate.finder.cost import Cost, StartCost
from pdf2gtfs.locate.finder.location import (
    DISTANCE_IN_M_PER_LAT_DEG, get_distance_per_lon_deg, Location)
from pdf2gtfs.locate.finder.stops import Stop, Stops
from pdf2gtfs.locate.finder.types import DF, StopPosition


logger = logging.getLogger(__name__)


class Node:
    """ Provide comparable Nodes, which combine stops, locs, and costs. """
    nodes: Nodes = None

    def __init__(self, stop: Stop, index: int, names: str,
                 loc: Location, cost: Cost) -> None:
        self.stop = stop
        self.index = index
        self.names = names
        self.loc: Location = loc
        self.parent: Node | None = None
        self.has_children = False
        self.cost: Cost = cost
        self.visited = False
        self.stop.nodes.append(self)
        if Node.nodes is None:
            raise Exception("Node.nodes needs to be set, "
                            "before creating a Node.")

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Node) and
                self.stop == other.stop and self.index == other.index and
                self.loc == other.loc and self.cost == other.cost)

    def __repr__(self) -> str:
        base = (f"Node('{self.stop.name}', cost: {self.cost.as_float:.0f}, "
                f"loc: {self.loc}")
        valid_parent = (self.parent and
                        not isinstance(self.parent, MNode) and
                        not isinstance(self, MNode))
        if valid_parent:
            dist_to_parent = self.dist_exact(self.parent)
            base += f", to_parent: {dist_to_parent / 1000:.3f}km"
        return base + ")"

    def __hash__(self) -> int:
        return id(self)

    def get_close_neighbors(self) -> list[Node]:
        """ Return all neighbors of node that are close to node. """
        all_neighbors = self.stop.next.nodes
        neighbors = [n for n in all_neighbors if self.close_nodes(n)]
        return neighbors

    def dist_exact(self, node: Node) -> float:
        """ Return our exact distance (up to a few m) to the given node. """
        # TODO NOW: Use geopy.
        lat_mid = mean((self.loc.lat, node.loc.lat))
        distance_per_lon_deg = get_distance_per_lon_deg(lat_mid)
        lat_dist = abs(self.loc.lat - node.loc.lat) * DISTANCE_IN_M_PER_LAT_DEG
        lon_dist = abs(self.loc.lon - node.loc.lon) * distance_per_lon_deg
        dist = sqrt(lat_dist ** 2 + lon_dist ** 2)
        return dist

    def cost_with_parent(self, parent_node: Node) -> Cost:
        """ Calculate the cost of self, if parent_node was its parent. """

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

    @property
    def has_parent(self) -> bool:
        """ If the node has a parent. """
        return self.parent is not None

    def set_parent(self, parent: Node) -> None:
        """ Set our parent to parent, if it is different to our parent. """
        if self.parent and parent == self.parent:
            return
        cost = self.cost_with_parent(parent)
        if cost.as_float == inf:
            return
        self.nodes.update_parent(parent, self, cost)

    def update_parent_if_better(self, parent: Node) -> None:
        """ Update the parent to other, if it is better. """
        if not self.parent:
            self.set_parent(parent)
            return
        self.set_parent(self._select_better_parent(self.parent, parent))

    def _select_better_parent(self, parent1: Node, parent2: Node) -> Node:
        """ Select the better parent of the two given parents. """
        better_node_by_type = self.compare_node_type(parent1, parent2)
        if better_node_by_type is None:
            cost1 = self.cost_with_parent(parent1)
            cost2 = self.cost_with_parent(parent2)
            return parent1 if cost1 <= cost2 else parent2
        return better_node_by_type

    def get_max_dist(self) -> float:
        """ Return the maximum distance of the current node. """
        return self.stop.distance_bounds[2]

    def close_nodes(self, node: Node, max_dist: float = 0) -> bool:
        """ Return if the two nodes are close to each other. """
        if Config.disable_close_node_check:
            return True
        if isinstance(node, MNode) and not node.parent:
            return True
        if max_dist == 0:
            max_dist = self.get_max_dist()
        distances = self.loc.distances(node.loc)
        return all(dist <= max_dist for dist in distances)

    @staticmethod
    def compare_node_type(node1: Node, node2: Node) -> Node | None:
        """ Compare the two nodes and return the one with the better type.

        If both have the same type, return None instead.
        ENodes are better than Nodes and Nodes are better than MNodes.
        """

        def type_count(n1: Node, n2: Node, node_type: Type[Node]) -> int:
            """ Sum the number of nodes with the given node_type. """
            return isinstance(n1, node_type) + isinstance(n2, node_type)

        # Can only compare the type of nodes of the same stop.
        assert node1.stop == node2.stop

        existing_node_count = type_count(node1, node2, ENode)
        # If only one Node is an existing node, we return it.
        if existing_node_count == 1:
            return node1 if isinstance(node1, ENode) else node2
        # If both nodes are the same type,
        if existing_node_count == 2:
            return None
        missing_node_count = type_count(node1, node2, MNode)
        # If only one node is a MissingNode, return the other one.
        if missing_node_count == 1:
            return node1 if isinstance(node2, MNode) else node2
        return None

    def update_neighbors(self) -> None:
        """ Update the neighbor's parent to, if necessary. """
        has_neighbors = False
        for neighbor in self.get_close_neighbors():
            neighbor.update_parent_if_better(self)
            if isinstance(neighbor, MNode):
                continue
            has_neighbors = True
        self.visited = True

        # Only create MissingNodes if we don't have any true neighbors,
        #  children, or if there is no ENode for the neighbors' stop.
        if has_neighbors or self.has_children or self.stop.next.exists:
            return
        logger.debug(f"Created missing childnode for {self}")
        self.nodes.create_missing_neighbor_for_node(self)


class MNode(Node):
    """ Describes a node, we know exists, but do not have the location for.
    It has a high node_score, to prevent MissingNodes to be better than
    normal ones. """

    def __init__(self, stop: Stop, index: int, names: str, loc: Location,
                 parent_cost: float) -> None:
        cost = Cost(parent_cost, Config.missing_node_cost, 0, 0)
        super().__init__(stop, index, names, loc, cost)

    def __repr__(self) -> str:
        return "M" + super().__repr__()

    def dist_exact(self, node: Node) -> float:
        """ The exact distance of a MissingNode to another Node
        is only defined, if its parent is. """
        if self.parent:
            return self.parent.dist_exact(node)
        raise NotImplementedError(
            "Can't calculate distance to missing node without parent.")

    def get_max_dist(self) -> float:
        """ Return the maximum distance of the current node.

        If the MNode has no parent, return maxsize instead.
        """
        if not self.parent:
            return inf
        return super().get_max_dist() + self.parent.get_max_dist()

    def cost_with_parent(self, parent: Node) -> Cost:
        """ Calculate the cost the Node would have to the given node. """
        cost = Cost(parent.cost.as_float, Config.missing_node_cost, 0, 0)
        return cost

    def close_nodes(self, node: Node, max_dist: float = 0) -> bool:
        """ Return if the node is close.

        MNodes without a parent are always close to other nodes. If they do
        have a parent, use the parent as anchor, to check if node is close.
        """
        if not self.parent:
            return True
        return self.parent.close_nodes(node, self.get_max_dist())


class ENode(Node):
    """ Nodes used for existing locations. """

    def __init__(self, stop: Stop, loc: Location, parent_cost: float) -> None:
        cost = Cost(parent_cost, 0, 0, 0)
        index = sys.maxsize
        super().__init__(stop, index, stop.name, loc, cost)

    def __repr__(self) -> str:
        return "E" + super().__repr__()


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

    def _initialize_dfs(self, stops: Stops) -> None:
        self.dfs: dict[Stop: DF] = {}

        stop = stops.first

        while stop is not None:
            self.dfs[stop] = self.filter_df_by_stop(stop)
            stop = stop.next

    def _add(self, node: Node) -> None:
        self._node_map[(node.stop, node.index)] = node
        self._node_heap.add_node(node)

    def create_nodes_for_stop(self, stop: Stop, loc: Location | None) -> None:
        """ Create the nodes for the given stop.

        If loc is given and valid, create an ExistingNode, otherwise use
        the dataframe to generate Node/MissingNode, depending on its values.
        """
        if loc and loc.is_valid:
            node = self._create_existing_node(stop, loc)
            if stop.is_first:
                node.cost = StartCost.from_cost(node.cost)
                self._node_heap.update(node)
            return

        df = self.filter_df_by_stop(stop)
        for values in df.itertuples(False, "StopPosition"):
            values: StopPosition
            if values.lat == 0 or values.lon == 0:
                node = self.get_or_create_missing(stop, values)
            else:
                node = self.get_or_create(stop, values)
            if stop.is_first:
                node.cost = StartCost.from_cost(node.cost)
                self._node_heap.update(node)

    def _create_node(self, stop: Stop, values: StopPosition) -> Node:
        loc = Location(values.lat, values.lon)
        cost = Cost(inf, values.node_cost, values.name_cost, None)
        node = Node(stop, values.idx, values.names, loc, cost)
        self._add(node)
        return node

    def _create_missing_node(self, stop: Stop, values: StopPosition) -> MNode:
        loc = Location(values.lat, values.lon)
        node = MNode(stop, values.idx, values.names, loc, inf)
        self._add(node)
        return node

    def _create_existing_node(self, stop: Stop, loc: Location) -> ENode:
        """ Create a new ExistingNode for stop at the given location. """
        parent_cost = 0 if stop.is_first else inf
        node = ENode(stop, loc, parent_cost)
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
            0, 0, Config.missing_node_cost, 0)
        neighbor = self._create_missing_node(stop, values)
        self.next_missing_node_idx -= 1
        neighbor.update_parent_if_better(parent)
        self._add(neighbor)

    def get_or_create_missing(self, stop: Stop, values: StopPosition) -> MNode:
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

    def get_min_node(self) -> Node:
        """ Return the unvisited node with the lowest Cost. """
        return self._node_heap.pop()

    def update_parent(self, parent: Node, node: Node, cost: Cost) -> None:
        """ Update the parent and cost of the node. """
        node.parent = parent
        node.cost = cost
        parent.has_children = True
        self._node_heap.update(node)

    def display_all_nodes(self) -> None:
        """ Display all nodes, that are not MissingNodes. """
        all_nodes = [node for node in self._node_map.values()
                     if not isinstance(node, MNode)
                     and node.cost.as_float != inf]
        display_nodes(all_nodes)

    def __repr__(self) -> str:
        num_stops = len(set([nodes for nodes, _ in self._node_map]))
        return (f"Nodes(# stops: {num_stops}, "
                f"# nodes: {len(self._node_map)}, "
                f"# unvisited nodes: {self._node_heap.count})")


def calculate_travel_cost_between(from_node: Node, to_node: Node) -> float:
    """ Return the travel cost between from_node and to_node. """
    if isinstance(from_node, MNode) or isinstance(to_node, MNode):
        return 0

    actual_distance: float = from_node.dist_exact(to_node)
    # Distance is too small.
    if actual_distance < Config.min_travel_distance:
        return inf
    if Config.simple_travel_cost_calculation:
        return int(log(max(1, int(actual_distance)), 8))

    lower, mid, upper = from_node.stop.distance_bounds
    # Log cant handle 0.
    dist_to_mid = max(1, abs(actual_distance - mid))
    # Determine the log_base, depending on the lower and upper bounds. If
    #  the log_base decreases, the cost will increase. This is used to punish
    #  distances too far away from the expected distance more harshly.
    log_base = 8
    if actual_distance < lower:
        log_base /= lower // actual_distance
    if actual_distance > upper:
        log_base /= actual_distance // upper
    # Log base needs to be higher than 1.
    log_base = max(1.001, log_base)
    travel_cost = int(log(max(1, int(log(dist_to_mid, log_base) ** 4)), 2))
    return max(1, travel_cost)


def display_nodes(nodes: list[Node]) -> None:
    """ Display the given nodes in the default webbrowser. """

    def get_map_location() -> tuple[float, float]:
        """ Calculate the location of the map upon opening it.

        Returns the average location of all Nodes, which are not Missing.
        """
        try:
            valid_nodes = [n for n in nodes if not isinstance(n, MNode)]
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
        if isinstance(node, MNode):
            icon = folium.Icon(color="red", icon="glyphicon-remove")
        elif isinstance(node, ENode):
            icon = folium.Icon(color="blue", icon="glyphicon-lock")
        else:
            icon = folium.Icon(color="green", icon="glyphicon-ok")
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

        if node.cost.as_float == inf:
            return
        # Node already exists.
        if node in self.node_map:
            self.update(node)
            return

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
            if (previous.next is None
                    or previous.next and previous.next.node_cost > node_cost):
                break
            if node_cost >= previous.node_cost:
                previous = previous.next
                continue
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

    def __repr__(self) -> str:
        return f"HeapNode({self.node})"
