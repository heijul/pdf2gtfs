from __future__ import annotations

import datetime as dt
import logging
import os.path
import platform
from io import BytesIO
from os import makedirs
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional, TYPE_CHECKING
from urllib import parse

import pandas as pd
import requests
from requests.exceptions import ConnectionError

from config import Config
from finder.routes import (
    display_route, generate_routes, generate_routes2, select_shortest_route)
from utils import get_abbreviations_regex, replace_abbreviation, SPECIAL_CHARS


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler
    from finder.cluster import Node, Cluster


logger = logging.getLogger(__name__)


KEYS = ["stop", "name", "lat", "lon", "public_transport"]
KEYS_OPTIONAL = [
    "railway", "bus", "tram", "train", "subway", "monorail", "light_rail"]


def get_osm_query(stop_positions=True, stations=True, platforms=True) -> str:
    def get_selection() -> list[str]:
        identifier = map(lambda key: f"?{key}", KEYS + KEYS_OPTIONAL)
        return ["SELECT {} WHERE {{".format(" ".join(identifier))]

    def get_transports() -> list[str]:
        fmt = '?stop osmkey:public_transport "{}" .'
        transport = ""
        if stations:
            transport = union(transport, fmt.format("station"))
        if stop_positions:
            transport = union(transport, fmt.format("stop_position"))
        if platforms:
            transport = union(transport, fmt.format("platform"))
        return transport.strip().split("\t")

    def get_optionals() -> list[str]:
        fmt = "OPTIONAL {{ ?stop osmkey:{0} ?{0} . }}"
        return [fmt.format(key) for key in KEYS_OPTIONAL]

    def union(a: str, b: str) -> str:
        # Union two statements. Uses \t as delimiter after/before braces.
        if not a:
            return b
        return f"{{\t{a}\t}} UNION {{\t{b}\t}}"

    pre = ["PREFIX osmrel: <https://www.openstreetmap.org/relation/>",
           "PREFIX geo: <http://www.opengis.net/ont/geosparql#>",
           "PREFIX geof: <http://www.opengis.net/def/function/geosparql/>",
           "PREFIX osm: <https://www.openstreetmap.org/>",
           "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>",
           "PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>"]
    base = ["?stop osmkey:public_transport ?public_transport .",
            "?stop rdf:type osm:node .",
            "?stop geo:hasGeometry ?location .",
            "?stop osmkey:name ?name ."]
    binds = ["BIND (geof:latitude(?location) AS ?lat)",
             "BIND (geof:longitude(?location) AS ?lon)"]

    query_list = (pre + get_selection() +
                  get_transports() + base + get_optionals() + binds + ["}"])
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

    osm_data_to_file(r.content, path)
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
        return series.str.replace(
            get_abbreviations_regex(), replace_abbreviation, regex=True)

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
    return df.where(df["name"] != "").dropna(subset="name")


def get_osm_comments(include_date: bool = True) -> str:
    join_str = "\n#   "
    date = dt.date.today().strftime("%Y%m%d")
    query = join_str.join(get_osm_query().split("\n"))
    abbrevs = join_str.join(
        [f"{key}: {value}"
         for key, value in sorted(Config.name_abbreviations.items())])
    allowed_chars = sorted(Config.allowed_stop_chars)
    comments = [f"# Queried: {date}"] if include_date else[]
    comments += [f"# Query:{join_str}{query}",
                 f"# Abbreviations:{join_str}{abbrevs}",
                 f"# Allowed chars:{join_str}{allowed_chars}"]
    return "\n".join(comments) + "\n"


def osm_data_to_file(raw_data: bytes, path: Path):
    df = _clean_osm_data(raw_data)

    with open(path, "w") as fil:
        fil.write(get_osm_comments())

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


def read_csv(file: Path | BytesIO) -> Optional[pd.DataFrame]:
    return pd.read_csv(
        file,
        sep="\t",
        names=KEYS + KEYS_OPTIONAL,
        header=0,
        comment="#")


class Finder:
    def __init__(self, gtfs_handler: GTFSHandler):
        self.handler = gtfs_handler
        self.temp = None
        self.use_cache, cache_dir = create_cache_dir()
        self._set_fp(cache_dir)
        self._get_stop_data()
        self.routes: list[list[Node]] | None = None

    def _set_fp(self, cache_dir: Path):
        self.fp: Path = cache_dir.joinpath("osm_cache.tsv").resolve()
        self.temp = NamedTemporaryFile()
        if self.use_cache:
            return
        self.fp = Path(self.temp.name).resolve()

    def rebuild_cache(self) -> bool:
        """ Cache needs to be rebuilt, if it does not exist or is too old. """
        if not self.fp.exists() or Path(self.temp.name).resolve() == self.fp:
            return True
        return self._cache_is_stale() or self._query_different_from_cache()

    def _cache_is_stale(self) -> bool:
        with open(self.fp, "r") as fil:
            line = fil.readline().strip()

        msg = ("Cache was found, but does not seem valid. First line must "
               "be a comment '# Queried: YYYYMMDD', where YYYYMMDD is the "
               "date when the cache was created.")
        if not line.startswith("# Queried: "):
            logger.warning(msg)
            return True

        try:
            date = dt.datetime.now()
            date_str = line.split(": ")[1].strip()
            query_date = dt.datetime.strptime(date_str, "%Y%m%d")
        except (ValueError, IndexError):
            logger.warning(msg)
            return True

        return (date - query_date).days > Config.stale_cache_days

    def _query_different_from_cache(self) -> bool:
        lines = []
        with open(self.fp, "r") as fil:
            line = fil.readline().strip()
            while line.startswith("#"):
                lines.append(line)
                line = fil.readline()

        return get_osm_comments(False) == "\n".join(lines[1:]) + "\n"

    def _get_stop_data(self) -> None:
        if not self.use_cache or self.rebuild_cache():
            if not get_osm_data_from_qlever(self.fp):
                return

        try:
            df = read_csv(self.fp)
        except Exception as e:
            cache_str = " cached " if self.use_cache else " "
            logger.error(
                f"While trying to read the{cache_str}osm data an error "
                f"occurred:\n{e}\nStop location detection will be skipped.")
            df = None
        self.df: pd.DataFrame = df

    def _generate_routes(self) -> None:
        names = [stop.stop_name for stop in self.handler.stops.entries]
        self.routes = generate_routes2(names, self.df, self.handler)

    def get_shortest_route(self) -> Optional[list[Node]]:
        # STYLE: Weird roundabout way to do all this.
        self._generate_routes()
        if not self.routes:
            return None
        names = [stop.stop_name for stop in self.handler.stops.entries]
        route = select_shortest_route(names, self.routes)
        if Config.display_route in [1, 3, 5, 7] and route:
            display_route(route, False, False)
        return route
