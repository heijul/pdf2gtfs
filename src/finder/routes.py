from __future__ import annotations

import itertools
import webbrowser
from operator import itemgetter
from statistics import mean
from typing import TypeAlias
import re

import pandas as pd
import folium

from config import Config
from finder import public_transport
from finder.cluster import Cluster2, Node2
from finder.public_transport import PublicTransport
from utils import normalize_name, replace_abbreviations


class Route2:
    stops: list[StopName]
    start: Cluster2

    def __init__(self, stops: list[StopName]) -> None:
        self.stops = stops

    def create(self, start: Cluster2,
               clusters: dict[StopName: list[Cluster2]]
               ) -> None:
        self.start = start
        current = self.start
        for stop in self.stops[1:]:
            # TODO: Need to check if clusters[stop] is empty
            current.next = clusters[stop]
            current = current.next

    def find_shortest_path(self):
        path: list[Node2] = []
        current = self.start
        while current is not None:
            path.append(current.get_closest())
            current = current.next
        return path

    def find_shortest_path2(self):
        path: list[Node2] = []
        current = self.start
        while current is not None:
            path.append(current.get_closest())
            current = current.next
        return path


StopName: TypeAlias = str
CStopName: TypeAlias = str
Location: TypeAlias = tuple[float, float]
Clusters: TypeAlias = dict[StopName: list[Cluster2]]


def _get_permutations(name) -> list[StopName]:
    splits = name.casefold().lower().strip().split(" ")
    return [" ".join(perm) for perm in itertools.permutations(splits)]


def _create_single_name_filter(name: StopName) -> list[StopName]:
    name = name.casefold().lower()
    name_filter = _get_permutations(name.casefold().lower())
    full_name = replace_abbreviations(name)
    if name != full_name:
        name_filter += _get_permutations(full_name)
    return name_filter


def _create_name_filter(names: list[StopName]):
    # FEATURE: Turn cf_names into dict with name -> [split names],
    #  sorted by edit distance to name
    name_filter = []
    for name in list(names):
        name_filter += _create_single_name_filter(name)
    return list(set(name_filter))


def name_filter_to_regex(name_filter: list[StopName]):
    re_names = []
    # TODO: Config
    special_char_ranges = "\u00C0-\u00D6\u00D9-\u00F6\u00F8-\u00FF"
    char_range = fr"[^a-zA-Z{special_char_ranges}]"
    # Only match a single word splitting char. (A-/Bstraße) will not be split.
    pattern = rf"\b{char_range}(?!{char_range})"
    for name in name_filter:
        re_name = r"\b(?:" + r").\b(?:".join(re.split(pattern, name)) + ")"
        re_names.append(re_name)
    return "|".join(re_names)


def _filter_df(df: pd.DataFrame, name_filter: list[StopName]):
    nf_regex = name_filter_to_regex(name_filter)
    return df.where(df["name"].str.contains(nf_regex, regex=True)).dropna()


def _create_clusters2(stops: list[StopName], df: pd.DataFrame) -> Clusters:
    def by_name(entry_id):
        _entry = df.loc[entry_id]
        return normalize_name(_entry["name"]).casefold().lower()

    grouped = df.groupby(by_name, axis=0)
    clusters = {}
    for stop in stops:
        clusters[stop] = []
        group = grouped.get_group(stop.casefold().lower())

        clustered_groups = _group_df_with_tolerance(group)
        for loc, values in clustered_groups.items():
            cluster = Cluster2(*loc)
            for value in values:
                Node2(cluster, value["name"], value["lat"], value["lon"])
            cluster.adjust_location()
            clusters[stop].append(cluster)
    return clusters


def _create_transports(df: pd.DataFrame, stops: list[StopName]
                       ) -> list[PublicTransport]:
    transports = []
    for _, entry in df.iterrows():
        transports.append(public_transport.from_series(entry))
    for stop in stops:
        name_filter = _create_single_name_filter(stop)
        nf_regex = name_filter_to_regex(name_filter)
        for transport in transports:
            if transport.stop:
                continue
            if transport.name == stop.casefold().lower():
                transport.set_stop(stop, True)
            elif re.match(nf_regex, transport.name):
                transport.set_stop(stop, False)

    return transports


def _create_clusters(stops: list[StopName], df: pd.DataFrame) -> Clusters:
    transports = _create_transports(df, stops)
    clusters = {}
    for stop in stops:
        clusters[stop] = []
        stop_transports = [t for t in transports if t.stop == stop]
        grouped_transports = _group_transports_with_tolerance(stop_transports)
        for loc, grouped_transport in grouped_transports.items():
            cluster = Cluster2(*loc)
            for transport in grouped_transport:
                loc = transport.location.lat, transport.location.lon
                cluster.add_node(Node2(cluster, transport, *loc))
            clusters[stop].append(cluster)
        if not clusters[stop]:
            print("a")
    return clusters


def _group_transports_with_tolerance(transports: list[PublicTransport]
                                     ) -> dict[Location: list[pd.Series]]:
    """ Group the list by (lat2, lon2), allowing for some tolerances. """
    def _try_create_group(lat2: float, lon2: float):
        for (lat1, lon1), _group in groups.items():
            if abs(lat1 - lat2) <= tolerance and abs(lon1 - lon2) <= tolerance:
                return _group
        groups[(lat2, lon2)] = []
        return groups[(lat2, lon2)]

    tolerance = 0.008
    groups: dict[Location: list[pd.Series]] = {}
    for transport in transports:
        loc = (transport.location.lat, transport.location.lon)
        _try_create_group(*loc).append(transport)
    return groups


def _group_df_with_tolerance(df: pd.DataFrame
                             ) -> dict[Location: list[pd.Series]]:
    """ Group the dataframe by (name, lat2, lon2), allowing tolerances. """
    def _try_create_group(lat2: float, lon2: float):
        for (lat1, lon1), _group in groups.items():
            if abs(lat1 - lat2) <= tolerance and abs(lon1 - lon2) <= tolerance:
                return _group
        groups[(lat2, lon2)] = []
        return groups[(lat2, lon2)]

    tolerance = 0.008
    groups: dict[Location: list[pd.Series]] = {}
    for row_id, row in df.iterrows():
        loc = (row["lat"], row["lon"])
        _try_create_group(*loc).append(row)
    return groups


def _create_routes(stops: list[StopName], clusters: Clusters
                   ) -> list[list[Node2]]:
    starts: list[Cluster2] = clusters[stops[0]]
    routes: list[list[Node2]] = []
    for start in starts:
        route = Route2(stops)
        route.create(start, clusters)
        routes.append(route.find_shortest_path())
    return routes


def _create_routes2(stops: list[StopName], clusters: Clusters
                    ) -> list[list[Node2]]:
    starts: list[Cluster2] = clusters[stops[0]]
    routes: list[list[Node2]] = []
    for start in starts:
        route = Route2(stops)
        route.create(start, clusters)
        routes.append(route.find_shortest_path2())
    return routes


def display_route2(names: list[StopName],
                   route: list[Node2], cluster=False, nodes=False) -> None:
    def add_other_node_markers():
        for node in entry.cluster.nodes:
            if node == entry:
                continue
            _loc = [node.lat, node.lon]
            folium.Marker(_loc, popup=f"{node.name}\n{_loc}",
                          icon=folium.Icon(color="green")).add_to(m)

    def add_cluster_marker():
        _loc = [entry.cluster.lat, entry.cluster.lon]
        folium.Marker(_loc, popup=f"{names[i]}\n{_loc}",
                      icon=folium.Icon(icon="cloud")).add_to(m)

    # FEATURE: Add cluster/nodes to Config.
    location = mean([e.lat for e in route]), mean([e.lon for e in route])
    m = folium.Map(location=location)
    for i, entry in enumerate(route):
        if nodes:
            add_other_node_markers()
        if cluster:
            add_cluster_marker()
        loc = [entry.lat, entry.lon]
        folium.Marker(loc, popup=f"{entry.name}\n{loc}").add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


def select_shortest_route(stops: list[StopName], routes: list[list[Node2]]
                          ) -> list[Node2]:
    dists: list[tuple[float, list[Node2]]] = []
    for route in routes:
        if len(route) < len(stops):
            continue
        dist: float = sum([route[i].distance(route[i + 1])
                           for i in range(len(route)) if i < len(route) - 1])
        dists.append((dist, route))
    # CHECK: Probably fails if dists[a][0] == dists[b][0]
    return min(dists, key=itemgetter(0))[1]


def generate_routes(raw_df: pd.DataFrame, stops: list[StopName]
                    ) -> list[list[Node2]]:
    df = _filter_df(raw_df, _create_name_filter(stops))
    clusters = _create_clusters2(stops, df)
    routes: list[list[Node2]] = _create_routes(stops, clusters)
    return routes


def generate_routes2(raw_df: pd.DataFrame, stops: list[StopName]
                     ) -> list[list[Node2]]:
    df = _filter_df(raw_df, _create_name_filter(stops))
    clusters = _create_clusters(stops, df)
    routes: list[list[Node2]] = _create_routes2(stops, clusters)
    return routes
