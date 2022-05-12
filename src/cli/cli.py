from argparse import ArgumentParser, Namespace

from config import Config


def parse_args(args: list | None = None):
    parser = get_parser()
    args_ns = parser.parse_args(args)
    update_config(args_ns)


def get_parser() -> ArgumentParser:
    parser = ArgumentParser("pdf2gtfs")
    _add_required_arguments(parser)
    _add_optional_arguments(parser)
    return parser


def update_config(args_ns: Namespace):
    args = {arg: getattr(args_ns, arg)
            for arg in dir(args_ns) if not arg.startswith("_")}
    Config.load_args(args)


def _add_required_arguments(parser: ArgumentParser):
    parser.add_argument(
        "filename", type=str,
        help="The pdf file you want to extract the tables from")


def _add_optional_arguments(parser: ArgumentParser):
    # TODO: Use the _Config.properties to get the name, type and help
    #  + add help to _Config.properties
    text = ("A strftime format string describing the format of the "
            "timestrings of the pdf table. ")
    parser.add_argument("--time_format", type=str, help=text)
    text = ("Which identifiers are used for the headers. Check the default "
            "config for more information.")
    parser.add_argument("--header_identifier", type=list, help=text)
    text = ("How repeating times are identified. Check the default "
            "config for more information.")
    parser.add_argument("--repeat_identifier", type=list, help=text)
    text = ("Only extract the tables of these pages. "
            "Either 'all', or a list of ints separated by commas.")
    parser.add_argument("--pages", type=str, help=text)
    text = ("Path to a configuration file. If given multiple times, all "
            "files will be read in the order given.")
    parser.add_argument("--config", action="append", type=str, help=text)
