from __future__ import annotations

import datetime as dt
import itertools
import logging
import operator
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
from finder.osm_values import get_all_cat_scores
from finder.location_finder import find_stop_nodes, update_missing_locations
from finder.location_nodes import display_nodes, MissingNode, Node
from utils import (get_abbreviations_regex, get_edit_distance,
                   replace_abbreviation, SPECIAL_CHARS)


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

logger = logging.getLogger(__name__)

DF: TypeAlias = pd.DataFrame
StopID: TypeAlias = str
StopName: TypeAlias = str
StopIdent: TypeAlias = tuple[StopID, StopName]
Route: TypeAlias = list[StopIdent]
Routes: TypeAlias = list[Route]
RouteStopIDs: TypeAlias = list[tuple[StopID]]
StopsNode: TypeAlias = dict[StopID, Node]
StopsNodes: TypeAlias = dict[StopID, list[Node]]


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


def _cleanup_name(raw_series: pd.Series) -> pd.Series:
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

    return (raw_series
            .pipe(_normalize)
            .pipe(_replace_abbreviations)
            .pipe(_remove_forbidden_chars)
            .pipe(_cleanup_spaces))


def _clean_osm_data(raw_data: bytes) -> pd.DataFrame:
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
        self.full_df: pd.DataFrame = df

    def find(self) -> dict[str: Location]:
        def _search_stop_nodes_of_all_routes() -> StopsNodes:
            routes: Routes = get_routes(self.handler)
            nodes: dict[str: list[Node]] = {}
            for route in routes:
                stop_nodes = find_stop_nodes(self.handler, route, df)
                for stop_id, node in stop_nodes.items():
                    nodes.setdefault(stop_id, []).append(node)
                route = list(reversed(route))
                stop_nodes = find_stop_nodes(self.handler, route, df)
                for stop_id, node in stop_nodes.items():
                    nodes.setdefault(stop_id, []).append(node)
            return nodes

        def _select_best_node(stop_nodes: list[Node]) -> Node:
            nodes = [n for n in stop_nodes if not isinstance(n, MissingNode)]
            missing = [n for n in stop_nodes if isinstance(n, MissingNode)]
            if not nodes:
                return missing[0]
            nodes_unique = set(nodes)
            nodes_count = {n: nodes.count(n) for n in nodes_unique}
            node_with_max_count = max(nodes, key=nodes_count.get)
            return node_with_max_count

        def _select_best_nodes(stops_nodes: StopsNodes) -> StopsNode:
            nodes: dict[str: Node] = {}
            for stop_id, stop_nodes in stops_nodes.items():
                nodes[stop_id] = _select_best_node(stop_nodes)
            return nodes

        df = get_df(self.handler.stops.entries, self.full_df)

        logger.info("Searching for the stop locations of each route.")
        t = time()

        route_stop_nodes = _search_stop_nodes_of_all_routes()
        best_nodes = _select_best_nodes(route_stop_nodes)
        logger.info(f"Done. Took {time() - t:.2f}s")

        if Config.display_route in [1, 3, 5, 7]:
            update_missing_locations(list(best_nodes.values()))
            display_nodes(list(best_nodes.values()))
        return best_nodes


def get_df(stop_entries: list, raw_df: DF) -> DF:
    def _split_df(df: DF) -> DF:
        logger.info("Splitting DataFrame based on stop names...")
        t = time()
        stops = [(stop.stop_id, stop.stop_name) for stop in stop_entries]
        prefiltered_df = prefilter_df([name for _, name in stops], df)
        df = add_extra_columns(stops, prefiltered_df)
        logger.info(f"Done. Took {time() - t:.2f}s")
        return df

    def _calculate_location_costs(df: DF) -> DF:
        logger.info(f"Calculating location costs based on the selected "
                    f"routetype '{Config.gtfs_routetype.name}'...")
        t = time()
        full_df = fix_df(df)
        df.loc[:, "node_cost"] = get_node_cost(full_df)
        df = df.loc[:, ["lat", "lon", "names",
                        "node_cost", "stop_id", "idx", "name_cost"]]
        logger.info(f"Done. Took {time() - t:.2f}s")
        return df

    split_df = _split_df(raw_df)
    cost_df = _calculate_location_costs(split_df)
    return cost_df


def get_df_with_min_cost(df: DF) -> DF:
    # TODO NOW: Use to get the stop_costs?
    min_costs = df.groupby("stop_id", sort=False)["node_cost"].agg("min")
    cum_costs = min_costs.cumsum()
    cum_costs.name = "min_cost"
    df2 = pd.merge(df, cum_costs, left_on="stop_id", right_on="stop_id")
    df2["min_cost"] = df2["min_cost"] + df2["node_cost"]
    return df2


def get_routes(handler: GTFSHandler) -> Routes:
    def get_stop_ids_from_gtfs_routes() -> RouteStopIDs:
        stop_ids: list[tuple[str]] = []
        for route in handler.routes.entries:
            stop_ids += handler.get_stop_ids(route.route_id)
        return stop_ids

    def get_routes_from_stop_ids(stop_ids: RouteStopIDs) -> Routes:
        def __get_route_from_stop_id(stop_id: StopID) -> StopIdent:
            return stop_id, handler.stops.get_by_stop_id(stop_id).stop_name

        routes = []
        for stop_ids in set(stop_ids):
            routes.append(list(map(__get_route_from_stop_id, stop_ids)))
        routes = sorted(routes, key=len, reverse=True)
        return routes

    def remove_routes_contained_by_others(raw_routes: Routes) -> Routes:
        def __route_is_contained(r1: Route, r2: Route) -> bool:
            start_idx = r1.index(r2[0]) if r2[0] in r1 else None
            if start_idx is None:
                return False

            # No need to check for length, as r1 has at least the length of r2.
            for idx, stop in enumerate(r2, start_idx):
                if r1[idx] == stop:
                    return False
            return True

        routes = [raw_routes[0]]
        for route_idx, new_route in enumerate(raw_routes[1:], 1):
            for route in routes:
                if __route_is_contained(route, new_route):
                    continue
            routes.append(new_route)

        return routes

    route_stop_ids = get_stop_ids_from_gtfs_routes()
    duplicate_routes = get_routes_from_stop_ids(route_stop_ids)
    clean_routes = remove_routes_contained_by_others(duplicate_routes)
    return clean_routes


def _normalize_stop(stop: str) -> str:
    return _cleanup_name(pd.Series([stop])).iloc[0]


def _create_stop_regex(stop: str, add_permutations: str) -> str:
    def _get_permutations(string: str) -> list[str]:
        if add_permutations == "none":
            return [string]

        words = string.split(" ")

        n = len(words)
        range_args = (1, n + 1) if add_permutations == "all" else (n, n + 1)

        perms_list: list[list[str]] = []
        for i in range(*range_args):
            perms_list.append(list(itertools.permutations(words, i)))
        perm_str = [" ".join(perm) for perms in perms_list for perm in perms]
        perm_str.sort(key=operator.methodcaller("count", " "), reverse=True)
        return perm_str

    assert add_permutations in ["all", "max", "none"]
    permutations = _get_permutations(stop)
    if add_permutations == "all":
        regex_list = [rf"\b{re.escape(perm)}\b" for perm in permutations]
    else:
        regex_list = [re.escape(perm) for perm in _get_permutations(stop)]
    regex = "|".join(regex_list)
    return regex


def _compile_regex(regex: str) -> re.Pattern[str]:
    flags = re.IGNORECASE + re.UNICODE
    return re.compile(regex, flags=flags)


def _filter_df_by_stop(stop: str, full_df: DF) -> DF:
    c_regex = _compile_regex(_create_stop_regex(_normalize_stop(stop), "none"))
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


def prefilter_df(stops: list[str], full_df: DF) -> DF:
    def remove_duplicates(duplicate_regex: str) -> str:
        return "|".join(set(duplicate_regex.split("|")))

    regexes = [_create_stop_regex(_normalize_stop(stop), "none")
               for stop in stops]
    unique_regex: str = remove_duplicates("|".join(regexes))
    df = full_df[full_df["names"].str.contains(
        unique_regex, regex=True, flags=re.IGNORECASE + re.UNICODE)]
    return df.copy()


def fix_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    def get_score(value: str) -> float:
        if value in bad:
            return bad_value
        try:
            return good[value] * 5
        except KeyError:
            return 20

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
    return full_df[KEYS_OPTIONAL].min(axis=1) ** 2 // 20
