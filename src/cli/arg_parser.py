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
    parser.add_argument("--out", type=str, help=text)

    text = ("Whether the preprocessed pdf should be saved. Will be saved to "
            "the output directory. This may be helpful for debugging.")
    parser.add_argument("--output_pp", const=True,
                        action="store_const", help=text)

    text = ("Disables any actions which require user input (e.g. the mapping "
            "of annotations to dates. Files that already exist will not be "
            "overwritten when this is set.")
    parser.add_argument("--non_interactive", const=True,
                        action="store_const", help=text)

    text = ("GTFS files which already exist in the output directory will be "
            "overwritten without asking for user input. This setting will "
            "take precedence over --non_interactive, in regards to "
            "overwriting existing files, if both are set.")
    parser.add_argument("--always_overwrite", const=True,
                        action="store_const", help=text)

    text = "Display the route in your webbrowser."
    parser.add_argument("--display_route", const=True,
                        action="store_const", help=text)
