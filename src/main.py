from reader import Reader
from config import Config
from cli.cli import parse_args
from sys import argv


def try_reader():
    reader = Reader(Config.filename)
    reader.read()


if __name__ == "__main__":
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_g10.pdf"]
    argv.append(fnames[0])
    parse_args()

    try_reader()


# TODO: Anschlüsse über an/ab rausfinden + evtl. Schwellenwert
