""" Utils used across multiple files, to prevent circular imports. """

from __future__ import annotations

import re
from typing import TypeAlias, TypeVar


class _UIDGenerator:
    def __init__(self) -> None:
        self.id: int | None = None
        self.skip_ids: set[str] = set()

    def skip(self, skipped_id: str) -> None:
        """ Skip the specified ID.

        The UIDGenerator never returns skipped IDs.
        """
        self.skip_ids.add(str(skipped_id))

    def __get_next_id(self) -> int:
        i = 0 if self.id is None else self.id + 1
        while str(i) in self.skip_ids:
            i += 1
            continue
        return i

    def next(self) -> str:
        """ Return the next available id. """
        self.id = self.__get_next_id()
        return str(self.id)


UIDGenerator = _UIDGenerator()


def next_uid() -> str:
    """ Return the next available UID. """
    return UIDGenerator.next()


SPECIAL_CHARS = "\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF"


def normalize_name(name: str) -> str:
    """ Normalize the given name.

    Return a str which only consists of letters and allowed chars.
    Will also remove any parentheses and their contents.
    """
    from config import Config

    def _remove_parentheses(string: str) -> str:
        # Replace with space if there are spaces on either side.
        string = re.sub(r"( *\(.*\) *?\b)", " ", string)
        # Replace with nothing if its is followed by another symbol (like ',')
        return re.sub(r"( *\(.*\).*?\B)", "", string)

    def _remove_forbidden_symbols(string: str) -> str:
        # Special chars include for example umlaute
        # See https://en.wikipedia.org/wiki/List_of_Unicode_characters
        allowed_chars = "".join([re.escape(char)
                                 for char in Config.allowed_stop_chars])
        re_allowed_symbols = rf"[^a-zA-Z\d{SPECIAL_CHARS}{allowed_chars}]"
        return re.sub(re_allowed_symbols, "", string)

    def _remove_non_letter_starts(string: str) -> str:
        # FEATURE: Instead of doing this, create function to add city name in
        #  case name starts with a '-'. See kvv example.
        # Names should start with a letter.
        while any([string.startswith(char)
                   for char in Config.allowed_stop_chars]):
            string = string[1:]
        return string

    name = _remove_parentheses(name)
    name = _remove_forbidden_symbols(name)
    name = _remove_non_letter_starts(name)
    # Remove multiple continuous spaces
    return re.sub("( +)", " ", name)


T_ = TypeVar("T_")
PaddedList: TypeAlias = list[T_ | None]


def padded_list(objects: list[T_]) -> tuple[PaddedList, list[T_], PaddedList]:
    """ Pad the list with None on either end and return all three. """
    # TODO NOW: Use itertools.
    left_pad = [None] + objects[:-1]
    right_pad = objects[1:] + [None]
    return left_pad, objects, right_pad


def replace_abbreviations(name: str) -> str:
    """ Replace all abbreviations in name. """
    regex = get_abbreviations_regex()
    return re.sub(regex, replace_abbreviation, name)


def get_abbreviations_regex() -> str:
    """ Return a regex that matches any abbreviation. """

    def _to_regex(abbrev_key: str) -> str:
        ends_with_key_regex = ""
        if abbrev_key.endswith("."):
            abbrev_key = re.escape(abbrev_key[:-1])
            ends_with_key_regex = rf"|({abbrev_key}\.)"

        # Full word may end with a dot as well, which could then be wrongly
        #  replaced by another abbrev. E.g. if given a string "hbf." and
        #  name_abbreviations = {"hbf": "hauptbahnhof", "of.": "offenbach"},
        #  would result in "hbf." -> "hauptbahnhof." -> "hauptbahnoffenbach"
        abbrev_key = re.escape(abbrev_key)
        key_matches_word_regex = rf"(\b{abbrev_key}\.)|(\b{abbrev_key}\b)"

        return key_matches_word_regex + ends_with_key_regex

    from config import Config

    abbrevs = Config.name_abbreviations
    return "|".join(map(_to_regex, abbrevs))


def replace_abbreviation(value: re.Match) -> str:
    """ Replace the single abbreviation in the given match. """
    from config import Config

    start, end = value.span()
    key = value.string[start:end].replace(".", "").lower()
    if key not in Config.name_abbreviations:
        return Config.name_abbreviations[key + "."]
    return Config.name_abbreviations[key.lower()]
