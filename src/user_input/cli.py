from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Callable, TypeAlias, TYPE_CHECKING


if TYPE_CHECKING:
    from datastructures.gtfs_output.agency import AgencyEntry


logger = logging.getLogger(__name__)
CheckType: TypeAlias = list[str] | Callable[[str], bool]
AnnotException: TypeAlias = dict[str: tuple[bool, list[datetime.date]]]


def _get_input(prompt: str, check: CheckType, msg: str = "") -> str:
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
    def is_valid_date(date_str: str) -> bool:
        return not date_str or _to_date(date_str) is not None

    msg = ("Enter a date (YYYYMMDD) where service is different than usual, "
           "or an empty string if there are no more exceptions "
           "for this annotation:")
    err_msg = ("Invalid date. Make sure you use the "
               "right format, i.e. YYYYMMDD (e.g. 20220420)")
    dates = _get_inputs(msg, is_valid_date, msg=err_msg)
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
def overwrite_existing_file(filename: str | Path):
    msg = (f"The file '{filename}' already exists.\n"
           f"Do you want to overwrite it? [y]es [n]o")
    # FEATURE: Extend to overwrite all/none/overwrite/skip
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


def _get_agency_header(agency: AgencyEntry) -> list[str]:
    return agency.get_field_names().split(",")


def _get_agency_column_widths(agencies: list[AgencyEntry]) -> list[int]:
    widths = [5] + [len(col) for col in list(_get_agency_header(agencies[0]))]
    # Index column length.
    widths[0] = max(widths[0], len(str(len(agencies))))

    for agency in agencies:
        for i, value in enumerate(agency.values, 1):
            widths[i] = max(widths[i], len(value))

    return [size for size in widths]


def _get_agency_prompt(path: str, agencies: list[AgencyEntry]):
    agency_strings = []
    widths = _get_agency_column_widths(agencies)

    for i, agency in enumerate(agencies):
        agency_string = _get_agency_string(str(i), agency.values, widths)
        agency_strings.append(agency_string)

    prompt = f"Multiple agencies found in '{path}':"
    lin_sep = "\n\t"

    columns = _get_agency_header(agencies[0])
    prompt += lin_sep + _get_agency_string("index", columns, widths)
    prompt += lin_sep + lin_sep.join(agency_strings)

    prompt += "\n\nPlease provide the index of the agency you want to use."
    return prompt


def select_agency(path: str, agencies: list[AgencyEntry]) -> AgencyEntry:
    prompt = _get_agency_prompt(path, agencies)
    answer = _get_input(prompt, list(map(str, range(len(agencies)))))
    return agencies[int(answer)]
