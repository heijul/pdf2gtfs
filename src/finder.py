from __future__ import annotations

import logging
import webbrowser
from dataclasses import dataclass
from heapq import heappush
from operator import itemgetter
from urllib import parse
from typing import TYPE_CHECKING, TypeAlias

import pandas as pd
import requests
from geopy import distance as _distance
import folium


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

# TODO: Create cache dir in $SYSTEMCACHEDIR
#  e.g. os.path.expanduser("~/.cache/pdf2gtfs")????

logger = logging.getLogger(__name__)


# TODO: Config
MAX_DIST_IN_KM = 50


def get_osm_data_from_qlever():
    base_url = "https://qlever.cs.uni-freiburg.de/api/osm-germany/?"
    # TODO: Rename columns
    data = {
        "action": "tsv_export",
        "query": (
            "PREFIX osmrel: <https://www.openstreetmap.org/relation/> "
            "PREFIX geo: <http://www.opengis.net/ont/geosparql#> "
            "PREFIX osm: <https://www.openstreetmap.org/> "
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
            "PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:> "
            "SELECT ?stop ?name ?stop_loc WHERE { "
            '?stop osmkey:public_transport "stop_position" . '
            "?stop rdf:type osm:node . ?stop geo:hasGeometry ?stop_loc . "
            "?stop osmkey:name ?name "
            "} ORDER BY ?name")}

    url = base_url + parse.urlencode(data)
    r = requests.get(url)

    if r.status_code != 200:
        logger.error(f"Response != 200: {r}\n{r.content}")
        return

    # TODO: Add comment in first line about time/date of request
    with open("../data/osm_germany_stops.csv", "wb") as fil:
        fil.write(r.content)


def stop_loc_converter(value: str) -> str:
    value = value.replace('"', "")
    if not value.startswith("POINT("):
        logger.warning(f"Stop location could not be converted: '{value}'")
        return ""

    return value[6:].split(")", 1)[0]


def name_converter(raw_name: str) -> str:
    """ Remove chars which are not allowed. """
    name = ""
    # TODO: Config
    allowed_chars = " .-"
    for char in raw_name:
        if char not in allowed_chars and not char.isalpha():
            continue
        name += char
    return name.strip()


class Finder:
    def __init__(self, gtfs_handler: GTFSHandler):
        self.handler = gtfs_handler
        self._get_stop_data()
        self.routes: Routes | None = None

    def _get_stop_data(self):
        converters = {"stop_loc": stop_loc_converter,
                      "name": name_converter}
        # TODO: Set sep properly
        df = pd.read_csv("../data/osm_germany_stops.csv",
                         sep="\t",
                         names=["stop", "name", "stop_loc"],
                         header=0,
                         converters=converters)
        df[["lon", "lat"]] = df.stop_loc.str.split(
            " ", expand=True).astype(float)
        del df["stop_loc"]
        self.df: pd.DataFrame = df

    def generate_routes(self):
        names = [stop.stop_name for stop in self.handler.stops.entries]
        self.routes = Routes(self.df, names)

    def get_routes(self) -> list[str]:
        if self.routes is None:
            self.generate_routes()
        return routes_to_csv([c.get_route() for c in self.routes.clusters])


def routes_to_csv(routes: list[list[pd.Series]]):
    # Turn into csv, usable by www.gpsvisualizer.com
    csv = []
    for i, route in enumerate(routes):
        lines = [f"{entry['name']},{entry['lat']},{entry['lon']}"
                 for entry in route]
        csv.append("\n".join(lines))
    return csv


def distance(lat1, lon1, lat2, lon2) -> float:
    """ Distance between two locations. """
    dist = _distance.distance((lat1, lon1), (lat2, lon2)).km
    return dist


@dataclass(eq=True, frozen=True)
class StopNode:
    name: str


class ClusterNode:
    stop: StopNode
    lat: float
    lon: float
    nodes: list[pd.Series]
    prev: list[tuple[float, ClusterNode]]
    next: list[tuple[float, ClusterNode]]

    def __init__(self, stop: StopNode, lat: float, lon: float,
                 nodes: list[pd.Series]):
        self.stop = stop
        self.lat = lat
        self.lon = lon
        self._prev = []
        self._next = []
        self.nodes = nodes

    @property
    def prev(self):
        return self._prev

    @property
    def next(self):
        return self._next

    def add_prev(self, node: ClusterNode, dist: float):
        heappush(self._prev, (dist, node))

    def add_next(self, node: ClusterNode, dist: float):
        heappush(self._next, (dist, node))

    def __repr__(self) -> str:
        return f"CNode({self.stop!r}, lat={self.lat}, lon={self.lon})"

    def get_closest(self, other: ClusterNode) -> pd.Series:
        dists = [(distance(other.lat, other.lon, node["lat"], node["lon"]), node)
                 for node in self.nodes]
        return min(dists, key=itemgetter(0))[1]


ClusterDict: TypeAlias = dict[StopNode: list[ClusterNode]]
GroupID: TypeAlias = tuple[str, float, float]


class Cluster:
    def __init__(self, start: ClusterNode, stops: list[StopNode]):
        self.stops: list[StopNode] = stops
        self.start: ClusterNode = start
        self._nodes: ClusterDict = {stop: [] for stop in self.stops}
        self.nodes[self.start.stop].append(self.start)
        self.stop_nodes = None
        self.groups = None
        self.cluster_nodes = None

    @property
    def nodes(self):
        return self._nodes

    def get_previous(self, stop: StopNode) -> list[ClusterNode]:
        stop_index = self.stops.index(stop)
        return self.nodes[self.stops[stop_index - 1]]

    def add(self, nodes: list[ClusterNode]) -> None:
        if not nodes:
            return

        assert all([nodes[0].stop == node.stop for node in nodes])

        previous_nodes = self.get_previous(nodes[0].stop)
        for previous_node in previous_nodes:
            for node in nodes:
                added = self.update_neighbor(previous_node, node)
                if added:
                    self.append(node)

    def append(self, node: ClusterNode) -> None:
        self.nodes[node.stop].append(node)

    @staticmethod
    def update_neighbor(prev: ClusterNode, node: ClusterNode) -> bool:
        dist = distance(prev.lat, prev.lon, node.lat, node.lon)
        if dist > MAX_DIST_IN_KM:
            return False
        prev.add_next(node, dist)
        node.add_prev(prev, dist)
        return True

    def get_route(self) -> list[pd.Series]:
        last_nodes = self.nodes[self.stops[-1]]

        node: ClusterNode = last_nodes[0]
        closest = node.get_closest(self.nodes[self.stops[0]][0])
        previous_node = node
        node = node.prev[0][1]

        route: list[pd.Series] = [closest]
        while node.prev:
            route.insert(0, node.get_closest(previous_node))
            previous_node = node
            node = node.prev[0][1]

        return route


class Routes:
    def __init__(self, raw_df: pd.Dataframe, stop_names: list[str]) -> None:
        self._set_df(raw_df, stop_names)
        self._create_stop_nodes(stop_names)
        self._group_df_with_tolerance()
        self._create_cluster_nodes()
        self._create_clusters()

    def _set_df(self, df: pd.DataFrame, stop_names: list[str]) -> None:
        casefolded = [name.casefold() for name in stop_names]
        self.df = df.where(df["name"].str.casefold().isin(casefolded)).dropna()
        self.df["lat2"] = self.df["lat"].round(2)
        self.df["lon2"] = self.df["lon"].round(2)

    def _create_stop_nodes(self, stop_names) -> None:
        self.stop_nodes = [StopNode(name) for name in stop_names]

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
                if _name != _node.name:
                    continue
                return _node

        nodes: ClusterDict = {}
        for (name, lat, lon), group in self.groups.items():
            stop_node = get_stop_node(name)
            if stop_node is None:
                continue
            node = ClusterNode(stop_node, lat, lon, group)
            if stop_node not in nodes:
                nodes[stop_node] = []
            nodes[stop_node].append(node)
        self.cluster_nodes = nodes

    def _create_clusters(self):
        clusters = []
        # Create a cluster for each start node.
        for start in self.cluster_nodes[self.stop_nodes[0]]:
            clusters.append(Cluster(start, self.stop_nodes))
        # Populate clusters.
        for stop_node in self.stop_nodes[1:]:
            for cluster in clusters:
                cluster.add(self.cluster_nodes[stop_node])
        self.clusters = clusters


def display_route(route: pd.Series):  # list[tuple[str, float, float]]):
    m = folium.Map(location=[47.9872899, 7.7263808])
    for entry in route:
        stop = entry["name"]
        lat = entry["lat"]
        lon = entry["lon"]
        folium.Marker([lat, lon], popup=stop).add_to(m)
    # TODO: Maybe use tempfile
    m.save("test.html")
    webbrowser.open_new_tab("test.html")
