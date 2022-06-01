import logging

from datastructures.gtfs_output.handler import GTFSHandler
from p2g_logging import initialize_logging

from reader import Reader
from config import Config
from cli.cli import parse_args
from sys import argv


logger = logging.getLogger(__name__)


def try_reader():
    reader = Reader(Config.filename)
    timetables = reader.read()
    return timetables


def try_gtfs_output(timetables):
    assert len(timetables) > 0
    gtfs_handler = GTFSHandler()
    gtfs_handler.timetable_to_gtfs(timetables[0])
    gtfs_handler.write_files()



if __name__ == "__main__":
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_g10.pdf", "./data/vag_linie_eins_new.pdf", "./data/test.pdf"]
    argv.append("--pages=1")
    argv.append(fnames[3])
    parse_args()
    initialize_logging(logging.DEBUG)

    logger.info(f"Reading the following pages: {Config.pages.pages}.")

    tables = try_reader()
    try_gtfs_output(tables)


# TODO: Anschlüsse über an/ab rausfinden + evtl. Schwellenwert
