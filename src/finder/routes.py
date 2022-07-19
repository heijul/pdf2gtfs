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
from finder.cluster import Cluster2, Node2, distance
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
    splits = re.split(r" *[,/ ] *", name)
    return [" ".join(perm) for perm in itertools.permutations(splits)]


def _create_single_name_filter(name: StopName) -> list[StopName]:
    name = name.casefold().lower()
    name_filter = _get_permutations(name.casefold().lower())
    full_name = replace_abbreviations(name)
    if name != full_name:
        name_filter += _get_permutations(full_name)
    return name_filter


def _create_single_name_filter_extended(name: StopName) -> list[StopName]:
    return _create_extended_name_filter([name])


def _create_name_filter(names: list[StopName]):
    # TODO: Turn cf_names into dict with name -> [split names], sorted by
    #  edit distance to name
    name_filter = []
    for name in list(names):
        name_filter += _create_single_name_filter(name)
    return list(set(name_filter))


def _create_extended_name_filter(names: list[StopName]):
    base_name_filter = _create_name_filter(names)
    name_filter = []
    for name in list(base_name_filter):
        splits = re.split(r" *[,/ ] *", name)
        # Abbreviations never occur on their own.
        name_filter += [split for split in splits
                        if split and split not in Config.name_abbreviations]
    return list(set(name_filter))


def name_filter_to_regex(name_filter: list[StopName]):
    re_names = []
    # TODO: Config
    special_char_ranges = "\u00C0-\u00D6\u00D9-\u00F6\u00F8-\u00FF"
    char_range = fr"[^a-zA-Z{special_char_ranges}]"
    # Only match a single word splitting char. (A-/Bstraße) will not be split.
    pattern = rf"\b{char_range}(?!{char_range})"
    for name in name_filter:
        split = [s for s in re.split(pattern, name) if s]
        re_name = r"\b(?:" + r").\b(?:".join(map(re.escape, split)) + ")"
        re_names.append(re_name)
    return "|".join(re_names)


def _filter_df(df: pd.DataFrame, name_filter: list[StopName]):
    nf_regex = name_filter_to_regex(name_filter)
    return df.where(df["name"].str.contains(
        nf_regex, flags=re.IGNORECASE, regex=True)).dropna()


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


def __create_regex(names):
    regex = "|".join([rf"\b{name}\b" for name in names])
    if len(names) == 1:
        return regex
    perms = itertools.permutations(names)
    perm_regex = "|".join([r"\b" + r".*?\b".join(n) for n in perms])
    return perm_regex + "|" + regex


def __create_transports(df, regex):
    df_part = df.where(
        df["name"].str.contains(regex, flags=re.IGNORECASE, regex=True))
    return [public_transport.from_series(e)
            for _, e in df_part.dropna().iterrows()]


def _create_transports(df: pd.DataFrame, stops: list[StopName]
                       ) -> list[PublicTransport]:
    transports = []
    for stop in stops:
        name_filter = _create_single_name_filter(stop)
        name_filter_regex = name_filter_to_regex(name_filter)
        stop_regex = __create_regex(name_filter)
        stop_transports = __create_transports(df, name_filter_regex)
        for transport in stop_transports:
            transport.set_stop(stop, False)
        transports += stop_transports

    return transports


def _create_transports_extended(df: pd.DataFrame, stops: list[StopName]
                                ) -> list[PublicTransport]:
    def match_span(regex: str, name: str) -> tuple[int, int]:
        match = re.match(regex, name)
        return (0, 0) if match is None else match.span()

    def match_length(span: tuple[int, int]):
        return len(range(*span))

    def better_match(new_regex: str, _old_regex: str, name: str) -> bool:
        """ Return if new_regex matches name better than old_regex. """
        old_match_span = match_span(_old_regex, name)
        new_match_span = match_span(new_regex, name)
        old_length = match_length(old_match_span)
        new_length = match_length(new_match_span)
        if old_length != new_length:
            return new_length > old_length
        # Same match length but new has an earlier start.
        return new_match_span[0] < old_match_span[0]

    transports = []
    #for _, entry in df.iterrows():
    #    transports.append(public_transport.from_series(entry))
    #    transports[-1].name2 = re.sub(" *[,/ ] *", " ", transports[-1].name)

    for stop in stops:
        name_filter = _create_single_name_filter_extended(stop)
        stop_regex = name_filter_to_regex(name_filter)
        stop_regex = __create_regex(name_filter)
        stop_transports = __create_transports(df, stop_regex)
        for transport in stop_transports:
            transport.set_stop(stop, False)
            continue
            if not re.match(stop_regex, transport.name):
                continue
            if not transport.stop:
                transport.set_stop(stop, False)
                continue
            if transport.is_permutation:
                # "Perfect" matches can't get better.
                continue
            old_stop = _create_single_name_filter_extended(transport.stop)
            old_regex = create_regex(old_stop)
            if better_match(stop_regex, old_regex, transport.name):
                transport.set_stop(stop, False)
            print("aaa")

        transports += stop_transports

    return transports


def _create_clusters(
        stops: list[StopName], df: pd.DataFrame, extended: bool) -> Clusters:
    if extended:
        transports = _create_transports_extended(df, stops)
    else:
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

    # TODO: Add cluster/nodes to Config.
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


def display_route3(names: list[StopName],
                   route: list[Node2], clusters: Clusters,
                   cluster=False, nodes=False) -> None:
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

    # TODO: Add cluster/nodes to Config.
    location = mean([e.lat for e in route]), mean([e.lon for e in route])
    m = folium.Map(location=location)
    for i, entry in enumerate(route):
        if nodes:
            add_other_node_markers()
        if cluster:
            add_cluster_marker()
        loc = [entry.lat, entry.lon]
        folium.Marker(loc, popup=f"{entry.name}\n{loc}").add_to(m)
        for c in clusters[names[i]]:
            c_loc = c.lat, c.lon
            if distance(*loc, *c_loc) > 300:
                continue
            folium.Marker(c_loc, popup=f"{[names[i]]}\n{loc}",
                          icon=folium.Icon(icon="cloud")).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay3.html")
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
    # TODO: Probably fails if dists[a][0] == dists[b][0]
    return min(dists, key=itemgetter(0))[1]


def generate_routes(raw_df: pd.DataFrame, stops: list[StopName]
                    ) -> list[list[Node2]]:
    df = _filter_df(raw_df, _create_name_filter(stops))
    clusters = _create_clusters2(stops, df)
    routes: list[list[Node2]] = _create_routes(stops, clusters)
    return routes


def generate_routes2(raw_df: pd.DataFrame, stops: list[StopName]
                     ) -> list[list[Node2]]:
    name_filter = _create_name_filter(stops)
    df = _filter_df(raw_df, _create_name_filter(stops))
    clusters = _create_clusters(stops, df, False)
    empty_clusters = {key: cluster for key, cluster in clusters.items()
                      if not cluster}
    if empty_clusters:
        missing_stops = list(empty_clusters.keys())
        missing_name_filter = _create_extended_name_filter(missing_stops)
        df = _filter_df(raw_df, missing_name_filter
                        ).drop(df.index, errors="ignore")
        clusters.update(_create_clusters(missing_stops, df, True))

    routes: list[list[Node2]] = _create_routes2(stops, clusters)
    return routes, clusters
