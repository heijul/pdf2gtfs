""" Subpackage to detect the coordinates of each stop. """

from __future__ import annotations

import logging
import re
from math import inf
from time import time
from typing import TYPE_CHECKING, TypeAlias

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.stop import GTFSStopEntry
from pdf2gtfs.locate.finder import find_stop_nodes, update_missing_locations
from pdf2gtfs.locate.finder.loc_nodes import display_nodes, MNode, Node
from pdf2gtfs.locate.finder.osm_values import get_all_cat_scores
from pdf2gtfs.locate.osm_fetcher import CAT_KEYS, OPT_KEYS, OSMFetcher
from pdf2gtfs.utils import normalize_name


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.gtfs_output.handler import GTFSHandler

logger = logging.getLogger(__name__)

DF: TypeAlias = pd.DataFrame


def search_locations_for_all_routes(
        handler: GTFSHandler, df: DF) -> dict[str: list[Node]]:
    """ Locate the stop nodes for each route individually. """
    routes = get_unique_routes(handler)
    nodes: dict[str: list[Node]] = {}
    for route_id, route in routes.items():
        stop_nodes = find_stop_nodes(handler, route_id, route, df)
        for stop_id, node in stop_nodes.items():
            nodes.setdefault(stop_id, []).append(node)
    return nodes


def find_location_nodes(gtfs_handler: GTFSHandler) -> dict[str: Node]:
    """ Return a dictionary of all stops and their locations. """

    fetcher = OSMFetcher()
    dataframe = fetcher.fetch()
    if dataframe.empty:
        return {}
    df = prepare_df(gtfs_handler.get_used_stops(), dataframe)

    logger.info("Searching for the stop locations of each route.")
    t = time()

    route_stop_nodes = search_locations_for_all_routes(gtfs_handler, df)
    best_nodes = select_best_nodes(route_stop_nodes)
    logger.info(f"Done. Took {time() - t:.2f}s")

    update_missing_locations(list(best_nodes.values()), True)
    if Config.display_route in [1, 3, 5, 7]:
        display_nodes(list(best_nodes.values()))
    return best_nodes


def prepare_df(gtfs_stops: list, raw_df: DF) -> DF:
    """ Prefilter the DataFrame and score the names and nodes. """
    # Filter the dataframe.
    logger.info("Splitting DataFrame based on stop names...")
    t = time()
    stops = [(stop.stop_id, stop.stop_name) for stop in gtfs_stops]
    prefiltered_df = prefilter_df([name for _, name in stops], raw_df)
    # Calculate name score.
    df = add_extra_columns(stops, prefiltered_df)
    logger.info(f"Done. Took {time() - t:.2f}s")

    logger.info(f"Calculating location costs based on the selected "
                f"routetype '{Config.gtfs_routetype}'...")
    t = time()
    # Calculate node score.
    full_df = node_score_strings_to_int(df)
    full_df["opts_value"] = opt_keys_to_int(full_df[OPT_KEYS])
    df.loc[:, "node_cost"] = get_node_cost(full_df)
    df = df.loc[:, ["lat", "lon", "names",
                    "node_cost", "stop_id", "idx", "name_cost"] + OPT_KEYS]
    logger.info(f"Done. Took {time() - t:.2f}s")

    return df


def get_unique_routes(handler: GTFSHandler) -> dict[str: list[GTFSStopEntry]]:
    """ Return a list of unique routes.

    The list contains unique combinations of stops occuring in the tables.
    If one combination is contained by another, only return the containing one.
    """

    def route_is_contained(contained_route_id: str) -> bool:
        """ Return if the route is contained by any other. """

        def _route_contains_stops(
                container: list[GTFSStopEntry], stops: list[GTFSStopEntry]
                ) -> bool:
            """ Return if all stops are in container, in the right order. """
            # No need to check for length, as r1 has at least the length of r2.
            # Copy to prevent changing the list using pop.
            stops = list(stops)
            for container_stop in container:
                if stops and stops[0] == container_stop:
                    stops.pop(0)

            return not stops

        route_stops = handler.get_stops_of_route(contained_route_id)

        for existing_route_id in routes:
            existing_stops = handler.get_stops_of_route(existing_route_id)
            if _route_contains_stops(existing_stops, route_stops):
                return True

        return False

    route_ids = handler.get_sorted_route_ids()

    routes = {}
    for route_id in route_ids:
        if route_is_contained(route_id):
            continue
        routes[route_id] = handler.get_stops_of_route(route_id)

    return routes


def _create_stop_regex(stop: str) -> str:
    name = normalize_name(stop)
    regex = " ".join([rf"\b{re.escape(word)}\b" for word in name.split(" ")])
    return regex


def add_extra_columns(stops: list[tuple[str, str]], full_df: DF) -> DF:
    """ Add extra columns (name_cost, stop_id, idx) to the df. """

    def filter_df_by_stop(stop: str) -> DF:
        """ Return a filtered df, which only contains entries of stop. """
        regex = _create_stop_regex(stop)
        df = full_df[full_df["names"].str.contains(regex, regex=True)]
        return df.copy()

    def calculate_name_cost(names: list[str]) -> int:
        """ Calculate the minimum approximate edit distance to the stop.

        Because we know all names contain the stop's words, we simply
        calculate the difference in length, ignoring spaces.
        """
        name_lengths = [len(name.replace(" ", "")) for name in names]
        return min([abs(stop_length - length) for length in name_lengths])

    dfs = []
    for stop_id, stop_name in stops:
        filtered_df = filter_df_by_stop(stop_name)
        stop_length = len(normalize_name(stop_name).replace(" ", ""))
        if filtered_df.empty:
            filtered_df[["name_cost", "stop_id", "idx"]] = None
            dfs.append(filtered_df)
            continue
        name_df = filtered_df["names"].str.split("|", regex=False)
        filtered_df.loc[:, "name_cost"] = name_df.map(calculate_name_cost)
        filtered_df.loc[:, "stop_id"] = stop_id
        filtered_df.loc[:, "idx"] = filtered_df.index
        dfs.append(filtered_df)
    return pd.concat(dfs, ignore_index=True)


def prefilter_df(stops: list[str], full_df: DF) -> DF:
    """ Filter the full_df, such that each entry contains a
    normalized stop name. """

    regexes = [_create_stop_regex(stop) for stop in stops]
    unique_regex: str = "|".join(set(regexes))
    df = full_df[full_df["names"].str.contains(unique_regex, regex=True)]
    return df.copy()


def node_score_strings_to_int(raw_df: pd.DataFrame) -> pd.DataFrame:
    """ Translate the OSM-key columns to int.

    Change the values of KEYS_OPTIONAL (i.e. the keys used to calculate
    the node score) in df, with its integer value, depending on the routetype.
    """

    def _get_score(value: str) -> float:
        if value in bad:
            return bad_value
        try:
            return good[value] * 5
        except KeyError:
            return 20

    bad_value = inf
    # Apply cat scores
    goods, bads = get_all_cat_scores()
    df = raw_df.copy()
    for key in CAT_KEYS:
        good = goods.get(key, {})
        bad = bads.get(key, {})
        df[key] = df[key].apply(_get_score)

    return df


def opt_keys_to_int(full_df: pd.DataFrame) -> pd.DataFrame:
    def evaluate_ifopt(value: str) -> int:
        return 5 * int(value == "")

    def evaluate_wheelchair(value: str) -> int:
        return 3 * int(value not in ["yes", "no", "limited"])

    opts_value = (full_df["ref_ifopt"].apply(evaluate_ifopt)
                  + full_df["wheelchair"].apply(evaluate_wheelchair))
    return opts_value


def get_node_cost(full_df: pd.DataFrame) -> pd.DataFrame:
    """ Calculate the integer score based on KEYS_OPTIONAL. """
    # Penalize nodes with fewer optional keys.
    min_cat = full_df[CAT_KEYS].min(axis=1)
    node_cost = (min_cat + full_df["opts_value"]) ** 2 // 20
    return node_cost


def select_best_nodes(stops_nodes: dict[str: list[Node]]) -> dict[str: Node]:
    """ Select the nodes for every stop. """

    def select_best_node_of_stop() -> Node:
        """ Select the best node for a specific Stop. """
        nodes = [n for n in stop_nodes if not isinstance(n, MNode)]
        missing = [n for n in stop_nodes if isinstance(n, MNode)]
        if not nodes:
            return missing[0]
        nodes_unique = set(nodes)
        nodes_count = {n: nodes.count(n) for n in nodes_unique}
        node_with_max_count = max(nodes, key=nodes_count.get)
        return node_with_max_count

    best_nodes: dict[str: Node] = {}
    for stop_id, stop_nodes in stops_nodes.items():
        best_nodes[stop_id] = select_best_node_of_stop()
    return best_nodes
