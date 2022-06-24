from __future__ import annotations

import logging
from math import sqrt, cos
from statistics import mean
from urllib import parse
from typing import TYPE_CHECKING, TypeAlias

import pandas as pd
import requests
from geopy import distance as _distance


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
        self._set_df()

    def _set_df(self):
        converters = {"stop_loc": stop_loc_converter,
                      "name": name_converter}
        df = pd.read_csv("../data/osm_germany_stops.csv",
                         sep="\t",
                         names=["stop", "name", "stop_loc"],
                         header=0,
                         converters=converters)
        df[["lon", "lat"]] = df.stop_loc.str.split(" ", expand=True).astype(float)
        df["lat2"] = df["lat"].astype(float).round(2)
        df["lon2"] = df["lon"].astype(float).round(2)
        del df["stop_loc"]
        self.df: pd.DataFrame = df

    def detect_coordinates(self):
        def cond(_name):
            return self.df["name"].str.casefold().str.startswith(
                _name.casefold())

        names = [stop.stop_name for stop in self.handler.stops.entries]
        coords = {name: self.df.where(cond(name)).dropna() for name in names}

        # Map stops to distances.
        dists = {}
        for cur, nxt in zip(names, names[1:] + [None]):
            if not nxt:
                dists[cur] = {}
                break
            dists[cur] = distances(coords[cur], coords[nxt])
        print(dists)

        # Map stop_ids to stop_ids.
        dists_dict = {}
        for values in dists.values():
            for value in values:
                dists_dict[value[0]] = value[1]

        # Generate routes
        routes = []
        for start, nxt, dist in dists[names[0]]:
            routes.append([self.df.loc[start]])

            while nxt:
                routes[-1].append(self.df.loc[nxt])
                nxt = dists_dict.get(nxt)
        print(routes)
        routes_to_csv(routes)


def routes_to_csv(routes: list[list[pd.Series]]):
    # Turn into csv, usable by www.gpsvisualizer.com
    csv = []
    for i, route in enumerate(routes):
        lines = [f"{entry['name']},{entry['lat']},{entry['lon']}"
                 for entry in route]
        csv.append("\n".join(lines))
        print(csv[-1])
    return csv


def distance(lat1, lon1, lat2, lon2) -> float:
    """ Distance between two locations. """
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
            if dist > MAX_DIST_IN_KM:
                continue
            dists.append((id1, id2, dist))
    return dists
