from __future__ import annotations

import itertools
import logging
import webbrowser
from operator import itemgetter
from statistics import mean
import re

import pandas as pd
import folium

from config import Config
from finder import public_transport
from finder.cluster import Cluster2, Node2, DummyCluster2
from finder.public_transport import PublicTransport, Location
from finder.types import StopName, Clusters, StopNames, Routes, Route
from utils import replace_abbreviations, SPECIAL_CHARS


logger = logging.getLogger(__name__)


class Route2:
    stops: StopNames
    start: Cluster2

    def __init__(self, stops: StopNames) -> None:
        self.stops = stops

    def create(self, start: Cluster2, clusters: Clusters) -> None:
        self.start = start
        current = self.start
        for stop in self.stops[1:]:
            # TODO: Need to check if clusters[stop] is empty
            current.next = clusters[stop]
            current = current.next

    def find_shortest_path2(self):
        path: Route = []
        current = self.start
        while current is not None:
            path.append(current.get_closest())
            current = current.next
        return path


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


def name_filter_to_regex2(names: StopNames) -> str:
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


def _create_stop_clusters(stop: StopName, df: pd.DataFrame) -> list[Cluster2]:
    """ Create the clusters for a single stop. """
    name_filter = _create_single_name_filter(stop)
    nf_regex = name_filter_to_regex2(name_filter)
    df = df.where(df["name"].str.contains(nf_regex, regex=True)).dropna()

    clusters: list[Cluster2] = []
    transports = _create_stop_transports_from_df(stop, df)
    grouped_transports = _group_transports_with_tolerance(transports)

    for loc, grouped_transport in grouped_transports.items():
        cluster = Cluster2(stop, loc)
        for transport in grouped_transport:
            cluster.add_node(Node2(cluster, transport))
        clusters.append(cluster)
    if not clusters:
        return [DummyCluster2(stop)]
    return clusters


def generate_clusters(df: pd.DataFrame, stops: StopNames) -> Clusters:
    def filter_df_with_stops():
        chars = fr"[^a-zA-Z\d{SPECIAL_CHARS}]"
        df["name"] = df["name"].str.replace(chars, "", regex=True)

        regex = name_filter_to_regex2(_create_name_filter(stops))
        return df.where(df["name"].str.contains(regex, regex=True)).dropna()

    clean_df = filter_df_with_stops()

    return {stop: _create_stop_clusters(stop, clean_df) for stop in stops}


def generate_routes(stops: StopNames, df: pd.DataFrame) -> Routes:
    clusters = generate_clusters(df, stops)
    starts: list[Cluster2] = clusters[stops[0]]
    routes: Routes = []
    for start in starts:
        route = Route2(stops)
        route.create(start, clusters)
        routes.append(route.find_shortest_path2())
    return routes


def display_route2(route: Route, cluster=False, nodes=False) -> None:
    def add_other_node_markers():
        for node in entry.cluster.nodes:
            if node == entry:
                continue
            folium.Marker(tuple(node.loc), popup=f"{node.name}\n{node.loc}",
                          icon=folium.Icon(color="green")).add_to(m)

    def add_cluster_marker():
        c = entry.cluster
        folium.Marker(tuple(c.loc), popup=f"{c.stop}\n{c.loc}",
                      icon=folium.Icon(icon="cloud")).add_to(m)

    # FEATURE: Add cluster/nodes to Config.
    location = (mean([e.loc.lat for e in route]),
                mean([e.loc.lon for e in route]))
    m = folium.Map(location=location)
    for i, entry in enumerate(route):
        if nodes:
            add_other_node_markers()
        if cluster:
            add_cluster_marker()
        loc = [entry.loc.lat, entry.loc.lon]
        folium.Marker(loc, popup=f"{entry.name}\n{loc}").add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))
