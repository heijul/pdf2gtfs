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

MISSING_NODE_SCORE = 1500


class RouteFinder:
    def __init__(self, handler: GTFSHandler, stop_names: list[tuple[str, str]],
                 df: DF) -> None:
        self.handler = handler
        self.stops = Stops(handler, stop_names)
        self.nodes = Nodes(df, self.stops)

    def find_dijkstra(self) -> list[Node]:
        while True:
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


def find_stop_nodes(handler: GTFSHandler,
                    route: list[tuple[str, str]], df: DF
                    ) -> dict[str: Node]:
    logger.info("Starting location detection...")
    t = time()
    d = df.copy()
    route_finder = RouteFinder(handler, route, d.copy())
    locations = route_finder.find_dijkstra()
    update_missing_locations(locations)
    logger.info(f"Done. Took {time() - t:.2f}s")

    if Config.display_route in [4, 5, 6, 7]:
        nodes = [node for node in route_finder.nodes.node_map.values()
                 if not isinstance(node, MissingNode)
                 and node.cost.as_float != inf]
        display_nodes(nodes)

    if Config.display_route in [2, 3, 6, 7]:
        display_nodes(locations)

    return {node.stop.stop_id: node
            for node in locations if not isinstance(node, MissingNode)}
