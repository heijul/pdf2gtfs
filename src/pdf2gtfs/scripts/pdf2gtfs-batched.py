import sys
import traceback
from argparse import ArgumentParser
from glob import glob
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout

from pdf2gtfs.config import Config
from pdf2gtfs.main import main


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


def run_all():
    """ Run pdf2gtfs on all PDFs in the given directory. """
    batch_args = batch_arg_parser().parse_args()
    p2g_arg = str(Config.p2g_dir.joinpath("main.py"))
    pdf_dir = Path(batch_args.pdf_dir).resolve(strict=True)
    out_dir = Path(batch_args.out_dir).resolve(strict=True)
    out_dir_args = ["--output_path", str(out_dir)]
    for pdf_file in glob("*.pdf", root_dir=pdf_dir):
        pdf_path = pdf_dir.joinpath(pdf_file)
        configs = get_configs(pdf_path)
        sys.argv = [p2g_arg] + configs + out_dir_args + [str(pdf_path)]
        print(f"Running pdf2gtfs on '{pdf_file}'.", end=" ")
        log_file = out_dir.joinpath(pdf_path.stem + ".log")
        err = None
        stream = StringIO()
        try:
            with redirect_stdout(stream):
                main()
        except Exception as e:
            stream.write("\n")
            traceback.print_exception(e, file=stream)
        stream.seek(0)
        with open(log_file, "w") as fil:
            fil.write(stream.read())

        if err:
            print(f"Errors occurred. See the log file '{log_file.name}'.")
        else:
            print("Done. No errors occurred.")


def batch_arg_parser():
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
