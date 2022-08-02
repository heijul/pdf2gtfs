import logging

from datastructures.gtfs_output.handler import GTFSHandler
from finder import Finder
from p2g_logging import initialize_logging

from reader import Reader
from config import Config
from cli.arg_parser import parse_args


logger = logging.getLogger(__name__)


def get_timetables():
    reader = Reader(Config.filename)
    timetables = reader.read()
    return timetables


def generate_gtfs(timetables):
    assert len(timetables) > 0
    gtfs_handler = GTFSHandler()
    for table in timetables:
        gtfs_handler.timetable_to_gtfs(table)
    return gtfs_handler


def match_coordinates(gtfs_handler: GTFSHandler):
    finder = Finder(gtfs_handler)
    # TODO: Check if osm_data could be fetched. If not -> abort adding coords
    finder.generate_routes()
    return finder.get_shortest_route()


def main():
    parse_args()
    initialize_logging(logging.DEBUG)

    logger.info(f"Reading the following pages: {Config.pages.pages}.")

    tables = get_timetables()
    handler = generate_gtfs(tables)
    route = match_coordinates(handler)
    handler.add_coordinates(route)
    handler.write_files()


if __name__ == "__main__":
    main()


# TODO: Add readme.md
# TODO: don't overwrite agency; Use agency from if single exists;
#  ask if multiple
# FIXME: When reading g10/u1 with pages=all, assertion fails,
#  because StopColumns are not recognized
