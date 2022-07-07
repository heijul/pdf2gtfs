import webbrowser
from operator import itemgetter
from statistics import mean
from typing import TypeAlias

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
        cf_names = [strip_forbidden_symbols(name).casefold()
                    for name in stop_names]
        for c in list(cf_names):
            if " " not in c:
                continue
            cf_names += c.split(" ")

        self._set_df(raw_df, cf_names)
        self._create_stop_nodes(cf_names)
        self._group_df_with_tolerance()
        self._create_cluster_nodes()
        self._create_clusters()

    def _set_df(self, df: pd.DataFrame, casefolded: list[str]) -> None:
        self.df = df.where(df["name"].str.casefold().isin(casefolded)).dropna()
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
