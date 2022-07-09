from __future__ import annotations

import webbrowser
from statistics import mean
from typing import TypeAlias

import pandas as pd
import folium

from config import Config
from finder.cluster import Cluster2, Node2
from utils import strip_forbidden_symbols


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


StopName: TypeAlias = str
CStopName: TypeAlias = str
Location: TypeAlias = tuple[float, float]
Clusters: TypeAlias = dict[StopName: list[Cluster2]]


def _create_name_filter(names: list[StopName]):
    # TODO: Turn cf_names into dict with name -> [split names]
    name_filter = [name.casefold().lower() for name in names]
    for char in list(name_filter):
        if " " not in char:
            continue
        name_filter += char.split(" ")
    return name_filter


def _filter_df(df: pd.DataFrame, name_filter: list[StopName]):
    return df.where(df["name"].isin(name_filter)).dropna()


def _create_clusters2(stops: list[StopName], df: pd.DataFrame) -> Clusters:
    def by_name(entry_id):
        _entry = df.loc[entry_id]
        return strip_forbidden_symbols(_entry["name"]).casefold().lower()

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
    # TODO: Needs check if routes is empty.
    if Config.display_route:
        _display_route2(routes[0], True, True)
    return routes


def _display_route2(route: list[Node2], cluster=False, nodes=False) -> None:
    # TODO: Add cluster/nodes to Config.
    location = mean([e.lat for e in route]), mean([e.lon for e in route])
    m = folium.Map(location=location)
    for entry in route:
        loc = [entry.lat, entry.lon]
        if nodes:
            for node in entry.cluster.nodes:
                if node == entry:
                    continue
                loc = [node.lat, node.lon]
                folium.Marker(loc, popup=f"{node.name}\n{loc}",
                              icon=folium.Icon(color="green")).add_to(m)
        if cluster:
            loc = [entry.cluster.lat, entry.cluster.lon]
            folium.Marker([entry.cluster.lat, entry.cluster.lon],
                          popup=f"{entry.name}\n{loc}",
                          icon=folium.Icon(icon="cloud")).add_to(m)
        folium.Marker(loc, popup=f"{entry.name}\n{loc}").add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


def generate_routes(raw_df: pd.DataFrame, stops: list[StopName]):
    df = _filter_df(raw_df, _create_name_filter(stops))
    clusters = _create_clusters2(stops, df)
    routes = _create_routes(stops, clusters)
    return routes
