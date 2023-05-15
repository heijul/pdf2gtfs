""" Provides a fetcher for OSM data using QLever. """

import os
import platform
from datetime import datetime as dt
from io import BytesIO
from logging import getLogger
from pathlib import Path
from time import time
from urllib import parse

import pandas as pd
import requests

from pdf2gtfs.config import Config
from pdf2gtfs.locate.finder.loc_nodes import OSMNode
from pdf2gtfs.utils import normalize_series


logger = getLogger(__name__)
KEYS = ["lat", "lon", "public_transport"]
# Keys are case-sensitive.
CAT_KEYS = ["railway", "bus", "tram",
            "train", "subway", "monorail", "light_rail"]
NAME_KEYS = ["name", "alt_name", "ref_name",
             "short_name", "official_name", "loc_name"]


class OSMFetcher:
    """ Provides an interface to get a dataframe of scored OSM data. """

    def __init__(self) -> None:
        self.qlever_url = Config.qlever_endpoint_url

    @property
    def cache_path(self) -> Path:
        """ The absolute path to the cache. """
        return get_and_create_cache_dir().joinpath("osm_cache.tsv")

    def cache_needs_rebuild(self) -> bool:
        """ Check if the cache needs to be rebuilt. """

        def cache_is_stale() -> bool:
            """ Return if the cache is older than the configured days. """
            with open(self.cache_path, "r", encoding="utf-8") as fil:
                line = fil.readline().strip()

            msg = ("Cache was found, but does not seem valid. "
                   "First line must be a comment '# Queried: YYYYMMDD', "
                   "where YYYYMMDD is the date when the cache was created."
                   "OSM data will be fetched again.")
            if not line.startswith("# Queried: "):
                logger.warning(msg)
                return True

            try:
                date = dt.now()
                query_date = dt.strptime(line.strip(), "# Queried: %Y%m%d")
                return (date - query_date).days > Config.stale_cache_days
            except (ValueError, IndexError):
                logger.warning(msg)
                return True

        def query_same_as_cache() -> bool:
            """ Return if the query and the cache's query are the same. """
            lines = []
            # Get all starting comments of the file.
            with open(self.cache_path, "r", encoding="utf-8") as fil:
                line = fil.readline().strip()
                while line.startswith("#"):
                    if line != "#":
                        lines.append(line)
                    line = fil.readline().strip()
            # Remove the '# ' from the comments.
            cache_comments = lines[1:]
            comment_list = get_osm_comments(False).split("\n")
            current_comments = [line.strip() for line in comment_list if line]

            return current_comments == cache_comments

        return cache_is_stale() or not query_same_as_cache()

    def read_cache(self) -> pd.DataFrame:
        """ Read the cached DataFrame.

        If no cache exists, return None instead.
        """
        if not self.cache_path.exists() or self.cache_needs_rebuild():
            return pd.DataFrame()
        dataframe = read_data(self.cache_path)
        return dataframe

    def write_cache(self, df: pd.DataFrame) -> None:
        """ Write the dataframe to disk. """
        # Write the comments first.
        with open(self.cache_path, "w", encoding="utf-8") as fil:
            fil.write(get_osm_comments())
        df.to_csv(
            self.cache_path, sep="\t", header=False, index=False, mode="a")
        logger.info(f"OSM data was cached at {self.cache_path}.")

    def _get_raw_osm_data(self, query: str) -> tuple[bool, bytes | None]:
        t = time()
        logger.info("Cache needs to be rebuilt. Fetching OSM data from "
                    "QLever...")
        data = {"action": "tsv_export", "query": query}
        url = self.qlever_url + parse.urlencode(data)
        try:
            request = requests.get(url)
        except ConnectionError as e:
            logger.error(f"Could not get osm data: {e}")
            return False, None

        if request.status_code == 200:
            logger.info(f"Done fetching OSM data from QLever. "
                        f"Took {time() - t:.2f}s.")
            return True, request.content

        logger.error(f"Could not get osm data: {request}\n{request.content}")
        return False, None

    def fetch(self) -> pd.DataFrame:
        """ Fetches the data from OSM. """
        t = time()
        logger.info("Looking for existing location information...")
        # Build query.
        query = get_qlever_query()
        # Check if query is cached and cache is fresh.
        cached_df: pd.DataFrame = self.read_cache()
        if not cached_df.empty:
            logger.info(f"Done. Found valid cache with "
                        f"{len(cached_df)} entries.")
            return cached_df
        # Fetch data.
        success, raw_data = self._get_raw_osm_data(query)
        if not success:
            logger.warning("Could not fetch OSM data using QLever. Will be "
                           "unable to continue location detection.")
            return pd.DataFrame()
        # Create dataframe.
        dataframe = raw_osm_data_to_dataframe(raw_data)
        # An empty cache needs not to be cached.
        if dataframe.empty:
            logger.warning("Fetching OSM data returned no results. Will be "
                           "unable to continue location detection.")
            return dataframe
        # Cache dataframe.
        self.write_cache(dataframe)
        logger.info(f"Done fetching location information. "
                    f"Took {time() - t:.2f}s.")
        return dataframe


def get_cache_dir(fallback_dir: Path) -> Path:
    """ Return the system dependent path to the cache directory.

If system is not one of linux or windows, return None instead.
"""
    if Config.cache_directory:
        return Config.cache_directory
    system = platform.system().lower()
    if system == "windows":
        return Path(os.path.expandvars("%LOCALAPPDATA%/pdf2gtfs/")).resolve()
    if system == "linux":
        return Path(os.path.expanduser("~/.cache/pdf2gtfs/")).resolve()

    fallback_msg = f"Using fallback cache directory ({fallback_dir})."
    logger.warning("Could not determine system platform. " + fallback_msg)
    return fallback_dir


def create_cache_dir(path: Path, fallback_dir: Path) -> Path:
    """ Tries to create the cache directory.

If creation fails, use the fallback cache directory.
"""
    fallback_msg = f"Using fallback cache directory ({fallback_dir})."
    if path.exists():
        if path.is_dir():
            return path
        logger.warning(f"Cache directory '{path}' appears to be a file. "
                       f"You need to move or remove that file to use the "
                       f"default system cache. " + fallback_msg)
        return fallback_dir
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError as e:
        logger.warning(f"Cache directory could not be created. "
                       f"Reason: '{e}'\n" + fallback_msg)
        return fallback_dir


def get_and_create_cache_dir() -> Path:
    """ Get the cache directory path. Create it, if it does not exist.

    If this fails at any point, the src directory will be used as fallback.
    """

    fallback_dir = Config.p2g_dir
    path = get_cache_dir(fallback_dir)
    path = create_cache_dir(path, fallback_dir)
    return path


def get_osm_comments(include_date: bool = True) -> str:
    """ Return the comment that would be written to the top of the cache,
    if the cache would be created right now. Uses get_qlever_query. """

    join_str = "\n#   "
    date = dt.now().strftime("%Y%m%d")
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
        identifier = map(_to_identifier,
                         KEYS + CAT_KEYS + list(OSMNode.optionals))
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
        fmt = "OPTIONAL {{ ?stop osmkey:{} ?{} . }}"
        return ([fmt.format(key, key) for key in CAT_KEYS]
                + [fmt.format(OSMNode.get_optional_key(k), k)
                   for k in OSMNode.optionals])

    def get_group_by() -> list[str]:
        """ Group-by statement, grouping by optional and mandatory keys. """
        fmt = "GROUP BY {}"
        identifier = " ".join(map(_to_identifier,
                                  KEYS + CAT_KEYS + list(OSMNode.optionals)))
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


def raw_osm_data_to_dataframe(raw_data: bytes) -> pd.DataFrame:
    """ Reads the feed and normalizes the names. """
    t = time()
    logger.info("Normalizing the stop names...")
    df = read_data(BytesIO(raw_data))
    df["names"] = normalize_series(df["names"])
    logger.info(f"Done. Took {time() - t:.2f}s.")
    return remove_entries_without_name(df)


def remove_entries_without_name(df: pd.DataFrame) -> pd.DataFrame:
    """ Remove all entries, that do not have a name. """
    full_count = len(df)
    df = df[df["names"] != ""]
    count = full_count - len(df)
    if count == 0:
        return df
    loc_str = "location" if count == 1 else "locations"
    logger.info(f"Dropped {count} {loc_str} without name from the dataframe.")
    return df


def read_data(path_or_stream: Path | BytesIO) -> pd.DataFrame:
    """ Read the given file or stream with pandas' read_csv.

    The file/stream must be CSV structured, using tabs as seperator.
    """

    dtype = {"lat": float, "lon": float,
             "public_transport": str, "names": str}
    for key in CAT_KEYS + list(OSMNode.optionals):
        dtype[key] = str

    return pd.read_csv(
        path_or_stream,
        sep="\t",
        names=KEYS + CAT_KEYS + list(OSMNode.optionals) + ["names"],
        dtype=dtype,
        keep_default_na=False,
        header=0,
        comment="#")
