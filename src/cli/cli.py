from argparse import ArgumentParser


def get_parser() -> ArgumentParser:
    parser = ArgumentParser("pdf2gtfs")
    _add_required_arguments(parser)
    _add_optional_arguments(parser)
    return parser


def _add_required_arguments(parser: ArgumentParser):
    parser.add_argument(
        "filename", type=str,
        help="The pdf file you want to extract the tables from")


def _add_optional_arguments(parser: ArgumentParser):
    parser.add_argument("--time_format", type=str,
                        help="The format of the timestrings of the pdf table")
    parser.add_argument("--header_identifier", type=str,
                        help="Which identifier to use for the headers")
    parser.add_argument("--repeat_identifier", type=str,
                        help="How repeating times are identified")
