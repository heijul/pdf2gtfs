""" Provides functions and classes to detect the location of stops. """

from __future__ import annotations

import heapq
import logging
from math import inf
from time import time
from typing import TYPE_CHECKING

from config import Config
from finder.location import Location
from finder.location_nodes import display_nodes, MissingNode, Nodes
from finder.stops import Stops
from finder.types import DF


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler
    from finder import Node

logger = logging.getLogger(__name__)


class LocationFinder:
    """ Tries to find the locations of the given stop_names for all routes
    described in the given handler. """

    def __init__(self, handler: GTFSHandler, stop_names: list[tuple[str, str]],
                 df: DF) -> None:
        self.handler = handler
        self.stops = Stops(handler, stop_names)
        self.nodes = Nodes(df, self.stops)

    def find_dijkstra(self) -> list[Node]:
        """ Uses Dijkstra's algorithm to find the shortest route. """
        while True:
            # TODO NOW: This should be done another way. Takes O(n) I guess?
            heapq.heapify(self.nodes.node_heap)
            node: Node = self.nodes.get_min()
            if node.stop.is_last:
                if not node.parent:
                    continue
                break
            has_neighbors = False
            for neighbor in node.get_neighbors():
                neighbor.update_parent_if_lower_cost(node)
                if isinstance(neighbor, MissingNode):
                    continue
                has_neighbors = True
            if not node.has_children and not has_neighbors:
                logger.info(f"Created missing childnode for {node}")
                self.nodes.create_missing_neighbor_for_node(node)
            node.visited = True

        route = node.construct_route()
        return route


def update_missing_locations(nodes) -> None:
    """ Interpoplate the location of missing nodes using their neighbors.

    Given that at least one MissingNode is in nodes, change the location
    of the missing nodes, such that it is between the previous and next Node's
    location. If consecutive nodes are missing they will all have equal
    distance to each other and the wrapping nodes.
    Will not update locations of MissingNodes at the start. """

    def get_first_node() -> tuple[int, Node | None]:
        """ Return the first node that is not a MissingNode. """
        for i, n in enumerate(nodes):
            if isinstance(n, MissingNode):
                continue
            return i + 1, n
        return 0, None

    # TODO NOW: Use the distance/vector of the first actual node to the second
    #  (missing or) actual node.
    start_id, prev = get_first_node()
    if prev is None:
        return

    missing_nodes = []
    for node in nodes[start_id:]:
        if isinstance(node, MissingNode):
            missing_nodes.append(node)
            continue
        if not missing_nodes:
            prev = node
            continue
        div = len(missing_nodes) + 1
        delta = Location((node.loc.lat - prev.loc.lat) / div,
                         (node.loc.lon - prev.loc.lon) / div)
        loc = prev.loc + delta

        for m in missing_nodes:
            m.loc = loc
            loc += delta
        missing_nodes = []
        prev = node


def find_stop_nodes(handler: GTFSHandler,
                    route: list[tuple[str, str]], df: DF
                    ) -> dict[str: Node]:
    """ Return the Nodes mapped to the stop ids for a list of routes. """
    logger.info("Starting location detection...")
    t = time()
    d = df.copy()
    location_finder = LocationFinder(handler, route, d.copy())
    nodes = location_finder.find_dijkstra()
    update_missing_locations(nodes)
    logger.info(f"Done. Took {time() - t:.2f}s")

    if Config.display_route in [4, 5, 6, 7]:
        all_nodes = [node for node in location_finder.nodes.node_map.values()
                     if not isinstance(node, MissingNode)
                     and node.cost.as_float != inf]
        display_nodes(all_nodes)

    if Config.display_route in [2, 3, 6, 7]:
        display_nodes(nodes)

    return {node.stop.stop_id: node for node in nodes}
