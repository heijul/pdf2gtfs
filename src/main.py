import logging

from reader import Reader
from config import Config
from cli.cli import parse_args
from sys import argv


logger = logging.getLogger(__name__)


def try_reader():
    reader = Reader(Config.filename)
    reader.read()


if __name__ == "__main__":
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_g10.pdf", "./data/vag_linie_eins_new.pdf", "./data/test.pdf"]
    argv.append("--pages=1")
    argv.append(fnames[3])
    parse_args()
    logging.basicConfig(level=20)
    logger.info(f"Reading the following pages: {Config.pages.pages}.")

    try_reader()


# TODO: Anschlüsse über an/ab rausfinden + evtl. Schwellenwert
