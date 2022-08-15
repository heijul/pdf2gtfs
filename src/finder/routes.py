from __future__ import annotations

import itertools
import logging
import re
import webbrowser
from operator import itemgetter
from statistics import mean

import folium
import pandas as pd

from config import Config
from finder import public_transport
from finder.cluster import Cluster, DummyCluster, DummyNode, Node
from finder.location import Location
from finder.public_transport import PublicTransport
from finder.types import Clusters, Route, Routes, StopName, StopNames
from utils import replace_abbreviations, SPECIAL_CHARS


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
    df = df.where(df["name"].str.contains(nf_regex, regex=True)).dropna()

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


def generate_clusters(df: pd.DataFrame, stops: StopNames) -> Clusters:
    def filter_df_with_stops() -> pd.DataFrame:
        chars = fr"[^a-zA-Z\d{SPECIAL_CHARS}]"
        df["name"] = df["name"].str.replace(chars, "", regex=True)

        regex = name_filter_to_regex(_create_name_filter(stops))
        return df.where(df["name"].str.contains(regex, regex=True)).dropna()

    clean_df = filter_df_with_stops()

    return {stop: _create_stop_clusters(stop, clean_df) for stop in stops}


def _create_route(
        stops: StopNames, start: Cluster, clusters: Clusters) -> Route:
    cluster_route = [start]
    for stop in stops[1:]:
        current: Cluster = cluster_route[-1]
        cluster_route.append(current.get_closest_cluster(clusters[stop]))
    return [cluster.get_closest() for cluster in cluster_route]


def generate_routes(stops: StopNames, df: pd.DataFrame) -> Routes:
    clusters = generate_clusters(df, stops)
    starts: list[Cluster] = clusters[stops[0]]
    routes: Routes = []
    for start in starts:
        route = _create_route(stops, start, clusters)
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
