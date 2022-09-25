from __future__ import annotations

import re
from typing import TypeAlias, TypeVar


class _UIDGenerator:
    def __init__(self) -> None:
        self.id: int | None = None
        self.skip_ids: set[str] = set()

    def skip(self, skipped_id: str) -> None:
        self.skip_ids.add(str(skipped_id))

    def __get_next_id(self) -> int:
        i = 0 if self.id is None else self.id + 1
        while str(i) in self.skip_ids:
            i += 1
            continue
        return i

    def next(self) -> str:
        self.id = self.__get_next_id()
        return str(self.id)


UIDGenerator = _UIDGenerator()


def next_uid() -> str:
    return UIDGenerator.next()


REGEX_FLAGS = re.I + re.U
SPECIAL_CHARS = "\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF"

def normalize_name(name: str) -> str:
    """ Return a str which only consists of letters and allowed chars. """
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
    left_pad = [None] + objects[:-1]
    right_pad = objects[1:] + [None]
    return left_pad, objects, right_pad


def get_edit_distance(s1, s2) -> int:
    """ Uses the Wagner-Fischer Algorithm. """
    s1 = " " + s1.casefold().lower()
    s2 = " " + s2.casefold().lower()
    m = len(s1)
    n = len(s2)
    d = [[0] * n for _ in range(m)]

    for i in range(1, m):
        d[i][0] = i
    for j in range(1, n):
        d[0][j] = j

    for j in range(1, n):
        for i in range(1, m):
            cost = int(s1[i] != s2[j])
            d[i][j] = min(d[i - 1][j] + 1,
                          d[i][j - 1] + 1,
                          d[i - 1][j - 1] + cost)

    return d[m - 1][n - 1]


def replace_abbreviations(name: str) -> str:
    return re.sub(get_abbreviations_regex(), replace_abbreviation, name,
                  flags=REGEX_FLAGS)


def get_abbreviations_regex() -> str:
    from config import Config

    abbrevs = Config.name_abbreviations
    base_regex = r"({0}\.)|(\b{0}\b)"
    return "|".join(
        [base_regex.format(re.escape(abbrev)) for abbrev in abbrevs])


def replace_abbreviation(value: re.Match) -> str:
    from config import Config

    start, end = value.span()
    key = value.string[start:end].replace(".", "")
    return Config.name_abbreviations[key.lower()]
