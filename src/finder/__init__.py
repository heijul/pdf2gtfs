from __future__ import annotations

import re
import logging
import os.path
import platform
import datetime as dt
from io import BytesIO

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
                           generate_routes2)
from utils import SPECIAL_CHARS


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
    # FEATURE: Add "OPTIONAL {?stop osmkey:XX Config.osmkey_XX}"
    #  e.g. railway: "tram_stop". Check branch 'add_railway_key'.

    url = base_url + parse.urlencode(data)
    try:
        r = requests.get(url)
    except ConnectionError as e:
        logger.error(f"Could not get osm data: {e}")
        return False

    if r.status_code != 200:
        logger.error(f"Could not get osm data: {r}\n{r.content}")
        return False

    osm_data_to_file(r.content, data["query"], path)
    return True


def _clean_osm_data(raw_data: bytes) -> pd.DataFrame:
    def _normalize(series: pd.Series) -> pd.Series:
        return series.str.lower().str.casefold()

    def _remove_parentheses(series: pd.Series) -> pd.Series:
        # Remove parentheses and all text enclosed by them.
        regex = r"(\(.*\))"
        return series.str.replace(regex, "", regex=True)

    def _remove_forbidden_chars(series: pd.Series) -> pd.Series:
        # Remove all chars other than the allowed ones.
        allowed_chars = "".join(Config.allowed_stop_chars)
        char_re = fr"[^a-zA-Z\d{SPECIAL_CHARS}{allowed_chars}]"
        return series.str.replace(char_re, "", regex=True)

    def _cleanup_spaces(series: pd.Series) -> pd.Series:
        # Remove consecutive, as well as leading/trailing spaces.
        return series.str.replace(" +", " ", regex=True).str.strip()

    def _replace_abbreviations(series: pd.Series) -> pd.Series:
        def replace_abbrev(value):
            start, end = value.span()
            return abbrevs[value.string[start:end]]

        # TODO: Try to match the whole abbrev, but allow missing dots as well
        abbrevs = Config.name_abbreviations
        regex = "|".join([rf"\b{re.escape(abbrev)}" for abbrev in abbrevs])
        return series.str.replace(regex, replace_abbrev, regex=True)

    def _cleanup_name(series: pd.Series):
        """ Remove any chars which are not letters or allowed chars.
        Doing it this way is a lot faster than using a converter. """
        return _cleanup_spaces(
            _remove_forbidden_chars(
                _remove_parentheses(
                    _replace_abbreviations(
                        _normalize(series)))))

    df = read_csv(BytesIO(raw_data))
    df["name"] = _cleanup_name(df["name"])
    # Remove entries with empty name.
    return df.where(df["name"] != "").dropna()


def osm_data_to_file(raw_data: bytes, query: str, path: Path):
    # TODO: Now requires --clear_cache, if allowed_chars/abbrevs are changed.
    #  Alternative: Save the allowed_chars + abbrevs in the cache as well.
    df = _clean_osm_data(raw_data)

    with open(path, "w") as fil:
        date = dt.date.today().strftime("%Y%m%d")
        fil.write(f"# Queried: .{date}.\n")
        query = "\n#   ".join(query.split("\n"))
        fil.write(f"# Query: \n#   {query}\n")

    df.to_csv(path, sep="\t", header=False, index=False, mode="a")


def stop_loc_converter(value: str) -> str:
    value = value.replace('"', "")
    if not value.startswith("POINT("):
        logger.warning(f"Stop location could not be converted: '{value}'")
        return ""

    return value[6:].split(")", 1)[0]


def get_cache_dir_path() -> Path | None:
    system = platform.system().lower()
    if system == "windows":
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


def read_csv(file: Path | BytesIO) -> pd.DataFrame:
    return pd.read_csv(
        file,
        sep="\t",
        names=["stop", "name", "lat", "lon", "transport", "clean_name"],
        header=0,
        comment="#")


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
        if not self.use_cache or self.rebuild_cache():
            if not get_osm_data_from_qlever(self.fp):
                return

        df = read_csv(self.fp)
        self.df: pd.DataFrame = df

    def generate_routes(self):
        names = [stop.stop_name for stop in self.handler.stops.entries]
        self.routes = generate_routes2(self.df, names)

    def get_shortest_route(self) -> list[Node2]:
        # STYLE: Weird roundabout way to do all this.
        if not self.routes:
            self.generate_routes()
        names = [stop.stop_name for stop in self.handler.stops.entries]
        # TODO: Needs check if route exists.
        route = select_shortest_route(names, self.routes)
        if Config.display_route:
            display_route2(names, route, False, False)
        return route
