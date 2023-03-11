""" pdf2gtfs main. From here all methods are called to create a gtfs archive
from the given pdf file. """

import logging
import sys
from time import time
from typing import TYPE_CHECKING

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.handler import GTFSHandler
from pdf2gtfs.locate import find_location_nodes
from pdf2gtfs.logging import initialize_logging
from pdf2gtfs.reader import Reader
from pdf2gtfs.user_input.arg_parser import parse_args
from pdf2gtfs.user_input.cli import create_output_directory


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable

logger = logging.getLogger(__name__)


def get_timetables() -> list["TimeTable"]:
    """ Returns all timetables in the pdf within the given pages. """
    pages = Config.pages.pages
    page_str = "page" if pages == [1] else "pages"
    page_msg = f"Reading the following {page_str}: {pages}."
    if not pages:
        page_msg = "Reading all pages."
    logger.info(page_msg)

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


def detect_locations(gtfs_handler: GTFSHandler) -> None:
    """ Find the locations of the stops defined in the gtfs_handler. """
    if Config.disable_location_detection:
        logger.info("Skipping location detection, as requested.")
        return
    locations = find_location_nodes(gtfs_handler)
    gtfs_handler.add_coordinates(locations or [])


def main() -> None:
    """ Main function. """
    start = time()
    Config.load_args(parse_args())
    initialize_logging(logging.INFO)

    if not create_output_directory():
        sys.exit(3)

    tables = get_timetables()
    handler = generate_gtfs(tables)
    detect_locations(handler)
    handler.write_files()
    logger.info(f"Export complete. Took {time() - start:.2f}s. Exiting...")


if __name__ == "__main__":
    main()