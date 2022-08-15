import logging

from config import Config
from datastructures.gtfs_output.handler import GTFSHandler
from datastructures.timetable.table import TimeTable
from finder import Finder
from p2g_logging import initialize_logging
from reader import Reader
from user_input.arg_parser import parse_args


logger = logging.getLogger(__name__)


def get_timetables() -> list[TimeTable]:
    reader = Reader()
    timetables = reader.read()
    return timetables


def generate_gtfs(timetables) -> GTFSHandler:
    assert len(timetables) > 0
    gtfs_handler = GTFSHandler()
    for table in timetables:
        gtfs_handler.timetable_to_gtfs(table)
    return gtfs_handler


def match_coordinates(gtfs_handler: GTFSHandler):
    finder = Finder(gtfs_handler)
    if not finder.df:
        return None
    finder.generate_routes()
    return finder.get_shortest_route()


def main() -> None:
    parse_args()
    initialize_logging(logging.DEBUG)

    logger.info(f"Reading the following pages: {Config.pages.pages}.")

    tables = get_timetables()
    handler = generate_gtfs(tables)
    if not Config.disable_location_detection:
        route = match_coordinates(handler)
        handler.add_coordinates(route)
    handler.write_files()


if __name__ == "__main__":
    main()


# TODO: Error handling
