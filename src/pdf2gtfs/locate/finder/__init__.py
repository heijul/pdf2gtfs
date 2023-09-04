""" Subpackage, that handles the actual search for stop coordinates. """

from __future__ import annotations

import logging
from time import time
from typing import TYPE_CHECKING, TypeAlias

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.locate.finder.loc_nodes import display_nodes, MNode, Node, Nodes
from pdf2gtfs.locate.finder.location import Location
from pdf2gtfs.locate.finder.stops import Stop, Stops


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.gtfs_output.handler import GTFSHandler
    from pdf2gtfs.datastructures.gtfs_output.stop import GTFSStopEntry

logger = logging.getLogger(__name__)
DF: TypeAlias = pd.DataFrame


class LocationFinder:
    """ Tries to find the locations of the given route for all routes
    described in the given handler. """

    def __init__(self, handler: GTFSHandler, route_id: str,
                 route: list[GTFSStopEntry], df: DF) -> None:
        self.handler = handler
        self.stops: Stops = Stops(handler, route_id, route)
        self.nodes: Nodes = Nodes(df, self.stops)
        self._generate_nodes()

    def _generate_nodes(self) -> None:
        """ Creates all Node objects for all stops.

        If a stop already has a location, create a ExistingNode instead.
        """

        stop_ids = [stop.stop_id for stop in self.stops]
        existing_locs = self.handler.stops.get_existing_stops(stop_ids)
        for stop in self.stops:
            stop: Stop
            loc = Location(*existing_locs.get(stop.stop_id))
            self.nodes.create_nodes_for_stop(stop, loc)

    def find_dijkstra(self) -> list[Node]:
        """ Uses Dijkstra's algorithm to find the shortest route. """
        while True:
            node: Node = self.nodes.get_min_node()
            if node.stop.is_last:
                if not node.parent:
                    continue
                break
            node.update_neighbors()

        route = node.construct_route()
        return route


def get_first_valid_node_id(nodes: list[Node]) -> int | None:
    """ Return the index of the first node with valid location.

    If there is no node with a valid location, return -1.
    """
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


def _interpolate_intermediate_node_locations(nodes: list[Node]) -> None:
    """ Fix the locations of MissingNodes, that are between the first and last
    normal nodes. """
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
        if missing_nodes:
            # Fix missing node locations.
            loc_delta = get_loc_delta(prev, node, len(missing_nodes) + 1)
            missing_loc = prev.loc + loc_delta
            for missing_node in missing_nodes:
                missing_node.loc = missing_loc
                missing_loc += loc_delta
            missing_nodes = []
        prev = node


def _interpolate_end_node_locations(nodes: list[Node]) -> None:
    """ Interpolate the locations of MissingNodes at the end of the route.

    Basically take the last known (or interpolated) travel vector, and
    add it to the last known node location, iteratively.
    """
    first_id = get_first_valid_node_id(nodes)
    prev = nodes[first_id]
    delta = Location(0, 0)
    for node in nodes[first_id:]:
        if node.loc != Location(0, 0):
            delta = node.loc - prev.loc
        else:
            node.loc = prev.loc + delta
        prev = node


def interpolate_missing_node_locations(all_nodes: list[Node]) -> None:
    """ Update the locations of missing nodes using their neighbors locations.

    Given that at least one MissingNode is in nodes, change the location
    of the missing nodes, such that it is between the previous and next Node's
    location. If consecutive nodes are missing they will all have equal
    distance to each other and the wrapping existing nodes.
    If the starting node is a MissingNode, its location will use the vector
    between the next two nodes, after all intermediate MissingNodes' locations
    have been interpolated (analogous for the last node).
    """

    def reset_missing_node_locations() -> None:
        """ Reset the locations of all MissingNode to (0, 0). """
        for node in all_nodes:
            if not isinstance(node, MNode):
                continue
            node.loc = Location(0, 0)

    reset_missing_node_locations()

    # Cannot interpolate positions with less than two valid nodes.
    first_id = get_first_valid_node_id(all_nodes)
    msg = ("Can not interpolate the locations of the MissingNodes, "
           "because at least two valid Nodes are required.")
    if first_id in [len(all_nodes) - 1, -1]:
        logger.info(msg)
        return
    next_id = get_first_valid_node_id(all_nodes[first_id + 1:])
    if next_id == -1:
        logger.info(msg)
        return

    _interpolate_intermediate_node_locations(all_nodes)
    _interpolate_end_node_locations(all_nodes)
    # To fix the start, we simply need to reverse the nodes.
    _interpolate_end_node_locations(all_nodes[::-1])


def find_stop_nodes(handler: GTFSHandler, route_id: str,
                    route: list[GTFSStopEntry], df: DF
                    ) -> dict[str, Node]:
    """ Return the Nodes mapped to the stop ids for a list of routes. """
    msg = (f"Starting location detection for the route from "
           f"'{route[0].stop_name}' to '{route[-1].stop_name}'...")
    logger.info(msg)
    t = time()
    finder: LocationFinder = LocationFinder(
        handler, route_id, route, df.copy())
    nodes = finder.find_dijkstra()
    interpolate_missing_node_locations(nodes)
    logger.info(f"Done. Took {time() - t:.2f}s")

    if Config.display_route in [4, 5, 6, 7]:
        finder.nodes.display_all_nodes()

    if Config.display_route in [2, 3, 6, 7]:
        display_nodes(nodes)

    return {node.stop.stop_id: node for node in nodes}
