from __future__ import annotations

import logging
import os.path
import platform
import datetime as dt
from os import makedirs
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib import parse
from typing import TYPE_CHECKING

import pandas as pd
import requests

from config import Config
from finder.cluster import Node2
from finder.routes import (generate_routes,
                           select_shortest_route, display_route2)


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

# TODO: Create cache dir in $SYSTEMCACHEDIR
#  e.g. os.path.expanduser("~/.cache/pdf2gtfs")????
# TODO: Add timestamp to csv + max_timestamp to Config

logger = logging.getLogger(__name__)


def get_osm_data_from_qlever(path: Path) -> bool:
    base_url = "https://qlever.cs.uni-freiburg.de/api/osm-germany/?"
    data = {
        "action": "tsv_export",
        "query": (
            "PREFIX osmrel: <https://www.openstreetmap.org/relation/> \n"
            "PREFIX geo: <http://www.opengis.net/ont/geosparql#> \n"
            "PREFIX geof: <http://www.opengis.net/def/function/geosparql/> \n"
            "PREFIX osm: <https://www.openstreetmap.org/> \n"
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> \n"
            "PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:> \n"
            "SELECT ?stop ?name ?lat ?lon ?location WHERE { \n"
            '?stop osmkey:public_transport "stop_position" . \n'
            "?stop rdf:type osm:node . \n"
            "?stop geo:hasGeometry ?location . \n"
            "?stop osmkey:name ?name . \n"
            "BIND (geof:latitude(?location) AS ?lat) \n"
            "BIND (geof:longitude(?location) AS ?lon) \n"
            "} ORDER BY ?name")}
    # TODO: Add "OPTIONAL {?stop osmkey:XX Config.osm_XX}"
    #  e.g. railway: "tram_stop"

    url = base_url + parse.urlencode(data)
    r = requests.get(url)

    if r.status_code != 200:
        logger.error(f"Could not get osm data: {r}\n{r.content}")
        return False

    with open(path, "wb") as fil:
        date = dt.date.today().strftime("%Y%m%d")
        fil.write(bytes(f"# Queried: {date}\n", "utf-8"))
        query = "\n#   ".join(data["query"].split("\n"))
        fil.write(bytes(f"# Query: \n#   {query}\n", "utf-8"))
        fil.write(r.content)

    return True


def stop_loc_converter(value: str) -> str:
    value = value.replace('"', "")
    if not value.startswith("POINT("):
        logger.warning(f"Stop location could not be converted: '{value}'")
        return ""

    return value[6:].split(")", 1)[0]


def get_cache_dir_path() -> Path | None:
    system = platform.system().lower()
    if system == "windows":
        # TODO: Test on windows
        return Path(os.path.expandvars("%LOCALAPPDATA%/pdf2gtfs/")).resolve()
    if system == "linux":
        return Path(os.path.expanduser("~/.cache/pdf2gtfs/")).resolve()

    logger.warning("Cache is only supported on linux and windows "
                   "platforms.")


def create_cache_dir() -> tuple[bool, Path | None]:
    """ Creates the platform-specific cache directory if it does not exist.

    :returns: Whether the cache directory is valid and the path to directory
    """
    path = get_cache_dir_path()
    if not path:
        return False, None
    if not path.exists():
        try:
            makedirs(path, exist_ok=True)
        except OSError as e:
            logging.warning(f"Cache directory could not be created. "
                            f"Caching has been disabled. Reason: {e}")
            return False, None
    if not path.is_dir():
        logger.warning(f"Cache directory '{path}' appears to be a file. "
                       f"You need to rename/remove that file to use caching. "
                       f"Caching has been disabled.")
        return False, None
    return True, path


class Finder:
    def __init__(self, gtfs_handler: GTFSHandler):
        self.handler = gtfs_handler
        self.temp = None
        self.use_cache, cache_dir = create_cache_dir()
        self._set_fp(cache_dir)
        self._get_stop_data()
        self.routes: list[list[Node2]] | None = None

    def _set_fp(self, cache_dir: Path):
        self.fp: Path = cache_dir.joinpath("osm_cache.tsv").resolve()
        self.temp = NamedTemporaryFile()
        if self.use_cache:
            return
        self.fp = Path(self.temp.name).resolve()

    def rebuild_cache(self) -> bool:
        """ Cache needs to be rebuild, if it does not exist or is too old. """
        if not self.fp.exists() or Path(self.temp.name).resolve() == self.fp:
            return True
        return self._cache_is_stale()

    def _cache_is_stale(self) -> bool:
        with open(self.fp, "rb") as fil:
            line = fil.readline().decode("utf-8").strip()

        msg = ("Cache was found, but does not seem valid. First line must "
               "be a comment '# Queried: .YYYYMMDD.', containing the date "
               "when the cache was created.")
        if not line.startswith("# Queried: "):
            logger.warning(msg)
            return True

        try:
            date = dt.datetime.now()
            query_date = dt.datetime.strptime(line.split(".")[1], "%Y%m%d")
        except ValueError:
            logger.warning(msg)
            return True

        return (date - query_date).days > Config.stale_cache_days

    def _get_stop_data(self):
        def _cleanup_name():
            """ Remove any chars which are not letters or allowed chars.
            Doing it this way is a lot faster than using a converter. """
            # Special chars include for example umlaute
            # See https://en.wikipedia.org/wiki/List_of_Unicode_characters
            special_char_ranges = "\u00C0-\u00D6\u00D9-\u00F6\u00F8-\u00FF"
            allowed_chars = "".join(Config.allowed_stop_chars)
            re = "[^a-zA-Z{}{}]".format(special_char_ranges, allowed_chars)
            df["name"] = df["name"].str.casefold().str.lower().str.replace(
                re, "", regex=True)

        if not self.use_cache or self.rebuild_cache():
            if not get_osm_data_from_qlever(self.fp):
                return

        converters = {"stop_loc": stop_loc_converter}
        df = pd.read_csv(self.fp,
                         sep="\t",
                         names=["stop", "name", "lat", "lon", "stop_loc"],
                         header=0,
                         comment="#",
                         converters=converters)
        _cleanup_name()
        del df["stop_loc"]
        self.df: pd.DataFrame = df

    def generate_routes(self):
        names = [stop.stop_name for stop in self.handler.stops.entries]
        self.routes = generate_routes(self.df, names)

    def get_shortest_route(self) -> list[Node2]:
        # TODO: Weird roundabout way to do all this.
        if not self.routes:
            self.generate_routes()
        names = [stop.stop_name for stop in self.handler.stops.entries]
        # TODO: Needs check if route exists.
        route = select_shortest_route(names, self.routes)
        if Config.display_route:
            display_route2(route, True, True)
        return route
