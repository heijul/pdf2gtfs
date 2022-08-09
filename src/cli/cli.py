from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Callable, TypeAlias


logger = logging.getLogger(__name__)
CheckType: TypeAlias = list[str] | Callable[[str], bool]
AnnotException: TypeAlias = dict[str: tuple[bool, list[datetime.date]]]


def get_input(prompt: str, check: CheckType, err_msg: str = "") -> str:
    answer = input(prompt + "\n> ").lower().strip()
    valid = answer in check if isinstance(check, list) else check(answer)
    if valid:
        return answer
    if err_msg:
        logger.warning(err_msg)
    return get_input(prompt, check, err_msg)


def get_inputs(prompt: str, check: CheckType, err_msg: str = "") -> list[str]:
    answers = []
    while True:
        answer = get_input(prompt, check, err_msg)
        if answer == "":
            break
        answers.append(answer)
    return answers


def to_date(date_str: str) -> datetime.date | None:
    try:
        return datetime.datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None


def get_annotation_exceptions() -> list[datetime.date]:
    def is_valid_date(date_str: str) -> bool:
        return not date_str or to_date(date_str) is not None

    msg = ("Enter a date (YYYYMMDD) where service is different than usual, "
           "or an empty string if there are no more exceptions "
           "for this annotation:")
    err_msg = ("Invalid date. Make sure you use the "
               "right format, i.e. YYYYMMDD (e.g. 20220420)")
    dates = get_inputs(msg, is_valid_date, err_msg=err_msg)
    return list(map(to_date, dates))


def get_annotation_default() -> bool:
    prompt = "Should service be usually active for this annotation? [y/n]"
    return get_input(prompt, ["y", "n"]) == "y"


def handle_annotation(annot: str) -> tuple[bool, bool]:
    prompt = (f"Found this annotation '{annot}'. What do you want to do?\n"
              "(S)kip annotation, Add (E)xception for this annotation, "
              "Skip (A)ll remaining annotations: [s/e/a]")
    answer = get_input(prompt, ["s", "e", "a"])
    return answer == "s", answer == "a"


def handle_annotations(annots: list[str]) -> AnnotException:
    exceptions: AnnotException = {}
    for annot in annots:
        skip_this, skip_all = handle_annotation(annot)
        if skip_all:
            break
        if skip_this:
            continue
        exceptions[annot] = (get_annotation_default(),
                             get_annotation_exceptions())

    return exceptions


def overwrite_existing_file(filename: str | Path):
    msg = (f"The file '{filename}' already exists.\n"
           f"Do you want to overwrite it? [y]es [n]o")
    # FEATURE: Extend to overwrite all/none/overwrite/skip
    answer = get_input(msg, ["y", "n"])
    return answer == "y"
