""" Handles the command line arguments given to pdf2gtfs. """

from argparse import ArgumentParser, Namespace

from pdf2gtfs.datastructures.gtfs_output.routes import RouteType


def parse_args(args: list | None = None) -> Namespace:
    """ Create an argument parser and try to parse the given args. """
    # Create an argument parser with all arguments.
    parser = ArgumentParser("pdf2gtfs")
    _add_required_arguments(parser)
    _add_optional_arguments(parser)

    return parser.parse_args(args)


def _add_required_arguments(parser: ArgumentParser):
    parser.add_argument(
        "filename", type=str,
        help="The pdf file you want to extract the tables from")


def _add_optional_arguments(parser: ArgumentParser):
    text = ("A strftime format string describing the format of the "
            "timestrings of the pdf table. ")
    parser.add_argument("--time_format", type=str, help=text)

    text = "The GTFS routetype."
    types = [typ.name for typ in RouteType]
    parser.add_argument(
        "--gtfs_routetype", type=str, choices=types, help=text)

    text = ("Only extract the tables of these pages. Either 'all' "
            "(default), or a list of ints separated by commas.")
    parser.add_argument("--pages", type=str, help=text)

    text = ("Path to a configuration file. If given multiple times, all "
            "files will be read in the order given. Config files read later "
            "may override the settings of previous config files.")
    parser.add_argument("--config", action="append", type=str,
                        help=text, default=[])

    text = ("Path to output directory. Will default to './out'. "
            "If the directory is not empty, files may be overwritten.")
    parser.add_argument("--output_dir", type=str, help=text)

    text = ("Whether the preprocessed pdf should be saved. Will be saved to "
            "the output directory. This may be helpful for debugging.")
    parser.add_argument("--output_pp", const=True,
                        action="store_const", help=text)

    text = ("Disables any actions which require user input (e.g. the mapping "
            "of annotations to dates.")
    parser.add_argument("--non_interactive", const=True,
                        action="store_const", help=text)

    text = "Display the route in your webbrowser."
    parser.add_argument("--display_route", type=int, help=text)

    text = "Disable the detection of the location of the stops."
    parser.add_argument("--disable_location_detection", const=True,
                        action="store_const", help=text)

    text = ("Disable writing the output to the output directory. "
            "Used for debugging.")
    parser.add_argument("--disable_output", const=True,
                        action="store_const", help=text)
