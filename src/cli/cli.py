from argparse import ArgumentParser, Namespace


def parse_args() -> Namespace:
    parser = ArgumentParser("pdf2gtfs")
    _add_required_arguments(parser)
    _add_optional_arguments(parser)
    return parser.parse_args()


def update_config(parser: ArgumentParser):
    ...


def _add_required_arguments(parser: ArgumentParser):
    parser.add_argument(
        "filename", type=str,
        help="The pdf file you want to extract the tables from")


def _add_optional_arguments(parser: ArgumentParser):
    parser.add_argument("--time_format", type=str,
                        help="The format of the timestrings of the pdf table")
    parser.add_argument("--header_identifier", type=list,
                        help="Which identifiers are used for the headers")
    parser.add_argument("--repeat_identifier", type=list,
                        help="How repeating times are identified")
