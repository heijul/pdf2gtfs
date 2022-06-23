from __future__ import annotations

import heapq
import logging
from urllib import parse
from operator import itemgetter
from typing import TYPE_CHECKING, TypeAlias, Optional

import pandas as pd
import requests
from geopy import distance as _distance


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler


logger = logging.getLogger(__name__)


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
        logger.error(f"Response != 200: {r}\n{r.content}")
        return

    with open("../data/osm_germany_stops.csv", "wb") as fil:
        fil.write(r.content)


def stop_loc_converter(value: str) -> str:
    if not value.startswith("POINT("):
        logger.warning(f"Stop location could not be converted: '{value}'")
        return ""

    return value[6:].split(")", 1)[0]


def name_converter(raw_name: str) -> str:
    name = ""
    # TODO: Config + regex?!/whitelist
    skip_chars = "#()"
    for char in raw_name:
        if char in skip_chars:
            continue
        name += char
    return raw_name


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
    """ Return distances between each entry of one df to each of the other. """
    dists: list[tuple[int, int, float]] = []
    for id1, value1 in df1.iterrows():
        id1: int
        for id2, value2 in df2.iterrows():
            id2: int
            dist = distance(value1.lat, value1.lon, value2.lat, value2.lon)
            dists.append((id1, id2, dist))
    return dists
