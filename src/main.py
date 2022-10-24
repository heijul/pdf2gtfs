""" pdf2gtfs main. From here all methods are called to create a gtfs archive
from the given pdf file. """

import logging
from typing import TYPE_CHECKING

from config import Config
from datastructures.gtfs_output.handler import GTFSHandler
from finder import Finder, Node
from p2g_logging import initialize_logging
from reader import Reader
from user_input.arg_parser import parse_args
from user_input.cli import create_output_directory


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable

logger = logging.getLogger(__name__)


def get_timetables() -> list["TimeTable"]:
    """ Returns all timetables in the pdf within the given pages. """
    logger.info(f"Reading the following pages: {Config.pages.pages}.")
    reader = Reader()
    timetables = reader.read()
    return timetables


def generate_gtfs(timetables) -> GTFSHandler:
    """ Create the GTFSHandler and add each given timetable to it. """
    assert len(timetables) > 0
    gtfs_handler = GTFSHandler()
    for table in timetables:
        gtfs_handler.timetable_to_gtfs(table)
    return gtfs_handler


def match_coordinates(gtfs_handler: GTFSHandler) -> list[Node]:
    """ Find the locations of the stops defined in the gtfs_handler. """
    finder: Finder = Finder(gtfs_handler)
    locations = finder.find_location_nodes()
    return locations if locations else None


def main() -> None:
    """ Main function. """
    parse_args()
    initialize_logging(logging.DEBUG)

    create_output_directory()

    tables = get_timetables()
    handler = generate_gtfs(tables)
    if not Config.disable_location_detection:
        route = match_coordinates(handler)
        handler.add_coordinates(route)
    handler.write_files()


if __name__ == "__main__":
    main()
