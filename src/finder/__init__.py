from __future__ import annotations

import re
import logging
import os.path
import platform
import datetime as dt
from requests.exceptions import ConnectionError
from os import makedirs
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib import parse
from typing import TYPE_CHECKING

import pandas as pd
import requests

from config import Config
from finder.cluster import Node2
from finder.routes import (select_shortest_route, display_route2,
                           generate_routes2, display_route3)


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler


logger = logging.getLogger(__name__)


def get_osm_query(stop_positions=True, stations=True, platforms=True) -> str:
    def union(a: str, b: str) -> str:
        if not a:
            return b
        return f"{{\t{a}\t}} UNION {{\t{b}\t}}"

    pre = ["PREFIX osmrel: <https://www.openstreetmap.org/relation/>",
           "PREFIX geo: <http://www.opengis.net/ont/geosparql#>",
           "PREFIX geof: <http://www.opengis.net/def/function/geosparql/>",
           "PREFIX osm: <https://www.openstreetmap.org/>",
           "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>",
           "PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>"]
    sel = ["SELECT ?stop ?name ?lat ?lon ?public_transport WHERE {"]
    base = ["?stop osmkey:public_transport ?public_transport .",
            "?stop rdf:type osm:node .",
            "?stop geo:hasGeometry ?location .",
            "?stop osmkey:name ?name .",
            "BIND (geof:latitude(?location) AS ?lat)",
            "BIND (geof:longitude(?location) AS ?lon)",
            "} ORDER BY ?name"]
    transport_format = '?stop osmkey:public_transport "{}" .'
    transport = ""
    if stations:
        transport = union(transport, transport_format.format("station"))
    if stop_positions:
        transport = union(transport, transport_format.format("stop_position"))
    if platforms:
        transport = union(transport, transport_format.format("platform"))
    transport_list = transport.strip().split("\t")

    query_list = pre + sel + transport_list + base
    return " \n".join(query_list)


def get_osm_data_from_qlever(path: Path) -> bool:
    base_url = "https://qlever.cs.uni-freiburg.de/api/osm-germany/?"
    data = {"action": "tsv_export", "query": get_osm_query()}
    # TODO: Add "OPTIONAL {?stop osmkey:XX Config.osmkey_XX}"
    #  e.g. railway: "tram_stop"

    url = base_url + parse.urlencode(data)
    try:
        r = requests.get(url)
    except ConnectionError as e:
        logger.error(f"Could not get osm data: {e}")
        return False

    if r.status_code != 200:
        logger.error(f"Could not get osm data: {r}\n{r.content}")
        return False

    with open(path, "wb") as fil:
        date = dt.date.today().strftime("%Y%m%d")
        fil.write(bytes(f"# Queried: .{date}.\n", "utf-8"))
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
        return self._cache_is_stale() or self._query_different_from_cache()

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
        except (ValueError, IndexError):
            logger.warning(msg)
            return True

        return (date - query_date).days > Config.stale_cache_days

    def _query_different_from_cache(self):
        def clean_line(_line):
            return _line[1:].strip()

        lines = []
        with open(self.fp, "rb") as fil:
            line = fil.readline().decode("utf-8").strip()
            while line.startswith("#"):
                if clean_line(line):
                    lines.append(clean_line(line))
                line = fil.readline().decode("utf-8")
        query = " \n".join(lines[2:])
        return query != get_osm_query()

    def _get_stop_data(self):
        def _cleanup_name():
            """ Remove any chars which are not letters or allowed chars.
            Doing it this way is a lot faster than using a converter. """
            # Special chars include for example umlaute
            # See https://en.wikipedia.org/wiki/List_of_Unicode_characters
            special_chars = "\u00C0-\u00D6\u00D9-\u00F6\u00F8-\u00FF"
            allowed_chars = "".join(Config.allowed_stop_chars)
            # Remove all text enclosed by parentheses.
            p_re = r"(\(.*\))"
            df["name"] = df["name"].str.replace(p_re, "", regex=True
                                                ).str.strip()
            # Replace all abbrevieations with their full version.
            for abbrev, full in Config.name_abbreviations.items():
                abbrev_pattern = r"\b" + re.escape(abbrev)
                df["name"] = df["name"].str.lower().str.replace(
                    abbrev_pattern, full, regex=True)
            # Remove all chars other than the allowed ones.
            char_re = "[^a-zA-Z{}{}]".format(special_chars, allowed_chars)
            df["name"] = df["name"].str.casefold().str.lower().str.replace(
                char_re, "", regex=True).str.strip()
            # Remove multiple spaces resulting from previous removal.
            df["name"] = df["name"].str.replace(" +", " ", regex=True)

        if not self.use_cache or self.rebuild_cache():
            if not get_osm_data_from_qlever(self.fp):
                return

        converters = {"stop_loc": stop_loc_converter}
        df = pd.read_csv(
            self.fp,
            sep="\t",
            names=["stop", "name", "lat", "lon", "transport"],
            header=0,
            comment="#",
            converters=converters)
        _cleanup_name()
        self.df: pd.DataFrame = df

    def generate_routes(self):
        names = [stop.stop_name for stop in self.handler.stops.entries]
        self.routes, self.clusters = generate_routes2(self.df, names)

    def get_shortest_route(self) -> list[Node2]:
        # TODO: Weird roundabout way to do all this.
        if not self.routes:
            self.generate_routes()
        names = [stop.stop_name for stop in self.handler.stops.entries]
        # TODO: Needs check if route exists.
        route = select_shortest_route(names, self.routes)
        if Config.display_route:
            display_route2(names, route, True, False)
            display_route3(names, route, self.clusters, True)
        return route
