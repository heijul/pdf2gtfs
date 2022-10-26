""" Provides functions and classes to detect the location of stops. """

from __future__ import annotations

import logging
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
        self.nodes: Nodes = Nodes(df, self.stops)

    def find_dijkstra(self) -> list[Node]:
        """ Uses Dijkstra's algorithm to find the shortest route. """
        while True:
            node: Node = self.nodes.pop()
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
            # Only create MissingNodes for neighbors of nodes
            #  without any true neighbors or children.
            if not node.has_children and not has_neighbors:
                logger.info(f"Created missing childnode for {node}")
                self.nodes.create_missing_neighbor_for_node(node)
            node.visited = True

        route = node.construct_route()
        return route


def update_missing_locations(
        all_nodes: list[Node], force: bool = False) -> None:
    """ Interpoplate the location of missing nodes using their neighbors.

    Given that at least one MissingNode is in nodes, change the location
    of the missing nodes, such that it is between the previous and next Node's
    location. If consecutive nodes are missing they will all have equal
    distance to each other and the wrapping nodes.
    Will not update locations of MissingNodes at the start. """

    def reset_missing_node_locations() -> None:
        """ Reset the locations of all MissingNode to 0, 0. """
        for node in all_nodes:
            if not isinstance(node, MissingNode):
                continue
            node.loc = Location(0, 0)

    def get_first_valid_node_id(nodes: list[Node]) -> int | None:
        """ Return the index of the first node with valid location. """
        for i in range(len(nodes)):
            if nodes[i].loc != Location(0, 0):
                return i
        return -1

    def get_loc_delta(n1: Node, n2: Node, div: int = 1) -> Location:
        """ Return the vector to get from n1 to n2.

        If div is given, divide both latitude and longitude by it.
        """
        lat_diff = (n2.loc.lat - n1.loc.lat) / div
        lon_diff = (n2.loc.lon - n1.loc.lon) / div
        return Location(lat_diff, lon_diff)

    def fix_intermediate_node_locations(nodes: list[Node]) -> None:
        """ Fix the locations of MissingNodes, not at the start or end. """
        idx = get_first_valid_node_id(nodes)
        prev = nodes[idx]
        missing_nodes = []
        while True:
            if idx == len(nodes):
                break
            node = nodes[idx]
            idx += 1
            # Current node has invalid location.
            if node.loc == Location(0, 0):
                missing_nodes.append(node)
                continue
            # Current node has valid location.
            if not missing_nodes:
                prev = node
                continue
            # Fix missing node locations.
            loc_delta = get_loc_delta(prev, node, len(missing_nodes) + 1)
            missing_loc = prev.loc + loc_delta
            for missing_node in missing_nodes:
                missing_node.loc = missing_loc
                missing_loc += loc_delta
            missing_nodes = []

    def fix_bordering_node_locations(nodes: list[Node]) -> None:
        """ Fix the locations of MissingNodes at the start or end.

        Basically take the last known (or interpolated) travel vector, and
        add it to the last known node location, iteratively.
        """
        idx = get_first_valid_node_id(nodes)
        if idx == 0:
            return

        loc_delta = get_loc_delta(nodes[idx + 1], nodes[idx])
        prev: Node = nodes[idx]
        while True:
            idx -= 1
            node = nodes[idx]
            node.loc = prev.loc + loc_delta
            prev = node
            if idx == 0:
                break

    if force:
        reset_missing_node_locations()

    # Cannot interpolate positions with less than two valid nodes.
    if get_first_valid_node_id(all_nodes) in [len(all_nodes), -1]:
        return

    fix_intermediate_node_locations(all_nodes)
    # Fix start/end.
    fix_bordering_node_locations(all_nodes)
    fix_bordering_node_locations(list(reversed(all_nodes)))


def find_stop_nodes(handler: GTFSHandler,
                    route: list[tuple[str, str]], df: DF
                    ) -> dict[str: Node]:
    """ Return the Nodes mapped to the stop ids for a list of routes. """
    logger.info("Starting location detection...")
    t = time()
    finder: LocationFinder = LocationFinder(handler, route, df.copy())
    nodes = finder.find_dijkstra()
    update_missing_locations(nodes)
    logger.info(f"Done. Took {time() - t:.2f}s")

    if Config.display_route in [4, 5, 6, 7]:
        finder.nodes.display_all_nodes()

    if Config.display_route in [2, 3, 6, 7]:
        display_nodes(nodes)

    return {node.stop.stop_id: node for node in nodes}
