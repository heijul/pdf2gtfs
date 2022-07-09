from __future__ import annotations

import webbrowser
from operator import itemgetter
from statistics import mean
from typing import TypeAlias, Optional

import pandas as pd
import folium

from config import Config
from finder.cluster import Cluster, StopNode, distance, Node
from utils import strip_forbidden_symbols


GroupID: TypeAlias = tuple[str, float, float]


class Route:
    def __init__(self, start: Cluster, stops: list[StopNode]):
        self.stops: list[StopNode] = stops
        self.start: Cluster = start
        self._nodes: dict[StopNode: list[Cluster]]
        self._nodes = {stop: [] for stop in self.stops}
        self.nodes[self.start.stop].append(self.start)
        self.stop_nodes = None
        self.groups = None
        self.cluster_nodes = None

    @property
    def nodes(self) -> dict[StopNode: list[Cluster]]:
        return self._nodes

    def get_previous(self, stop: StopNode) -> list[Cluster]:
        stop_index = self.stops.index(stop)
        return self.nodes[self.stops[stop_index - 1]]

    def add_nodes(self, nodes: list[Cluster]) -> None:
        if not nodes:
            return

        assert all([nodes[0].stop == node.stop for node in nodes])

        previous_nodes = self.get_previous(nodes[0].stop)
        for previous_node in previous_nodes:
            for node in nodes:
                if not self.update_neighbor(previous_node, node):
                    continue
                self.nodes[node.stop].append(node)

    @staticmethod
    def update_neighbor(prev: Cluster, node: Cluster) -> bool:
        if node.is_dummy or prev.is_dummy:
            prev.add_next(node, 0.1)
            node.add_prev(prev, 0.1)
            return True

        dist = distance(prev.lat, prev.lon, node.lat, node.lon)
        if dist > Config.max_stop_distance:
            return False
        prev.add_next(node, dist)
        node.add_prev(prev, dist)
        return True

    def get_route(self) -> list[Node]:
        cluster: Cluster = self.start
        cluster_route: list[Cluster] = [cluster]
        while cluster.next:
            cluster = min(
                [(distance(cluster.lat, cluster.lon, c[1].lat, c[1].lon), c[1])
                 for c in cluster.next], key=itemgetter(0))[1]
            cluster_route.append(cluster)

        closest = cluster_route[-1].get_closest(cluster_route[-2])
        node_route: list[Node] = [closest]
        for node in reversed(cluster_route[:-1]):
            node_route.insert(0, node.get_closest(node_route[0]))

        return node_route


class Routes:
    def __init__(self, raw_df: pd.DataFrame, stop_names: list[str]) -> None:
        # TODO: Turn cf_names into dict with name -> [split names]
        cf_names = [name.casefold().lower() for name in stop_names]
        for c in list(cf_names):
            if " " not in c:
                continue
            cf_names += c.split(" ")

        self._set_df(raw_df, cf_names)
        clusters = create_clusters2(stop_names, self.df)
        routes = create_routes(stop_names, clusters)

        self._create_stop_nodes(cf_names)
        self._group_df_with_tolerance()
        self._create_cluster_nodes()
        self._create_clusters()

    def _set_df(self, df: pd.DataFrame, casefolded: list[str]) -> None:
        self.df = df.where(df["name"].isin(casefolded)).dropna()
        self.df["lat2"] = self.df["lat"].round(2)
        self.df["lon2"] = self.df["lon"].round(2)

    def _create_stop_nodes(self, casefolded) -> None:
        self.stop_nodes = [StopNode(name) for name in casefolded]

    def _group_df_with_tolerance(self) -> dict[GroupID: list[pd.Series]]:
        """ Group the dataframe by (name, lat2, lon2), allowing tolerances. """

        def _get_or_create_group(name2: str, lat2: float, lon2: float) -> list:
            for (name, lat, lon), _group in groups.items():
                if name.casefold() != name2.casefold():
                    continue
                if abs(lat - lat2) <= 0.01 and abs(lon - lon2) <= 0.01:
                    return _group
            groups[(name2, lat2, lon2)] = []
            return groups[(name2, lat2, lon2)]

        groups: dict[GroupID: list[pd.Series]] = {}
        for row_id, row in self.df.iterrows():
            group = _get_or_create_group(row["name"], row["lat2"], row["lon2"])
            group.append(row)
        self.groups = groups

    def _create_cluster_nodes(self):
        def get_stop_node(_name):
            for _node in self.stop_nodes:
                if _name.casefold() != _node.name:
                    continue
                return _node

        nodes: dict[StopNode: list[Cluster]] = {}
        for (name, lat, lon), group in self.groups.items():
            stop_node = get_stop_node(name)
            if stop_node is None:
                continue
            node = Cluster(stop_node, lat, lon, group)
            if stop_node not in nodes:
                nodes[stop_node] = []
            nodes[stop_node].append(node)
        self.cluster_nodes = nodes

    def _create_clusters(self):
        clusters = []
        # Create a cluster for each start node.
        for start in self.cluster_nodes[self.stop_nodes[0]]:
            clusters.append(Route(start, self.stop_nodes))
        # Populate clusters.
        for stop_node in self.stop_nodes[1:]:
            for cluster in clusters:
                nodes = self.cluster_nodes.get(stop_node, [])
                if not nodes:
                    nodes = [Cluster(stop_node, 0, 0, [])]
                cluster.add_nodes(nodes)
        self.clusters = clusters


def routes_to_csv(routes: list[list[Node]]):
    # Turn into csv, usable by www.gpsvisualizer.com
    csv = []
    for i, route in enumerate(routes):
        lines = [f"{entry.stop},{entry.lat},{entry.lon}"
                 for entry in route]
        csv.append("\n".join(lines))
    return csv


def display_route(route: list[Node]):
    location = mean([e.lat for e in route]), mean([e.lon for e in route])
    m = folium.Map(location=location)
    for entry in route:
        folium.Marker([entry.lat, entry.lon], popup=entry.stop).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


class Node2:
    cluster: Cluster2
    lat: float
    lon: float
    name: str

    def __init__(self, cluster, name, lat, lon) -> None:
        # Remove cluster and add it via add_node
        self.cluster = cluster
        self.name = name
        self.lat = lat
        self.lon = lon

    @property
    def cluster(self) -> Cluster2:
        return self._cluster

    @cluster.setter
    def cluster(self, cluster: Cluster2) -> None:
        self._cluster = cluster
        cluster.add_node(self)

    def distance(self, other: Node2 | Cluster2) -> float:
        return distance(self.lat, self.lon, other.lat, other.lon)


StopName: TypeAlias = str
CStopName: TypeAlias = str


class Cluster2:
    nodes: list[Node2]
    lat: float
    lon: float

    def __init__(self, lat: float, lon: float) -> None:
        self.nodes = []
        self.lat = lat
        self.lon = lon
        self._next = None
        self._prev = None

    @property
    def next(self) -> Cluster2:
        return self._next

    @next.setter
    def next(self, other: Cluster2 | list[Cluster2]) -> None:
        if isinstance(other, list) and other:
            other = self.get_closest_cluster(other)
        self._next = other
        if not other.prev == self:
            other.prev = self

    @property
    def prev(self) -> Cluster2:
        return self._prev

    @prev.setter
    def prev(self, other: Cluster2):
        self._prev = other
        if not other.next == self:
            other.next = self

    def get_closest_cluster(self, clusters: list[Cluster2]) -> Cluster2:
        closest = clusters[0]
        min_dist = distance(self.lat, self.lon, closest.lat, closest.lon)
        for cluster in clusters[1:]:
            dist = distance(self.lat, self.lon, cluster.lat, cluster.lon)
            if dist > min_dist:
                continue
            closest = cluster
            min_dist = dist
        return closest

    def add_node(self, node: Node2) -> None:
        if node in self.nodes:
            return
        self.nodes.append(node)

    def get_closest(self) -> Optional[Node2]:
        if not self.nodes:
            return None
        costs: list[tuple[float, Node2]] = []
        for node in self.nodes:
            cost_next = node.distance(self.next) if self.next else 0
            cost_prev = node.distance(self.prev) if self.prev else 0
            cost_self = node.distance(self)
            # Prefer nodes closer to next node, because vehicles
            #  typically stop at the furthest stop position first.
            # Preferring nodes closer to the cluster location seems to lead
            #  to better results as well. TODO: Needs more testing
            cost = 1.05 * cost_next + cost_prev + 0.5 * cost_self
            costs.append((cost, node))
        return min(costs, key=itemgetter(0))[1]

    def adjust_location(self):
        """ Set the location to the mean of the location of the nodes. """
        self.lat = mean([node.lat for node in self.nodes])
        self.lon = mean([node.lon for node in self.nodes])


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


Clusters: TypeAlias = dict[StopName: list[Cluster2]]


def create_clusters2(stops: list[StopName], df: pd.DataFrame) -> Clusters:
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


def create_routes(stops: list[StopName], clusters: Clusters) -> list[Route2]:
    starts: list[Cluster2] = clusters[stops[0]]
    routes: list[Route2] = []
    for start in starts:
        route = Route2(stops)
        route.create(start, clusters)
        routes.append(route)
    route = routes[0].find_shortest_path()
    display_route2(route, True, True)
    return routes


def display_route2(route: list[Node2], cluster=False, nodes=False) -> None:
    location = mean([e.lat for e in route]), mean([e.lon for e in route])
    m = folium.Map(location=location)
    for entry in route:
        loc = [entry.lat, entry.lon]
        folium.Marker(loc, popup=f"{entry.name}\n{loc}").add_to(m)
        if cluster:
            loc = [entry.cluster.lat, entry.cluster.lon]
            folium.Marker([entry.cluster.lat, entry.cluster.lon],
                          popup=f"{entry.name}\n{loc}",
                          icon=folium.Icon(icon="cloud")).add_to(m)
        if not nodes:
            continue
        for node in entry.cluster.nodes:
            if node == entry:
                continue
            loc = [node.lat, node.lon]
            folium.Marker(loc, popup=f"{node.name}\n{loc}",
                          icon=folium.Icon(color="green")).add_to(m)

    outfile = Config.output_dir.joinpath("routedisplay.html")
    m.save(str(outfile))
    webbrowser.open_new_tab(str(outfile))


Location: TypeAlias = tuple[float, float]


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
    groups: dict[GroupID: list[pd.Series]] = {}
    for row_id, row in df.iterrows():
        loc = (row["lat2"], row["lon2"])
        _try_create_group(*loc).append(row)
    return groups
