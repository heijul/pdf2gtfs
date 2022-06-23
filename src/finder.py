from __future__ import annotations

import heapq
from urllib import parse
from operator import itemgetter
from typing import TYPE_CHECKING, TypeAlias, Optional

import pandas as pd
import requests
from geopy import distance as _distance


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler


Lat: TypeAlias = float
Lon: TypeAlias = float


def get_osm_data_from_qlever():
    base_url = "https://qlever.cs.uni-freiburg.de/api/osm-germany/?"
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
        print(f"{r}\n{r.content}")
        return
    with open("../data/osm_germany_stops.csv", "bw") as fil:
        fil.write(r.content)


def clean_point(entry: pd.Series) -> pd.Series:
    point = entry["stop_loc"]
    if not point.startswith("POINT("):
        print("AAA", point)

    entry["stop_loc"] = point[6:].split(")")[0]
    return entry


def stop_loc_converter(value: str) -> str:
    if not value.startswith("POINT("):
        print("AAA", value)
        return ""

    return value[6:].split(")", 1)[0]


def name_converter(name: str) -> str:
    return name


class Finder:
    def __init__(self, gtfs_handler: GTFSHandler):
        self.handler = gtfs_handler
        self._set_df()

    def _set_df(self):
        converters = {"stop_loc": stop_loc_converter,
                      "name": name_converter}
        df = pd.read_csv("../data/osm_germany_stops.csv",
                         sep="\t",
                         names=["stop", "name", "stop_loc"],
                         header=0,
                         converters=converters)
        df[["lon", "lat"]] = df.stop_loc.str.split(" ", expand=True)
        del df["stop_loc"]
        self.df = df

    def detect_coordinates(self):
        def cond(_name):
            return self.df["name"].str.startswith(_name)

        names = [stop.stop_name for stop in self.handler.stops.entries]
        coords = {name: self.df.where(cond(name)).dropna() for name in names}
        dists = {}
        for cur, nxt in zip(names, names[1:] + [None]):
            if not nxt:
                dists[cur] = {}
                break
            dists[cur] = distances(coords[cur], coords[nxt])
        print(dists)


def distance(lat1, lon1, lat2, lon2) -> float:
    dist = _distance.distance((lat1, lon1), (lat2, lon2)).km
    return dist


def distances(df1: pd.DataFrame, df2: pd.DataFrame
              ) -> list[tuple[int, int, float]]:
    dists: list[tuple[int, int, float]] = []
    for id1, value1 in df1.iterrows():
        id1: int
        for id2, value2 in df2.iterrows():
            id2: int
            dist = distance(value1.lat, value1.lon, value2.lat, value2.lon)
            dists.append((id1, id2, dist))
    return dists


NodeList: TypeAlias = list[("Node", float)]


class Node:
    def __init__(self, node_id: int):
        self.id = node_id
        self._neighbors: NodeList = []

    @property
    def neighbors(self) -> NodeList:
        return self._neighbors

    @property
    def closest(self) -> tuple[Optional[Node], float]:
        if not self.neighbors:
            return None, 0
        return sorted(self.neighbors, key=itemgetter(1))[0]

    def add_neighbor(self, neighbor: Node, dist: float):
        self.neighbors.append((neighbor, dist))


def get_min_node(nodes: list[Node]):
    min_node = None
    min_dist = -1
    for node in nodes:
        _, dist = node.closest
        if min_dist < 0 or dist < min_dist:
            min_node = node
    return min_node


class ClusterDijkstra:
    def __init__(self, nodes: list[Node]):
        self.unvisited = set(nodes)
        self.first = get_min_node(nodes)

    def solve(self):
        for node in self.unvisited:
            pass


def search(nodes: list[Node]):
    heap = list(nodes)
    heapq.heapify(heap)


