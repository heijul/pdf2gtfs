from reader.reader import Reader


def try_reader():
    # noinspection PyPackageRequirements
    fnames = ["./data/vag_linie_eins.pdf", "./data/rmv_u1.pdf",
              "./data/rmv_g10.pdf"]
    reader = Reader(fnames[0])
    reader.read()


if __name__ == "__main__":
    try_reader()
