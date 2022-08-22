from __future__ import annotations

import itertools
import logging
import re
import webbrowser
from operator import itemgetter
from statistics import mean
from typing import TYPE_CHECKING

import folium
import pandas as pd
from folium import Circle, Map

from config import Config
from finder import public_transport
from finder.cluster import Cluster, DummyCluster, DummyNode, Node
from finder.location import Location
from finder.osm_node import ExistingOSMNode, get_min_node, OSMNode
from finder.public_transport import PublicTransport
from finder.types import Clusters, Route, Route2, Routes, Routes2, StopName, StopNames
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


def _create_stop_transports_from_df(stop: StopName, df: pd.DataFrame
                                    ) -> list[PublicTransport]:
    return [public_transport.from_series(series, stop)
            for _, series in df.iterrows()]


def _group_transports_with_tolerance(
        transports: list[PublicTransport]) -> dict[Location: list[pd.Series]]:
    """ Group the list by (lat2, lon2), allowing for some tolerances. """
    def _get_group_key(keys: list[Location], loc2: Location) -> Location:
        """ Tries to find a key in keys, which is close to the given location.
        If no such key exists, return the given location. """
        return next((loc1 for loc1 in keys if loc1.close(loc2)), loc2)

    groups: dict[Location: list[PublicTransport]] = {}
    for transport in transports:
        key = _get_group_key(list(groups.keys()), transport.location)
        groups.setdefault(key, []).append(transport)

    return groups


def select_shortest_route(stops: StopNames, routes: Routes) -> Route:
    dists: list[tuple[float, Route]] = []
    for route in routes:
        if len(route) < len(stops):
            continue
        dist: float = sum([route[i].distance(route[i + 1])
                           for i in range(len(route)) if i < len(route) - 1])
        dists.append((dist, route))
    # CHECK: Probably fails if dists[a][0] == dists[b][0]
    return min(dists, key=itemgetter(0))[1]


def _create_stop_clusters(stop: StopName, df: pd.DataFrame) -> list[Cluster]:
    """ Create the clusters for a single stop. """
    name_filter = _create_single_name_filter(stop)
    nf_regex = name_filter_to_regex(name_filter)
    df = df.where(df["name"].str.contains(nf_regex, regex=True)
                  ).dropna(subset="name")

    clusters: list[Cluster] = []
    transports = _create_stop_transports_from_df(stop, df)
    grouped_transports = _group_transports_with_tolerance(transports)

    for loc, grouped_transport in grouped_transports.items():
        cluster = Cluster(stop, loc)
        for transport in grouped_transport:
            cluster.add_node(Node(cluster, transport))
        clusters.append(cluster)
    if not clusters:
        return [DummyCluster(stop)]
    return clusters


def filter_df_with_stops(df: pd.DataFrame, stops: StopNames) -> pd.DataFrame:
    chars = fr"[^a-zA-Z\d{SPECIAL_CHARS}]"
    df["name"] = df["name"].str.replace(chars, "", regex=True)

    regex = name_filter_to_regex(_create_name_filter(stops))
    return df.where(df["name"].str.contains(regex, regex=True)
                    ).dropna(subset="name")


def generate_clusters(df: pd.DataFrame, all_stops: StopNames,
                      handler: GTFSHandler) -> Clusters:
    existing_clusters = {stop.stop_name: [Cluster.from_gtfs_stop(stop)]
                         for stop in handler.stops if stop.valid}
    stops = [stop for stop in all_stops if stop not in existing_clusters]
    # All stops already have a location.
    if not stops:
        return existing_clusters
    clean_df = filter_df_with_stops(df, stops)
    clusters = {stop: _create_stop_clusters(stop, clean_df) for stop in stops}
    clusters.update(existing_clusters)
    return clusters


def _create_route(
        stops: StopNames, start: Cluster, clusters: Clusters) -> Route:
    cluster_route = [start]
    for stop in stops[1:]:
        current: Cluster = cluster_route[-1]
        cluster_route.append(current.get_closest_cluster(clusters[stop]))
    return [cluster.get_closest() for cluster in cluster_route]


def generate_routes(stops: StopNames, df: pd.DataFrame,
                    handler: GTFSHandler) -> Routes:
    if Config.display_route in [4, 5, 6, 7]:
        display_stops(df, stops)
    clusters = generate_clusters(df, stops, handler)
    if Config.display_route in [2, 3, 6, 7]:
        display_clusters(clusters)
    starts: list[Cluster] = clusters[stops[0]]
    routes: Routes = []
    for start in starts:
        route = _create_route(stops, start, clusters)
        routes.append(route)
    return routes


def _create_stop_nodes(stop: StopName, df: pd.DataFrame) -> list[OSMNode]:
    name_filter = _create_single_name_filter(stop)
    nf_regex = name_filter_to_regex(name_filter)
    df = df.where(df["name"].str.contains(nf_regex, regex=True)
                  ).dropna(subset="name")
    nodes = _create_osm_nodes_from_df(stop, df)
    return nodes


def _create_osm_nodes_from_df(stop, df) -> list[OSMNode]:
    return [OSMNode.from_series(s, stop) for _, s in df.iterrows()]


def generate_osm_nodes(df: pd.DataFrame, all_stops: StopNames,
                       handler: GTFSHandler) -> dict[StopName: list[OSMNode]]:
    existing_nodes = {stop.stop_name: [ExistingOSMNode.from_gtfsstop(stop)]
                      for stop in handler.stops if stop.valid}
    stops = [stop for stop in all_stops if stop not in existing_nodes]
    # All stops already have a location.
    if not stops:
        return existing_nodes
    clean_df = filter_df_with_stops(df, stops)
    nodes = {stop: _create_stop_nodes(stop, clean_df) for stop in stops}
    nodes.update(existing_nodes)
    return nodes


def _create_route2(stops: StopNames, end: OSMNode,
                   nodes: dict[StopName: list[OSMNode]]) -> Route2:
    def get_min_dist() -> float:
        return min([current.distance(n) for n in nodes[stop]])

    current = end
    route = [end]
    for stop in list(reversed(stops))[1:]:
        min_dist = get_min_dist()
        for node in nodes[stop]:
            node: OSMNode
            node.calculate_score(current, min_dist)
        current = get_min_node(nodes[stop], current)
        route.insert(0, current)

    return route


def generate_routes2(stops: StopNames, df: pd.DataFrame, handler: GTFSHandler
                     ) -> Routes2:
    if Config.display_route in [4, 5, 6, 7]:
        display_stops(df, stops)
    nodes = generate_osm_nodes(df, stops, handler)
    ends = nodes[stops[-1]]
    routes: Routes2 = []
    for end in ends:
        route = _create_route2(stops, end, nodes)
        routes.append(route)
    return routes


def display_route(route: Route, cluster=False, nodes=False) -> None:
    def add_other_node_markers() -> None:
        for node in entry.cluster.nodes:
            if node == entry:
                continue
            folium.Marker(tuple(node.loc), popup=f"{node.name}\n{node.loc}",
                          icon=folium.Icon(color="green")).add_to(m)

    def add_cluster_marker() -> None:
        c = entry.cluster
        folium.Marker(tuple(c.loc), popup=f"{c.stop}\n{c.loc}",
                      icon=folium.Icon(icon="cloud")).add_to(m)

    def get_map_location() -> tuple[float, float]:
        non_dummy_nodes = [node for node in route
                           if not isinstance(node, DummyNode)]
        return (mean([node.loc.lat for node in non_dummy_nodes]),
                mean([node.loc.lon for node in non_dummy_nodes]))

    # FEATURE: Add cluster/nodes to Config.
    # FEATURE: Add info about missing nodes.
    # TODO: Adjust zoom/location depending on lat-/lon-minimum
    m = folium.Map(location=get_map_location())
    for i, entry in enumerate(route):
        if isinstance(entry, DummyNode):
            continue
        if nodes:
            add_other_node_markers()
        if cluster:
            add_cluster_marker()
        loc = [entry.loc.lat, entry.loc.lon]
        folium.Marker(loc, popup=f"{entry.name}\n{loc}").add_to(m)

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


def display_clusters(clusters_dict: Clusters) -> None:
    def add_clusters_to_map(c: Cluster) -> None:
        for n in c.nodes:
            Circle(radius=1, location=tuple(n.loc),
                   color="crimson", fill=False, tooltip=n.name).add_to(m)
        Circle(radius=Config.cluster_radius, location=tuple(c.loc),
               color="lime", fill=False, tooltip=c.stop).add_to(m)

    m = Map(location=(48, 8), tiles="CartoDB positron")
    for clusters in clusters_dict.values():
        for cluster in clusters:
            add_clusters_to_map(cluster)

    path = str(Config.output_dir.joinpath("clusters.html"))
    m.save(path)
    webbrowser.open_new_tab(path)


def display_stops(df: pd.DataFrame, stops: list[str]) -> None:
    def df_to_loc_list(clean_df: pd.DataFrame) -> list[tuple[int, int]]:
        locs = []
        for _, row in clean_df.iterrows():
            locs.append((row["lat"], row["lon"]))
        return locs

    list_to_map(df_to_loc_list(filter_df_with_stops(df, stops)))
