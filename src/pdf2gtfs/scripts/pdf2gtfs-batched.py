""" Runs pdf2gtfs on all files in the given directory. """

import logging
import sys
import traceback
from argparse import ArgumentParser
from glob import glob
from pathlib import Path

from pdf2gtfs.config import Config
from pdf2gtfs.main import main
from pdf2gtfs.p2g_logging import initialize_logging


def get_configs(pdf_file: Path) -> list[str]:
    """ Return all existing configs for the given pdf file. """
    base_config = pdf_file.parent.joinpath("base.yaml")
    routetype_config_name = pdf_file.stem.split("-", 1)[0] + ".yaml"
    routetype_config = pdf_file.parent.joinpath(routetype_config_name)
    special_config = pdf_file.parent.joinpath(pdf_file.stem + ".yaml")
    configs = []
    if base_config.exists():
        configs += ["--config", str(base_config)]
    if routetype_config.exists():
        configs += ["--config", str(routetype_config)]
    if special_config.exists():
        configs += ["--config", str(special_config)]
    return configs


def run_all() -> None:
    """ Run pdf2gtfs on all PDFs in the given directory. """
    batch_args = batch_arg_parser().parse_args()
    p2g_arg = str(Config.p2g_dir.joinpath("main.py"))
    pdf_dir = Path(batch_args.pdf_dir).resolve(strict=True)
    out_dir = Path(batch_args.out_dir).resolve(strict=True)
    for pdf_file in glob("*.pdf", root_dir=pdf_dir):
        pdf_path = pdf_dir.joinpath(pdf_file)
        configs = get_configs(pdf_path)
        sys.argv = [p2g_arg] + configs + [str(pdf_path)]
        print(f"Running pdf2gtfs on '{pdf_file}'.", end=" ")
        legacy = "-legacy" if Config.use_legacy_extraction else ""
        log_file = out_dir.joinpath(pdf_path.stem + f"{legacy}.log")
        try:
            log_handler = logging.FileHandler(str(log_file), mode="w")
            initialize_logging(0, force=True, handlers=[log_handler])
            Config.output_path = out_dir.joinpath(f"{pdf_path.stem}.zip")
            main()
            log_handler.close()
            print("Done. No errors occurred.")
        except Exception as e:
            with open(log_file, "a") as fil:
                fil.write("\n\n")
                traceback.print_exception(e, file=fil)
            print(f"Errors occurred. See the log file '{log_file.name}'.")


def batch_arg_parser() -> ArgumentParser:
    """ Parse the arguments.

    The first argument is the directory containing the input and config files.
    The second argument is the output directory.
    """
    parser = ArgumentParser("pdf2gtfs-batch")
    text = ("The directory that contains the PDF files and the config files"
            "that should be used when running pdf2gtfs.")
    parser.add_argument("pdf_dir", type=str, help=text)
    text = "The output directory for the GTFS feeds"
    parser.add_argument("out_dir", type=str, help=text)
    return parser


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [str(Config.p2g_dir.parents[1].joinpath("examples2")),
                     str(Config.p2g_dir.parents[1].joinpath("out2"))]
    run_all()
