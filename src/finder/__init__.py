""" Subpackage to detect the locations of the stops. """
# TODO NOW: Split into osm_fetcher, location_detector, etc.


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
from typing import TYPE_CHECKING, TypeAlias
from urllib import parse

import pandas as pd
import requests
from requests.exceptions import ConnectionError

from config import Config
from datastructures.gtfs_output.stop import GTFSStopEntry
from finder.location import Location
from finder.location_finder import find_stop_nodes, update_missing_locations
from finder.location_nodes import display_nodes, MNode, Node
from finder.osm_values import get_all_cat_scores
from utils import normalize_series, normalize_name


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler

logger = logging.getLogger(__name__)

DF: TypeAlias = pd.DataFrame
StopID: TypeAlias = str
StopName: TypeAlias = str
StopIdent: TypeAlias = tuple[StopID, StopName]
Route: TypeAlias = list[StopIdent]
Routes: TypeAlias = dict[str: Route]
RouteStopIDs: TypeAlias = list[tuple[StopID]]
StopsNode: TypeAlias = dict[StopID, Node]
StopsNodes: TypeAlias = dict[StopID, list[Node]]

KEYS = ["lat", "lon", "public_transport"]
KEYS_OPTIONAL = ["railway", "bus", "tram",
                 "train", "subway", "monorail", "light_rail"]
NAME_KEYS = ["name", "alt_name", "ref_name",
             "short_name", "official_name", "loc_name"]


def get_qlever_query() -> str:
    """ Return the full query, usable by QLever. """

    def _union(a: str, b: str) -> str:
        # Union two statements. Uses \t as delimiter after/before braces.
        if not a:
            return b
        return f"{{\t{a}\t}} UNION {{\t{b}\t}}"

    def _to_identifier(key: str) -> str:
        return f"?{key}"

    def get_selection() -> list[str]:
        """ Return the select clause. """
        identifier = map(_to_identifier, KEYS + KEYS_OPTIONAL)
        group_concat = " (GROUP_CONCAT(?name;SEPARATOR=\"|\") AS ?names)"
        variables = " ".join(identifier) + group_concat
        return ["SELECT {} WHERE {{".format(variables)]

    def get_transports() -> list[str]:
        """ Return a union of all possible public_transport values. """
        fmt = "?stop osmkey:public_transport \"{}\" ."
        transport = ""
        transport = _union(transport, fmt.format("station"))
        transport = _union(transport, fmt.format("stop_position"))
        transport = _union(transport, fmt.format("platform"))
        return transport.strip().split("\t")

    def get_names() -> list[str]:
        """ Return a union of clauses, based on the different name keys. """
        name_fmt = "?stop osmkey:{} ?name ."
        names = ""
        for name_key in NAME_KEYS:
            names = _union(names, name_fmt.format(name_key))
        return names.strip().split("\t")

    def get_optionals() -> list[str]:
        """ Get the clause for all optional keys. """
        fmt = "OPTIONAL {{ ?stop osmkey:{0} ?{0} . }}"
        return [fmt.format(key) for key in KEYS_OPTIONAL]

    def get_group_by() -> list[str]:
        """ Group-by statement, grouping by optional and mandatory keys. """
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


def get_osm_data_from_qlever(filepath: Path) -> bool:
    """ Saves the osm data fetched using QLever in the given filepath.

    :return: True, if fetching and writing was successful, False otherwise.
    """
    base_url = "https://qlever.cs.uni-freiburg.de/api/osm-germany/?"
    data = {"action": "tsv_export", "query": get_qlever_query()}
    url = base_url + parse.urlencode(data)

    try:
        r = requests.get(url)
    except ConnectionError as e:
        logger.error(f"Could not get osm data: {e}")
        return False

    if r.status_code != 200:
        logger.error(f"Could not get osm data: {r}\n{r.content}")
        return False

    # TODO NOW: Try -> except
    osm_data_to_file(r.content, filepath)

    return True


def _clean_osm_data(raw_data: bytes) -> pd.DataFrame:
    df = read_csv(BytesIO(raw_data))
    df["names"] = normalize_series(df["names"])
    # Remove entries with empty name.
    return df[df["names"] != ""]


def get_osm_comments(include_date: bool = True) -> str:
    """ Return the comment that would be written to the top of the cache,
    if the cache would be created right now. Uses get_qlever_query. """

    join_str = "\n#   "
    date = dt.date.today().strftime("%Y%m%d")
    query = join_str.join(get_qlever_query().split("\n"))
    abbrevs = join_str.join(
        [f"{key}: {value}"
         for key, value in sorted(Config.name_abbreviations.items())])
    allowed_chars = sorted(Config.allowed_stop_chars)
    comments = [f"# Queried: {date}"] if include_date else []
    comments += [f"# Query:{join_str}{query}",
                 f"# Abbreviations:{join_str}{abbrevs}",
                 f"# Allowed chars:{join_str}{allowed_chars}"]
    return "\n".join(comments) + "\n"


def osm_data_to_file(raw_data: bytes, filepath: Path):
    """ Writes the given raw_data to the given filepath,
    overwriting existing files. """
    df = _clean_osm_data(raw_data)

    with open(filepath, "w") as fil:
        fil.write(get_osm_comments())

    df.to_csv(filepath, sep="\t", header=False, index=False, mode="a")


def get_cache_dir_path() -> Path | None:
    """ Return the system dependent path to the cache directory. """

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
    """ Read the given file or stream with pandas' read_csv.

    The file/stream must be CSV structured.
    Return a DataFrame with the content.
    """

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
    """ Handles the cache/dataframe creation. """

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
        def _get_line() -> str:
            return fil.readline().strip()

        lines = []
        with open(self.fp, "r") as fil:
            line = _get_line()
            while line.startswith("#"):
                if line != "#":
                    lines.append(line)
                line = _get_line()
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

    def find_location_nodes(self) -> dict[str: Location]:
        """ Return a dictionary of all stops and their locations. """

        def _search_stop_nodes_of_all_routes() -> StopsNodes:
            routes: Routes = get_unique_routes(self.handler)
            nodes: dict[str: list[Node]] = {}
            for route_id, route in routes.items():
                stop_nodes = find_stop_nodes(self.handler, route_id, route, df)
                for stop_id, node in stop_nodes.items():
                    nodes.setdefault(stop_id, []).append(node)
                # TODO: Add search for reversed as well.
            return nodes

        def _select_best_node(stop_nodes: list[Node]) -> Node:
            nodes = [n for n in stop_nodes if not isinstance(n, MNode)]
            missing = [n for n in stop_nodes if isinstance(n, MNode)]
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

        used_stops = [e for e in self.handler.stops.entries
                      if e.used_in_timetable]
        df = get_df(used_stops, self.full_df)

        logger.info("Searching for the stop locations of each route.")
        t = time()

        route_stop_nodes = _search_stop_nodes_of_all_routes()
        best_nodes = _select_best_nodes(route_stop_nodes)
        logger.info(f"Done. Took {time() - t:.2f}s")

        update_missing_locations(list(best_nodes.values()), True)
        if Config.display_route in [1, 3, 5, 7]:
            display_nodes(list(best_nodes.values()))
        return best_nodes


def get_df(stop_entries: list, raw_df: DF) -> DF:
    """ Split the dataframe and add the calculated node costs. """

    def _split_df(df: DF) -> DF:
        logger.info("Splitting DataFrame based on stop names...")
        t = time()
        stops = [(stop.stop_id, stop.stop_name) for stop in stop_entries]
        prefiltered_df = prefilter_df([name for _, name in stops], df)
        df = add_extra_columns(stops, prefiltered_df)
        logger.info(f"Done. Took {time() - t:.2f}s")
        return df

    def _calculate_node_costs(df: DF) -> DF:
        logger.info(f"Calculating location costs based on the selected "
                    f"routetype '{Config.gtfs_routetype.name}'...")
        t = time()
        full_df = node_score_strings_to_int(df)
        df.loc[:, "node_cost"] = get_node_cost(full_df)
        df = df.loc[:, ["lat", "lon", "names",
                        "node_cost", "stop_id", "idx", "name_cost"]]
        logger.info(f"Done. Took {time() - t:.2f}s")
        return df

    split_df = _split_df(raw_df)
    cost_df = _calculate_node_costs(split_df)
    return cost_df


def get_unique_routes(handler: GTFSHandler) -> Routes:
    """ Return a list of unique routes.

    The list contains unique combinations of stops occuring in the tables.
    If one combination is contained by another, only return the containing one.
    """

    def route_is_contained(contained_route_id: str) -> bool:
        """ Return if the route is contained by any other. """

        def _route_contains_stops(
                container: list[GTFSStopEntry], stops: list[GTFSStopEntry]
                ) -> bool:
            """ Return if all stops are in container, in the right order. """
            # No need to check for length, as r1 has at least the length of r2.
            # Copy to prevent changing the list using pop.
            stops = list(stops)
            for container_stop in container:
                if stops and stops[0] == container_stop:
                    stops.pop(0)

            return not stops

        route_stops = handler.get_stops_of_route(contained_route_id)

        for existing_route_id in routes:
            existing_stops = handler.get_stops_of_route(existing_route_id)
            if _route_contains_stops(existing_stops, route_stops):
                return True

        return False

    route_ids: list[str] = [r.route_id for r in handler.routes.entries]
    # Need to sort routes by number of stops.
    route_ids.sort(key=lambda r: len(handler.get_stops_of_route(r)),
                   reverse=True)

    routes: Routes = {}
    for route_id in route_ids:
        if route_is_contained(route_id):
            continue
        route = [(stop.stop_id, stop.stop_name)
                 for stop in handler.get_stops_of_route(route_id)]
        routes[route_id] = route

    return routes


def _create_stop_regex(stop: str) -> str:
    name = normalize_name(stop)
    regex = " ".join([rf"\b{re.escape(word)}\b" for word in name.split(" ")])
    return regex


def _filter_df_by_stop(stop: str, full_df: DF) -> DF:
    regex = _create_stop_regex(stop)
    df = full_df[full_df["names"].str.contains(regex, regex=True)]
    return df.copy()


def add_extra_columns(stops: list[tuple[str, str]], full_df: DF) -> DF:
    """ Add extra columns (name_cost, stop_id, idx) to the df. """

    def calculate_name_cost(names: list[str]) -> int:
        """ Calculate the minimum approximate edit distance to the stop.

        Because we know all names contain the stop's words, we simply
        calculate the difference in length, ignoring spaces.
        """
        name_lengths = [len(name.replace(" ", "")) for name in names]
        return min([abs(stop_length - length) for length in name_lengths])

    dfs = []
    for stop_id, stop in stops:
        df = _filter_df_by_stop(stop, full_df)
        stop_length = len(normalize_name(stop).replace(" ", ""))
        if df.empty:
            df[["name_cost", "stop_id", "idx"]] = None
            dfs.append(df)
            continue
        name_df = df["names"].str.split("|", regex=False)
        df.loc[:, "name_cost"] = name_df.map(calculate_name_cost)
        df.loc[:, "stop_id"] = stop_id
        df.loc[:, "idx"] = df.index
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def prefilter_df(stops: list[str], full_df: DF) -> DF:
    """ Filter the full_df, such that each entry contains a
    normalized stop name. """

    regexes = [_create_stop_regex(stop) for stop in stops]
    unique_regex: str = "|".join(set(regexes))
    df = full_df[full_df["names"].str.contains(unique_regex, regex=True)]
    return df.copy()


def node_score_strings_to_int(raw_df: pd.DataFrame) -> pd.DataFrame:
    """ Translate the OSM-key columns to int.

    Change the values of KEYS_OPTIONAL (i.e. the keys used to calculate
    the node score) in df, with its integer value, depending on the routetype.
    """

    def _get_score(value: str) -> float:
        if value in bad:
            return bad_value
        try:
            # STYLE: Adjust osm scores instead of doing this?
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
        df[key] = df[key].apply(_get_score)

    return df


def get_node_cost(full_df: pd.DataFrame) -> pd.DataFrame:
    """ Calculate the integer score based on KEYS_OPTIONAL. """
    return full_df[KEYS_OPTIONAL].min(axis=1) ** 2 // 20
