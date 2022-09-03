from __future__ import annotations

import itertools
import logging
import re
import webbrowser
from operator import attrgetter
from statistics import mean, StatisticsError
from typing import Callable, TYPE_CHECKING

import folium
import pandas as pd

from config import Config
from finder.osm_node import DummyOSMNode, ExistingOSMNode, get_min_node, OSMNode, Route3
from finder.types import Route2, StopName, StopNames
from utils import replace_abbreviations, SPECIAL_CHARS

if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler


logger = logging.getLogger(__name__)


def _get_permutations(name) -> StopNames:
    # TODO: Use \b or \B instead
    splits = re.split(r" *[,/ ] *", name)
    return [" ".join(perm) for perm in itertools.permutations(splits)]


def _create_single_name_filter(name: StopName) -> StopNames:
    name = name.casefold().lower()
    full_name = replace_abbreviations(name)
    return _get_permutations(full_name)


def _create_name_filter(names: StopNames) -> StopNames:
    return [name_filter for name in names
            for name_filter in _create_single_name_filter(name)]


def name_filter_to_regex(names: StopNames) -> str:
    def name_to_regex(_name: str) -> str:
        regex = ""
        for char in _name:
            if re.search(char_range, char, re.IGNORECASE):
                regex += re.escape(char) + "?"
                continue
            regex += re.escape(char)
        return fr"\b{regex}"

    char_range = fr"[^a-zA-Z\d{SPECIAL_CHARS}]"
    re_names = []
    for name in names:
        splits = re.split(fr"\b| |{char_range}", name)
        splits = [split.strip() for split in splits if split.strip()]
        perms = _get_permutations(" ".join(splits))
        re_names += list(map(name_to_regex, perms))

    return "|".join(set(re_names))


def filter_df_with_stops(df: pd.DataFrame, stops: StopNames) -> pd.DataFrame:
    chars = fr"[^a-zA-Z\d{SPECIAL_CHARS}]"
    df["names"] = df["names"].str.replace(chars, "", regex=True)

    regex = name_filter_to_regex(_create_name_filter(stops))
    return df.where(df["names"].str.contains(regex, regex=True)).dropna()


def _create_stop_nodes(stop: StopName, df: pd.DataFrame) -> list[OSMNode]:
    name_filter = _create_single_name_filter(stop)
    nf_regex = name_filter_to_regex(name_filter)
    df = df.where(df["names"].str.contains(nf_regex, regex=True)).dropna()
    nodes = _create_osm_nodes_from_df(stop, df)
    return nodes


def _create_osm_nodes_from_df(stop, df) -> list[OSMNode]:
    return [OSMNode.from_series(s, stop) for _, s in df.iterrows()]


def generate_osm_nodes(
        df: pd.DataFrame, all_stops: StopNames, handler: GTFSHandler
        ) -> dict[StopName: tuple[list[OSMNode], bool]]:
    existing_nodes = {stop.stop_name: [ExistingOSMNode.from_gtfsstop(stop)]
                      for stop in handler.stops if stop.valid}
    stops = [stop for stop in all_stops if stop not in existing_nodes]
    # All stops already have a location.
    if not stops:
        return existing_nodes
    node_gen = create_node_generator(df, stops, False)
    nodes = {stop: (node_gen(stop), False) for stop in stops}
    nodes.update(existing_nodes)
    return nodes


def _create_route2(stops: StopNames, end: OSMNode,
                   nodes: dict[StopName: list[OSMNode]]) -> Route2:
    def get_min_dist() -> float:
        return min([current.distance(n) for n in nodes[stop]], default=-1)

    current = end
    route = [end]
    for stop in list(reversed(stops))[1:]:
        min_dist = get_min_dist()
        if min_dist < 0:
            # CHECK: Maybe current needs to be updated?!
            route.insert(0, DummyOSMNode(stop))
            continue
        for node in nodes[stop]:
            node: OSMNode
            node.calculate_score(current, min_dist)
        current = get_min_node(nodes[stop], current)
        route.insert(0, current)

    return route


def create_node_generator(
        df: pd.DataFrame, stops: StopNames, extended_search: bool = False
        ) -> Callable[[str], list[OSMNode]]:
    def get_clean_df() -> pd.DataFrame:
        return filter_df_with_stops(df, stops)

    def node_generator(stop: str) -> list[OSMNode]:
        # Ensure get_clean_df is only run when actually needed, instead of
        # when creating the generator.
        nonlocal clean_df

        if clean_df is None:
            clean_df = get_clean_df()

        nodes = _create_stop_nodes(stop, clean_df)
        return nodes

    def node_generator_extended(stop: str) -> list[OSMNode]:
        # TODO: Implement this.
        return node_generator(stop)

    clean_df = None
    return node_generator_extended if extended_search else node_generator


def generate_routes2(stops: StopNames, df: pd.DataFrame, handler: GTFSHandler
                     ) -> list[Route3]:
    if Config.display_route in [2, 3]:
        display_stops(df, stops)
    nodes = generate_osm_nodes(df, stops, handler)
    ends = sorted(nodes[stops[-1]][0], key=attrgetter("loc.lat"))
    routes = []
    node_generator = create_node_generator(df, stops, True)
    for end in ends:
        route = Route3.from_nodes(stops, end, nodes, node_generator)
        routes.append(route)
    return routes


def display_route2(route: Route3) -> None:
    def get_map_location() -> tuple[float, float]:
        non_dummy_nodes = [n for n in route.nodes
                           if not isinstance(n, DummyOSMNode)]
        try:
            return (mean([n.loc.lat for n in non_dummy_nodes]),
                    mean([n.loc.lon for n in non_dummy_nodes]))
        except StatisticsError:
            return 0, 0

    # FEATURE: Add cluster/nodes to Config.
    # FEATURE: Add info about missing nodes.
    # TODO: Adjust zoom/location depending on lat-/lon-minimum
    location = get_map_location()
    if location == (0, 0):
        logger.warning("Nothing to display, route is empty.")
        return
    m = folium.Map(location=location)
    for i, node in enumerate(route.nodes):
        if isinstance(node, DummyOSMNode):
            continue
        loc = [node.loc.lat, node.loc.lon]
        folium.Marker(loc, popup=f"{node.name}\n{loc}").add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


def list_to_map(values, name="positions.html") -> None:
    loc = mean([a for a, _ in values]), mean([b for _, b in values])
    m = folium.Map(location=loc, tiles="CartoDB positron")
    for node in values:
        folium.CircleMarker(radius=5, location=node, color="crimson",
                            fill=True, fill_color="lime").add_to(m)
    path = str(Config.output_dir.joinpath(name))
    m.save(path)
    webbrowser.open_new_tab(path)


def display_stops(df: pd.DataFrame, stops: list[str]) -> None:
    def df_to_loc_list(clean_df: pd.DataFrame) -> list[tuple[int, int]]:
        locs = []
        for _, row in clean_df.iterrows():
            locs.append((row["lat"], row["lon"]))
        return locs

    list_to_map(df_to_loc_list(filter_df_with_stops(df, stops)))
