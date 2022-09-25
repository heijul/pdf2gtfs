from __future__ import annotations

import datetime as dt
import logging
import os.path
import platform
import re
from io import BytesIO
from math import inf
from os import makedirs
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import time
from typing import Optional, TYPE_CHECKING, TypeAlias
from urllib import parse

import numpy as np
import pandas as pd
import requests
from requests.exceptions import ConnectionError

from config import Config
from finder.location import Location
from finder.osm_node import OSMNode, Route3
from finder.osm_values import get_all_cat_scores
from finder.route_finder2 import display_route, find_shortest_route, Node
from finder.types import StopNames
from utils import (
    get_abbreviations_regex, get_edit_distance, replace_abbreviation,
    replace_abbreviations, SPECIAL_CHARS)


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

logger = logging.getLogger(__name__)

DF: TypeAlias = pd.DataFrame

KEYS = ["lat", "lon", "public_transport"]
KEYS_OPTIONAL = [
    "railway", "bus", "tram", "train", "subway", "monorail", "light_rail"]
NAME_KEYS = [
    "name", "alt_name", "ref_name", "short_name", "official_name", "loc_name"]


def get_osm_query(stop_positions=True, stations=True, platforms=True) -> str:
    def _union(a: str, b: str) -> str:
        # Union two statements. Uses \t as delimiter after/before braces.
        if not a:
            return b
        return f"{{\t{a}\t}} UNION {{\t{b}\t}}"

    def _to_identifier(key: str) -> str:
        return f"?{key}"

    def get_selection() -> list[str]:
        identifier = map(_to_identifier, KEYS + KEYS_OPTIONAL)
        group_concat = " (GROUP_CONCAT(?name;SEPARATOR=\"|\") AS ?names)"
        variables = " ".join(identifier) + group_concat
        return ["SELECT {} WHERE {{".format(variables)]

    def get_transports() -> list[str]:
        fmt = "?stop osmkey:public_transport \"{}\" ."
        transport = ""
        if stations:
            transport = _union(transport, fmt.format("station"))
        if stop_positions:
            transport = _union(transport, fmt.format("stop_position"))
        if platforms:
            transport = _union(transport, fmt.format("platform"))
        return transport.strip().split("\t")

    def get_names() -> list[str]:
        name_fmt = "?stop osmkey:{} ?name ."
        names = ""
        for name_key in NAME_KEYS:
            names = _union(names, name_fmt.format(name_key))
        return names.strip().split("\t")

    def get_optionals() -> list[str]:
        fmt = "OPTIONAL {{ ?stop osmkey:{0} ?{0} . }}"
        return [fmt.format(key) for key in KEYS_OPTIONAL]

    def get_group_by() -> list[str]:
        fmt = "GROUP BY {}"
        identifier = " ".join(map(_to_identifier, KEYS + KEYS_OPTIONAL))
        return [fmt.format(identifier)]

    pre = ["PREFIX osmrel: <https://www.openstreetmap.org/relation/>",
           "PREFIX geo: <http://www.opengis.net/ont/geosparql#>",
           "PREFIX geof: <http://www.opengis.net/def/function/geosparql/>",
           "PREFIX osm: <https://www.openstreetmap.org/>",
           "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>",
           "PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>"]
    base = ["?stop osmkey:public_transport ?public_transport .",
            "?stop rdf:type osm:node .",
            "?stop geo:hasGeometry ?location ."]
    binds = ["BIND (geof:latitude(?location) AS ?lat)",
             "BIND (geof:longitude(?location) AS ?lon)"]

    query_list = (pre + get_selection() +
                  get_transports() + base + get_names() +
                  get_optionals() + binds + ["}"] + get_group_by())
    return " \n".join(query_list)


def get_osm_data_from_qlever(path: Path) -> bool:
    base_url = "https://qlever.cs.uni-freiburg.de/api/osm-germany/?"
    data = {"action": "tsv_export", "query": get_osm_query()}
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
        return series.str.lower().str.casefold().str.strip()

    def _replace_abbreviations(series: pd.Series) -> pd.Series:
        return series.str.replace(
            get_abbreviations_regex(), replace_abbreviation, regex=True)

    def _remove_forbidden_chars(series: pd.Series) -> pd.Series:
        # Match parentheses and all text enclosed by them.
        parentheses_re = r"(\(.*\))"
        allowed_chars = "".join(Config.allowed_stop_chars)
        # Match all chars other than the allowed ones.
        char_re = fr"([^a-zA-Z\d\|{SPECIAL_CHARS}{allowed_chars}])"
        regex = "|".join([parentheses_re, char_re])
        return series.str.replace(regex, " ", regex=True)

    def _cleanup_spaces(series: pd.Series) -> pd.Series:
        # Remove consecutive, as well as leading/trailing spaces.
        return series.str.replace(" +", " ", regex=True)

    def _cleanup_name(series: pd.Series):
        return (series
                .pipe(_normalize)
                .pipe(_replace_abbreviations)
                .pipe(_remove_forbidden_chars)
                .pipe(_cleanup_spaces))

    df = read_csv(BytesIO(raw_data))
    df["names"] = _cleanup_name(df["names"])
    # Remove entries with empty name.
    return df[df["names"] != ""]


def get_osm_comments(include_date: bool = True) -> str:
    join_str = "\n#   "
    date = dt.date.today().strftime("%Y%m%d")
    query = join_str.join(get_osm_query().split("\n"))
    abbrevs = join_str.join(
        [f"{key}: {value}"
         for key, value in sorted(Config.name_abbreviations.items())])
    allowed_chars = sorted(Config.allowed_stop_chars)
    comments = [f"# Queried: {date}"] if include_date else []
    comments += [f"# Query:{join_str}{query}",
                 f"# Abbreviations:{join_str}{abbrevs}",
                 f"# Allowed chars:{join_str}{allowed_chars}"]
    return "\n".join(comments) + "\n"


def osm_data_to_file(raw_data: bytes, path: Path):
    df = _clean_osm_data(raw_data)

    with open(path, "w") as fil:
        fil.write(get_osm_comments())

    df.to_csv(path, sep="\t", header=False, index=False, mode="a")


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
    dtype = {"lat": float, "lon": float,
             "public_transport": str, "names": str}
    for key in KEYS_OPTIONAL:
        dtype[key] = str

    return pd.read_csv(
        file,
        sep="\t",
        names=KEYS + KEYS_OPTIONAL + ["names"],
        dtype=dtype,
        keep_default_na=False,
        header=0,
        comment="#")


class Finder:
    def __init__(self, gtfs_handler: GTFSHandler):
        self.handler = gtfs_handler
        self.temp = None
        self.use_cache, cache_dir = create_cache_dir()
        self._set_fp(cache_dir)
        self._get_stop_data()
        self.routes: list[Route3] | None = None

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
        return self._cache_is_stale() or not self._query_same_as_cache()

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

    def _query_same_as_cache(self) -> bool:
        def get_line() -> str:
            return fil.readline().strip()

        lines = []
        with open(self.fp, "r") as fil:
            line = get_line()
            while line.startswith("#"):
                if line != "#":
                    lines.append(line)
                line = get_line()
        cache_comments = lines[1:]
        current_comments = [
            line.strip()
            for line in get_osm_comments(False).split("\n") if line]

        return current_comments == cache_comments

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

    def find(self) -> dict[str: Location]:
        stops = [(stop.stop_id, stop.stop_name)
                 for stop in self.handler.stops.entries]
        logger.info("Splitting DataFrame based on stop names...")
        t = time()
        prefiltered_df = prefilter_df([name for _, name in stops], self.df)
        df = add_extra_columns(stops, prefiltered_df)
        logger.info(f"Done. Took {time() - t:.2f}s")

        logger.info(f"Calculating location scores based on the selected "
                    f"routetype '{Config.gtfs_routetype.name}'...")
        t = time()
        full_df = fix_df(df)
        df.loc[:, "node_cost"] = get_node_cost(full_df)
        df = df.loc[:, ["lat", "lon", "names",
                        "node_cost", "stop_id", "idx", "name_cost"]]
        logger.info(f"Done. Took {time() - t:.2f}s")
        # TODO NOW: Create multiindex
        # TODO NOW: Fill empty stops with dummy values.
        # TODO NOW: Split
        logger.info("Searching for the stop locations of each route.")
        t = time()
        # TODO NOW: Remove routes which are contained by others.
        routes_names: list[list[tuple[str, str]]] = get_routes_names(self.handler)
        stops_nodes: dict[str: list[Node]] = {}
        for route_names in routes_names:
            route: dict[str: Node] = find_shortest_route(self.handler, route_names, df)
            for stop_id, node in route.items():
                stops_nodes.setdefault(stop_id, []).append(node)

        # Get best location for all stops
        stops_node: dict[str: Location] = {}
        for stop_id, nodes in stops_nodes.items():
            nodes_unique = set(nodes)
            nodes_count = {node: nodes.count(node) for node in nodes_unique}
            node_with_max_count = max(nodes, key=lambda x: nodes_count[x])
            stops_node[stop_id] = node_with_max_count
        if Config.display_route in [1, 3]:
            display_route(list(stops_node.values()))

        logger.info(f"Done. Took {time() - t:.2f}s")
        return stops_node


def get_df_with_min_cost(df: DF) -> DF:
    min_costs = df.groupby("stop_id", sort=False)["node_cost"].agg("min")
    cum_costs = min_costs.cumsum()
    cum_costs.name = "min_cost"
    df2 = pd.merge(df, cum_costs, left_on="stop_id", right_on="stop_id")
    df2["min_cost"] = df2["min_cost"] + df2["node_cost"]
    return df2


def get_routes_names(handler: GTFSHandler) -> list[list[tuple[str, str]]]:
    # Get routes from gtfs_routes
    route_stop_ids: list[tuple[str]] = []
    for route in handler.routes.entries:
        route_stop_ids += handler.get_stop_ids(route.route_id)
    # Get names from routes
    routes = []
    for stop_ids in set(route_stop_ids):
        routes.append(
            [(stop_id, handler.stops.get_by_stop_id(stop_id).stop_name)
             for stop_id in stop_ids])
    return sorted(routes, key=len, reverse=True)


def _normalize_stop(stop: str) -> str:
    return replace_abbreviations(stop).casefold().lower()


def _create_stop_regex(stop: str) -> str:
    def _remove_forbidden_chars(string: str) -> str:
        # Match parentheses and all text enclosed by them.
        parentheses_re = r"(\(.*\))"
        allowed_chars = "".join(Config.allowed_stop_chars)
        # Match all chars other than the allowed ones.
        char_re = fr"([^a-zA-Z\d\|{SPECIAL_CHARS}{allowed_chars}])"
        regex = "|".join([parentheses_re, char_re])
        return re.sub(regex, " ", string, flags=re.I + re.U)

    def _cleanup_spaces(string: str) -> str:
        # Remove consecutive, as well as leading/trailing spaces.
        return re.sub(" +", " ", string, flags=re.I + re.U)

    return "|".join([re.escape(_cleanup_spaces(_remove_forbidden_chars(s)))
                     for s in stop.split("|")])


def _compile_regex(regex: str) -> re.Pattern[str]:
    flags = re.IGNORECASE + re.UNICODE
    return re.compile(regex, flags=flags)


def _filter_df_by_stop(stop: str, full_df: DF) -> DF:
    c_regex = _compile_regex(_create_stop_regex(_normalize_stop(stop)))
    df = full_df[full_df["names"].str.contains(c_regex, regex=True)]
    return df.copy()


def add_extra_columns(stops: list[tuple[str, str]], full_df: DF) -> DF:
    def name_distance(names: np.array) -> list[int]:
        """ Edit distance between name and stop after normalizing both. """
        distances = []
        normal_stop = _normalize_stop(stop)
        for name in names:
            normal_name = _normalize_stop(name[0])
            if normal_name == normal_stop:
                dist = 0
            else:
                dist = get_edit_distance(normal_name, normal_stop)
            distances.append(dist)
        return distances

    dfs = []
    for stop_id, stop in stops:
        df = _filter_df_by_stop(stop, full_df)
        if df.empty:
            continue
        df.loc[:, "name_cost"] = df[["names"]].apply(name_distance, raw=True)
        df.loc[:, "stop_id"] = stop_id
        df.loc[:, "idx"] = df.index
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def prefilter_df(stops: StopNames, full_df: DF) -> DF:
    regexes = [_create_stop_regex(_normalize_stop(stop)) for stop in stops]
    df = full_df[full_df["names"].str.contains(
        "|".join(regexes), regex=True, flags=re.IGNORECASE + re.UNICODE)]
    return df.copy()


def fix_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    def get_score(value: str) -> float:
        if value in bad:
            return bad_value
        try:
            return good[value]
        except KeyError:
            return 10

    bad_value = inf
    # Apply cat scores
    goods, bads = get_all_cat_scores()
    df = raw_df.copy()
    for key in KEYS_OPTIONAL:
        good = goods.get(key, {})
        bad = bads.get(key, {})
        df[key] = df[key].apply(get_score)

    return df


def get_node_cost(full_df: pd.DataFrame) -> pd.DataFrame:
    return full_df[KEYS_OPTIONAL].sum(axis=1)
