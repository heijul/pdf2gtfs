""" Utils used across multiple files, to prevent circular imports. """

from __future__ import annotations

import functools
import re
from typing import TypeAlias, TypeVar

import pandas as pd


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

    def is_used(self, id_: str) -> bool:
        return id_ in self.skip_ids


UIDGenerator = _UIDGenerator()


def next_uid() -> str:
    """ Return the next available UID. """
    return UIDGenerator.next()


SPECIAL_CHARS = "\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF"

T_ = TypeVar("T_")
PaddedList: TypeAlias = list[T_ | None]


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

    from pdf2gtfs.config import Config

    abbrevs = Config.name_abbreviations
    return "|".join(map(_to_regex, abbrevs))


def replace_abbreviation(value: re.Match) -> str:
    """ Replace the single abbreviation in the given match. """
    from pdf2gtfs.config import Config

    start, end = value.span()
    key = value.string[start:end].replace(".", "").lower()
    if key not in Config.name_abbreviations:
        return Config.name_abbreviations[key + "."]
    return Config.name_abbreviations[key.lower()]


def normalize_series(raw_series: pd.Series) -> pd.Series:
    """ Normalize the series and remove symbols. """

    def _normalize(series: pd.Series) -> pd.Series:
        """ Lower and casefold the series. """
        return series.str.lower().str.casefold()

    def _replace_abbreviations(series: pd.Series) -> pd.Series:
        """ Replace the abbreviations by their full version. """
        return series.str.replace(
            get_abbreviations_regex(), replace_abbreviation, regex=True)

    def _remove_forbidden_chars(series: pd.Series) -> pd.Series:
        """ Remove parentheses and their content and special chars. """
        from pdf2gtfs.config import Config

        # Match parentheses and all text enclosed by them.
        parentheses_re = r"(\(.*\))"
        allowed_chars = "".join(Config.allowed_stop_chars)
        # Match all chars other than the allowed ones.
        char_re = fr"([^a-zA-Z\d\|{SPECIAL_CHARS}{allowed_chars}])"
        regex = "|".join([parentheses_re, char_re])
        return series.str.replace(regex, " ", regex=True)

    def _cleanup_words(series: pd.Series) -> pd.Series:
        """ Sort the words in the series, removing duplicates and whitespace.

        This will remove duplicate words, as well as replace leading/trailing
        and multiple consecutive whitespace with a single space.
        Split the series into two, one containing the single names and the
        other containing all names that are delimited using "|", because they
        need to be handled differently.
        As this also removes multiple consecutive, as well as
        leading/trailing whitespace, it should be run last.
        """

        def _sort_names(value: str) -> str:
            """ Sort a single entry in the series. """
            names = []
            for name in value.split("|"):
                words = {w.strip() for w in name.split(" ") if w.strip()}
                names.append(" ".join(sorted(words)))

            return "|".join(names)

        return series.map(_sort_names)

    return (raw_series
            .pipe(_normalize)
            .pipe(_replace_abbreviations)
            .pipe(_remove_forbidden_chars)
            .pipe(_cleanup_words)
            )


@functools.cache
def normalize_name(name: str) -> str:
    """ Normalize the given name. Simple wrapper function for a single str. """
    return normalize_series(pd.Series([name])).iloc[0]
