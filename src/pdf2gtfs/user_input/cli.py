""" Used to ask for userinput. """

from __future__ import annotations

import datetime
import logging
from operator import attrgetter
from pathlib import Path
from typing import Callable, TYPE_CHECKING, TypeAlias

from pdf2gtfs.p2g_logging import flush_all_loggers


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.gtfs_output.agency import (
        GTFSAgency, GTFSAgencyEntry)

logger = logging.getLogger(__name__)
CheckType: TypeAlias = list[str] | Callable[[str], bool]
AnnotException: TypeAlias = dict[str, tuple[bool, list[datetime.date]]]


def _get_input(prompt: str, check: CheckType, msg: str = "") -> str:
    flush_all_loggers()
    answer = input(prompt + "\n> ").lower().strip()
    valid = answer in check if isinstance(check, list) else check(answer)
    if valid:
        return answer
    if msg:
        logger.warning(msg)
    return _get_input(prompt, check, msg)


def _get_inputs(prompt: str, check: CheckType, msg: str = "") -> list[str]:
    answers = []
    while True:
        answer = _get_input(prompt, check, msg)
        if answer == "":
            break
        answers.append(answer)
    return answers


# Annotation handling.
def _to_date(date_str: str) -> datetime.date | None:
    try:
        return datetime.datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None


def _get_annotation_exceptions() -> list[datetime.date]:
    def _is_valid_date(date_str: str) -> bool:
        return not date_str or _to_date(date_str) is not None

    msg = ("Enter a date (YYYYMMDD) where service is different than usual, "
           "or an empty string if there are no more exceptions "
           "for this annotation:")
    err_msg = ("Invalid date. Make sure you use the "
               "right format, i.e. YYYYMMDD (e.g. 20220420)")
    dates = _get_inputs(msg, _is_valid_date, msg=err_msg)
    return list(map(_to_date, dates))


def _get_annotation_default() -> bool:
    prompt = "Should service be usually active for this annotation? [y/n]"
    return _get_input(prompt, ["y", "n"]) == "y"


def _handle_annotation(annot: str) -> tuple[bool, bool]:
    prompt = (f"Found this annotation '{annot}'. What do you want to do?\n"
              "(S)kip annotation, Add (E)xception for this annotation, "
              "Skip (A)ll remaining annotations: [s/e/a]")
    answer = _get_input(prompt, ["s", "e", "a"])
    return answer == "s", answer == "a"


def handle_annotations(annots: list[str]) -> AnnotException:
    """ Ask the user whether each annotation in annots is used to define dates,
     where service differs from the regular schedule. If yes, the user has to
     provide the regular schedule and dates where it differs. """
    exceptions: AnnotException = {}
    for annot in annots:
        skip_this, skip_all = _handle_annotation(annot)
        if skip_all:
            break
        if skip_this:
            continue
        exceptions[annot] = (_get_annotation_default(),
                             _get_annotation_exceptions())

    return exceptions


# Overwrite handling.
def ask_overwrite_existing_file(filename: str | Path):
    """ Ask the user, if the given file should be overwritten. """

    msg = (f"The file '{filename}' already exists.\n"
           f"Do you want to overwrite it? [y]es [n]o")
    answer = _get_input(msg, ["y", "n"])
    return answer == "y"


# Agency selection.
def _get_agency_string(
        idx: str, agency: list[str], widths: list[int]) -> str:
    format_strings = ["{" + ":>" + str(size) + "}" for size in widths]

    idx_str = format_strings[0].format(idx, widths[0]) + " | "

    agency_list = []
    for i, value in enumerate(agency, 1):
        agency_list.append(format_strings[i].format(value, widths[i]))

    return idx_str + " | ".join(agency_list)


def _get_agency_header(agency: GTFSAgency) -> list[str]:
    return agency.get_header().split(",")


def _get_agency_column_widths(agency: GTFSAgency) -> list[int]:
    widths = [5] + [len(col) for col in list(_get_agency_header(agency))]
    # Index column length.
    widths[0] = max(widths[0], len(str(len(agency))))

    for entry in agency:
        for i, value in enumerate(entry.values, 1):
            widths[i] = max(widths[i], len(value))

    return [size for size in widths]


def _get_agency_prompt(agency: GTFSAgency) -> str:
    agency_strings = []
    widths = _get_agency_column_widths(agency)
    entries = sorted(agency, key=attrgetter("agency_id"))

    for i, entry in enumerate(entries):
        agency_strings.append(_get_agency_string(str(i), entry.values, widths))

    prompt = "Multiple agencies found:"
    lin_sep = "\n\t"

    columns = _get_agency_header(agency)
    prompt += lin_sep + _get_agency_string("index", columns, widths)
    prompt += lin_sep + lin_sep.join(agency_strings)

    prompt += "\n\nPlease provide the index of the agency you want to use."
    return prompt


def select_agency(agency: GTFSAgency) -> GTFSAgencyEntry:
    """ Ask the user to select an agency from the given agencies. """
    prompt = _get_agency_prompt(agency)
    answer = _get_input(prompt, list(map(str, range(len(agency)))))
    return agency.entries[int(answer)]


# Existing outdir handling.
def create_output_directory() -> bool:
    """ Create the output directory. If an error occurs,
    ask the user to resolve it. """
    from pdf2gtfs.config import Config

    def _get_msg_from_error(e: OSError) -> str:
        msg = ("An error occurred, while trying "
               "to create the output directory:\n")
        if isinstance(e, PermissionError):
            return msg + "You are missing the permissions to create it."
        if isinstance(e, FileExistsError):
            return msg + "There already exists a file with the same name."
        return msg + str(e)

    path = Config.output_dir
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        logger.error(_get_msg_from_error(error))
        if Config.non_interactive:
            return False
        prompt = ("You may resolve the issue now and press enter, to try to "
                  "create the output directory again, or enter 'q' to quit.")
        answer = _get_input(prompt, ["", "q"])
        if answer == "q":
            return False
        return create_output_directory()
    return True
