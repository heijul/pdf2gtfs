import logging

from datastructures.gtfs_output.handler import GTFSHandler
from finder import Finder, display_route
from p2g_logging import initialize_logging

from reader import Reader
from config import Config
from cli.arg_parser import parse_args
from sys import argv


logger = logging.getLogger(__name__)


def try_reader():
    reader = Reader(Config.filename)
    timetables = reader.read()
    return timetables


def try_gtfs_output(timetables):
    assert len(timetables) > 0
    gtfs_handler = GTFSHandler()
    for table in timetables:
        gtfs_handler.timetable_to_gtfs(table)
    return gtfs_handler


def try_matching_coordinates(gtfs_handler: GTFSHandler):
    finder = Finder(gtfs_handler)
    finder.generate_routes()
    r = finder.routes.clusters[0].get_route()
    display_route(r)
    for route in finder.get_routes():
        print(route)


if __name__ == "__main__":
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_g10.pdf", "./data/vag_linie_eins_new.pdf",
              "./data/vag_linie_eins_new_a.pdf"]
    argv.append("--pages=2")
    argv.append(fnames[3])
    parse_args()
    initialize_logging(logging.DEBUG)

    logger.info(f"Reading the following pages: {Config.pages.pages}.")

    tables = try_reader()
    handler = try_gtfs_output(tables)
    try_matching_coordinates(handler)
    handler.write_files()

# TODO: Rendermode in pdfminer
# TODO: Ghostscript preprocessing
# TODO: Tests + testdaten in svn
