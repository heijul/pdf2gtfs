""" Contains the CellTypes, as well as the functions used to infer them. """

from __future__ import annotations

import re
from enum import Enum
from operator import attrgetter
from statistics import mean
from time import strptime
from typing import Any, Callable, TYPE_CHECKING, TypeAlias, TypeVar

from math import floor, log2
from more_itertools import collapse, substrings_indexes

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.table.direction import (
    D, Direction, E, H, N, Orientation, S, V, W,
    )


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.cell import Cell

C: TypeAlias = "Cell"
Cs: TypeAlias = list[C]

A = TypeVar("A")


def get_argmax_key(dictionary: dict[A, Any]) -> A:
    """ Given the dictionary, return the key for the maximal value.

    :param dictionary: The dictionary used to get the key.
    :return: The key for the item that has the highest value.
    """
    return max(dictionary.items(), key=lambda item: item[1])[0]


class CellType:
    """ Can be used to guess and infer the Type of a Cell. """
    def __init__(self, cell: C) -> None:
        self.cell = cell
        # Probabilities for the different Types.
        self.possible_types: dict[T: float] = {}
        self.inferred_type: T | None = None
        self.inferred_types: dict[T: float] = {}

    def guess_type(self) -> T:
        """ Guess the Type of the Cell solely on its text contents.

        Also stores all possible Types and their probability,
        as these are necessary for the Type inference.

        :return: The Type that is most likely based on the Cell's contents.
        """

        if self.possible_types:
            return get_argmax_key(self.possible_types)

        possible_types = {}
        for t, indicator_func in ABS_INDICATORS.items():
            value = int(indicator_func(self.cell))
            if not value:
                continue
            possible_types[t] = int(value)
        # It may always happen that a Cell is not of any proper Type,
        #  even if it looks like it.
        possible_types[T.Other] = .5

        # If the Cell contains no identifiers, it could still be one of these.
        if len(possible_types) == 1:
            possible_types = {t: 1 for t in ABS_FALLBACK}
            # However, the chance that it is not, is higher.
            possible_types[T.Other] = 2

        # Calculate the probability for each possible Type.
        div = sum(possible_types.values())
        self.possible_types = {key: round(value / div, 3)
                               for key, value in possible_types.items()}
        # Return the Type with the highest probability.
        return get_argmax_key(self.possible_types)

    def infer_type_from_neighbors(self) -> T:
        """ Infer the Type of the Cell based on other Cells.

        Other Cells, in general, are the direct neighbors or the row/col.

        :return: The Type that has the highest probability of being the
            "true" Type, when considering both the content and other Cells.
        """
        # We need the possible Types for the Type inference.
        if not self.possible_types:
            self.guess_type()

        inferred_types = {}
        for t, possibility in self.possible_types.items():
            indicator_func = REL_INDICATORS.get(t, lambda *_: possibility)
            score_multiplier = indicator_func(self.cell)
            if not score_multiplier:
                continue
            inferred_types[t] = score_multiplier * possibility

        # Return the Type with the highest score.
        self.inferred_types = inferred_types
        self.inferred_type = get_argmax_key(self.inferred_types)
        return self.inferred_type


class EmptyCellType(CellType):
    """ Used for EmptyCells. Has a fixed Type of T.Empty. """
    def __init__(self, cell: C) -> None:
        super().__init__(cell)
        self.possible_types = {T.Empty: 1}
        self.inferred_types = {T.Empty: 1}
        self.inferred_type = T.Empty

    def guess_type(self) -> T:
        """ The Type of empty Cells is always the same.

        :return: T.Empty
        """
        return T.Empty

    def infer_type_from_neighbors(self) -> T:
        """ The Type of empty Cells is always the same.

        :return: T.Empty
        """
        return T.Empty


class T(Enum):
    """ The different possible Types a Cell could have. """
    # The value is used only for illustrative purposes, though that may change.
    Time = 0.1
    TimeAnnot = 0.2
    Stop = 1.1
    StopAnnot = 1.2
    Days = 2.
    RepeatIdent = 3.1
    RepeatValue = 3.2
    RouteAnnotIdent = 4.1
    RouteAnnotValue = 4.2
    EntryAnnotIdent = 5.1
    EntryAnnotValue = 5.2
    LegendIdent = 6.1
    LegendValue = 6.2
    Other = 7.
    Empty = 8.

    def __gt__(self, other) -> bool:
        if not isinstance(other, T):
            raise TypeError(
                "Can only compare Types with Types, not '{type(other)}'.")
        return self.value > other.value

    def __lt__(self, other) -> bool:
        if not isinstance(other, T):
            raise TypeError(
                "Can only compare Types with Types, not '{type(other)}'.")
        return self.value < other.value

    def __eq__(self, other) -> bool:
        if not isinstance(other, T):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return id(self)


AbsIndicatorFunc: TypeAlias = Callable[[C], bool]


def is_time(cell: C) -> bool:
    """  Check if the Cell contains text that can be converted to a time.

    :param cell: The Cell in question.
    :return: True if the Cell's text can be parsed using strptime,
        using Config.time_format as format.
    """
    try:
        strptime(cell.text, Config.time_format)
    except ValueError:
        return False
    return True


def is_wrapper(*args) -> AbsIndicatorFunc:
    """ Simple wrapper around is_any.

    :param args: Contains lists of strings or strings, used in is_any.
    :return: Function that takes only a Cell and checks if the
        Cell's text is equal to any of the (collapsed) args.
    """
    def is_any(cell: C) -> bool:
        """ Checks if the Cell's text is equal to any of the values.

        Also lowers both Cell text and each value.

        :param cell:  The Cell the text content is checked.
        :return: True if the Cell's text contains any of the values.
            False, otherwise.
        """
        return cell.text.lower() in [v.lower() for v in values]

    values: list[str] = list(collapse(args))
    return is_any


HYPHEN_LIKE_CHARS = (
    r"["
    r"\u002D"  # HYPHEN-MINUS
    r"\u00AD"  # SOFT HYPHEN
    r"\u05BE"  # HEBREW PUNCTUATION MAQAF
    r"\u1806"  # MONGOLIAN TODO SOFT HYPHEN
    r"\u2010"  # HYPHEN
    r"\u2011"  # NON-BREAKING HYPHEN
    r"\u2012"  # FIGURE DASH
    r"\u2013"  # EN DASH
    r"\u2014"  # EM DASH
    r"\u2015"  # HORIZONTAL BAR
    r"\u207B"  # SUPERSCRIPT MINUS
    r"\u208B"  # SUBSCRIPT MINUS
    r"\u2212"  # MINUS SIGN
    r"\u2E3A"  # TWO-EM DASH
    r"\u2E3B"  # THREE-EM DASH
    r"\uFE58"  # SMALL EM DASH
    r"\uFE63"  # SMALL HYPHEN-MINUS
    r"\uFF0D"  # FULL-WIDTH HYPHEN-MINUS
    r"]")


def is_repeat_value(cell: C) -> bool:
    """ Check if the Cell contains text that could be a repeat value.

    :param cell: The Cell in question.
    :return: True if the text is either a number, two numbers
        separated by a hyphen, or two numbers separated by a comma.
        False, otherwise.
    """
    # For the hyphen case, we need to check multiple different characters
    #  that look like hyphens. See https://jkorpela.fi/dashes.html

    # TODO: Allow custom regex.
    patterns = (r"^\d+$",
                r"^\d+\s?" + HYPHEN_LIKE_CHARS + r"\s?\d+$",
                r"\d+\s?,\s?\d+$")
    for pattern in patterns:
        if bool(re.match(pattern, cell.text)):
            return True
    return False


def is_legend(cell: C) -> bool:
    """ Check if the Cell's text could be (part of) a legend.

    :param cell: The Cell in question.
    :return: True if the Cell contains a non-empty string,
        followed by a colon or equals, followed by another non-empty string.
    """
    return bool(re.match(r"^\S+\s?[:=]\s?\S+$", cell.text))


def true(*_) -> bool:
    """ Always true.

    :return: True regardless of arguments.
    """
    return True


def false(*_) -> bool:
    """ Always False.

    :return: False regardless of arguments.
    """
    return False


# The absolute Type-indicator functions.
ABS_INDICATORS: dict[T: AbsIndicatorFunc] = {
    T.Time: is_time,
    T.Days: is_wrapper(Config.header_values),
    T.RepeatIdent: is_wrapper(Config.repeat_identifier),
    T.StopAnnot: is_wrapper(Config.arrival_identifier,
                            Config.departure_identifier),
    T.RouteAnnotIdent: is_wrapper(Config.route_identifier),
    T.EntryAnnotIdent: is_wrapper(Config.annot_identifier),
    T.LegendIdent: is_legend,
    }
# The fallback Types in case no absolute indicator function returned True.
ABS_FALLBACK: list[T] = [
    T.Stop, T.RouteAnnotValue, T.EntryAnnotValue, T.TimeAnnot, T.LegendValue,
    T.RepeatValue, T.Days]


RelIndicatorFunc: TypeAlias = Callable[[C], float]


def cell_has_type_wrapper(typ: T, strict: bool = True) -> Callable[[C], bool]:
    """ Simple wrapper around has_type.

    :param typ: The Type passed to cell_has_type.
    :param strict: The strict argument passed to cell_has_type.
    :return: A function that takes a Cell
        and returns whether the Cell has the given Type.
    """
    def _cell_has_type(cell: C) -> bool:
        return cell.has_type(typ, strict=strict)

    return _cell_has_type


def cell_row_contains_type(cell: C, typ: T) -> bool:
    """ Check if the Cell's row contains a Cell with the given Type.

    :param cell: The Cell used to get the row.
    :param typ: The Type the row's Cells are checked against.
    :return: True if there is at least one Cell with the given Type.
        False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    return any(map(func, cell.row))


def cell_col_contains_type(cell: C, typ: T) -> bool:
    """ Check if the Cell's col contains a Cell with the given Type.

    :param cell: The Cell used to get the col.
    :param typ: The Type the col's Cells are checked against.
    :return: True if there is at least one Cell with the given Type.
        False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    return any(map(func, cell.col))


def cell_neighbor_has_type(cell: C, typ: T, direct_neighbor: bool = False,
                           directions: list[Direction] = D) -> bool:
    """ Check if the Cell has a neighbor with the given Type.

    :param cell: The Cell in question.
    :param typ: The Type we check the neighbors against.
    :param direct_neighbor: Whether to only check direct neighbors;
        that is, neighbors that may be empty.
        If False, get the first neighbor in each Direction that is not empty.
    :param directions: If given,
        only the neighbors in these Directions will be checked.
    :return: True if any of the Cell's neighbors is of the given Type.
        False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    return any(map(func, cell.get_neighbors(allow_empty=direct_neighbor,
                                            directions=directions)))


def cell_neighbor_has_type_wrapper(typ: T, direct_neighbor: bool = False
                                   ) -> Callable[[C], float]:
    """ Simple wrapper around cell_neighbor_has_type.

    :param typ: The Type passed to cell_neighbor_has_type.
    :param direct_neighbor: Passed to cell_neighbor_has_type.
    :return: A function that, when called with a Cell,
        returns whether the Cell has any (direct) neighbor of the given Type.
    """
    def _cell_neighbor_has_type(cell: C) -> float:
        return float(cell_neighbor_has_type(cell, typ, direct_neighbor))

    return _cell_neighbor_has_type


def cell_is_between_type(cell: C, typ: T, direct: bool = False) -> bool:
    """ Check if the Cell is 'sandwiched' between Cells of the given Type.

    :param cell: The Cell in question
    :param typ: The Type the two opposite, direct neighbors should both have.
    :param direct: If True, only the direct neighbors will be checked,
        even if they are EmptyCells.
        If False, we look for the first neighbor on both sides
        that are not EmptyCells.
    :return: True, if any two opposite direct neighbors
        are of the given Type. False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    o: Orientation
    for o in (V, H):
        lower, upper = cell.get_neighbors(allow_none=True,
                                          allow_empty=not direct,
                                          directions=[o.lower, o.upper])
        if lower and func(lower) and upper and func(upper):
            return True
    return False


def cell_is_between_type_wrapper(typ: T, **kwargs) -> Callable[[C], bool]:
    """ Simple wrapper around cell_is_between_type.

    :param typ: The Type passed to cell_is_between_type.
    :return: A function that, when passed a Cell, returns whether the
        Cell is 'sandwiched' between two Cells of the given Type.
    """
    def _cell_is_between_type(cell: C) -> bool:
        return cell_is_between_type(cell, typ, **kwargs)

    return _cell_is_between_type


def rel_multiple_function_wrapper(funcs: tuple[RelIndicatorFunc, ...]
                                  ) -> RelIndicatorFunc:
    """ A simple wrapper, running all the given indicator functions.

    :param funcs: The functions that should be run.
    :return: A function that, when passed a Cell, returns the average return
        value of the given functions, when run with that Cell as argument.
    """
    def _run(cell: C) -> float:
        return sum(func(cell) for func in funcs) / len(funcs)

    return _run


def series_contains_type(cell: C, o: Orientation, typ: T) -> bool:
    """ Check if any Cell in the Cell's row/col has the given Type.

    :param cell: This Cell's row/col is checked.
    :param o: Based on this, the row (H) or column (V) is checked.
    :param typ: The Type each Cell is checked against.
    :return: True if there exists a Cell with the given Type in the
        Cell's row/col. False, otherwise.
    """
    if o == V:
        return cell_col_contains_type(cell, typ)
    return cell_row_contains_type(cell, typ)


def time_aligned_cells_are_non_empty(starter: C, o: Orientation,
                                     cell_type: T, neighbor_type: T | None
                                     ) -> bool:
    """ Checks if the row/col of starter contains empty Cells
    in the cols/rows where the TimeCells are.

    :param starter: The row/col of this Cell will be checked.
    :param o: Whether to check row or column of starter. The normal
        Orientation to o will be used to check neighbors of each empty Cell.
    :param cell_type: The Type the aligned Cells should have.
    :param neighbor_type: The Type (other than T.Time) the neighbors of any
        encountered EmptyFields should have. If this is None, at least one
        neighbor must be of Type `Time`. In either case, neighbors must exist.
    :return: True if all Cells of the starter's col/row, which are within
        a row/col containing Cells of Type Time, are either non-empty Cells
        with Stop as possible Type, or are EmptyCells. The latter must either
        be missing a neighbor in the normal Orientation or such a neighbor
        has a different Type than Stop or Time. False, otherwise.
    """
    from pdf2gtfs.datastructures.table.cell import EmptyCell

    n = o.normal
    neighbor_types = [T.Time]
    if neighbor_type is not None:
        neighbor_types.append(neighbor_type)
    for cell in starter.iter(o=o):
        if not series_contains_type(cell, n, T.Time):
            continue
        if not isinstance(cell, EmptyCell):
            if not cell.has_type(cell_type):
                return False
            continue
        # The current Cell may be part of an incomplete row/col, which will
        # be merged to a proper StopCell.
        neighbors = cell.get_neighbors(allow_none=True,
                                       allow_empty=False,
                                       directions=[n.lower, n.upper])
        # Check the Type of the neighbors.
        correct_types = 0
        for neighbor in neighbors:
            if neighbor and neighbor.has_type(*neighbor_types):
                correct_types += 1
        if correct_types < len(neighbor_types):
            return False
    return True


def series_is_aligned(starter: C, o: Orientation,
                      max_displacement: float = 0.5) -> bool:
    """ Checks if the Cells in starter's row/col are aligned.

    :param starter: This Cell's row/col will be checked.
    :param o: Whether to check row (H) or col (V) of starter.
    :param max_displacement: The maximum displacement between
        a Cell's lower x-/y-coordinate (based on o) and
        the smallest x-/y-coordinate of all checked Cells.
    :return: True if the lower x-/y-coordinate of all checked Cells
        differs at most by max_displacement. False, otherwise.
    """
    bbox_attr = "x0" if o == V else "y0"
    lower_coords: list[float] = []
    for cell in starter.iter(o=o):
        # Only check TimeCells.
        if not series_contains_type(cell, o.normal, T.Time):
            continue
        lower_coords.append(getattr(cell.bbox, bbox_attr))
    lower_coords.sort()
    # Only the largest difference needs to be checked.
    return max_displacement >= (lower_coords[-1] - lower_coords[0])


def rel_indicator_stop(cell: C) -> float:
    """ The relative indicator for Stop.

    :param cell: The Cell that has its Type evaluated.
    :return: A value between 0 and 2.5, representing change in probability,
        based on the funcs called.
    """
    # Stops are never between the Table's TimeCells.
    if cell_is_between_type(cell, T.Time):
        return 0
    col_contains_time = cell_col_contains_type(cell, T.Time)
    row_contains_time = cell_row_contains_type(cell, T.Time)
    # We need exactly one of col/row to contain a TimeCell.
    # Otherwise, the Cell is either diagonal or
    #  inside the grid spanned by the Table's TimeCells.
    if (col_contains_time + row_contains_time) % 2 == 0:
        return 0
    o = H if col_contains_time else V
    # Stops are usually long (here, >= 8 chars on average).
    mean_length = get_time_aligned_avg_text_length(cell, o)
    # Normalize the length.
    norm_length = floor(log2(mean_length))
    if norm_length < Config.stop_min_mean_normed_length:
        return 0
    # Stops have a high letter to non-letter ratio.
    letter_ratio = get_time_aligned_letter_ratio(cell, o)
    if letter_ratio < Config.stop_letter_ratio:
        return 0

    score = 1
    if col_contains_time:
        # Every row that contains a Time must contain a Stop.
        if not time_aligned_cells_are_non_empty(cell, H, T.Stop, T.Stop):
            return 0
        # Stop columns are (generally) left aligned.
        score += series_is_aligned(cell, H)
        # If the column contains Time, the row should contain Stops.
        score += cell_row_contains_type(cell, T.Stop)
        score += cell_neighbor_has_type(
            cell, T.StopAnnot, directions=[N, S])
    elif row_contains_time:
        # Every col that contains Time must contain a Stop.
        if not time_aligned_cells_are_non_empty(cell, V, T.Stop, T.Stop):
            return 0
        score += series_is_aligned(cell, V)
        score += cell_col_contains_type(cell, T.Stop)
        score += cell_neighbor_has_type(
            cell, T.StopAnnot, directions=[W, E])

    return score


def rel_indicator_stop_annot(cell: C) -> float:
    """ The relative indicator for StopAnnot.

    :param cell: The Cell that has its Type evaluated.
    :return: A value between 0 and 1, representing change in probability,
        based on the results of the functions called.
    """
    col_contains_time = cell_col_contains_type(cell, T.Time)
    row_contains_time = cell_row_contains_type(cell, T.Time)
    # Either the row or col has to contain Time, but never both.
    if (col_contains_time + row_contains_time) % 2 == 0:
        return 0
    score = 1
    if col_contains_time:
        if not time_aligned_cells_are_non_empty(cell, H, T.StopAnnot, None):
            return 0
        score += cell_neighbor_has_type(cell, T.Stop, directions=[N, S])
        score += cell_neighbor_has_type(cell, T.StopAnnot, directions=[W, E])
    elif row_contains_time:
        if not time_aligned_cells_are_non_empty(cell, V, T.StopAnnot, None):
            return 0
        score += cell_neighbor_has_type(cell, T.Stop, directions=[W, E])
        score += cell_neighbor_has_type(cell, T.StopAnnot, directions=[N, S])

    return score


def rel_indicator_time_annot(cell: C) -> float:
    """ The relative indicator for T.TimeAnnot.

    :param cell: The Cell that has its Type evaluated.
    :return: 0, if the Cell either has no direct neighbor of Type Time,
        or if the Cell's fontsize is greater than the TimeCell's fontsize.
        1, otherwise.
    """
    neighbor_of_time = cell_neighbor_has_type(cell, T.Time, True)
    if not neighbor_of_time:
        return 0

    neighbors = cell.get_neighbors(allow_none=False, allow_empty=False)
    time_neighbors = [n for n in neighbors if n.has_type(T.Time, strict=True)]
    mean_time_fontsize = mean(map(attrgetter("fontsize"), time_neighbors))
    return cell.fontsize <= mean_time_fontsize


def rel_indicator_repeat_ident(cell: C) -> float:
    """ The relative indicator for RepeatIdent.

    :param cell: The Cell that has its Type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    required = cell_is_between_type_wrapper(T.Time)

    if not required(cell):
        return 0.
    return 1. + cell_neighbor_has_type(cell, T.RepeatValue, True)


def rel_indicator_repeat_value(cell: C) -> float:
    """ The relative indicator for RepeatValue.

    :param cell: The Cell that has its Type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    if not is_repeat_value(cell):
        return 0
    funcs = (cell_is_between_type_wrapper(T.Time),
             cell_is_between_type_wrapper(T.RepeatIdent))
    # Both are strictly required.
    return (rel_multiple_function_wrapper(funcs)(cell) == 1.0) * 2


def rel_indicator_entry_annot_value(cell: C) -> float:
    """ The relative indicator for EntryAnnotValue.

    :param cell: The Cell that has its Type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    mod = 0
    # It is less likely for a Cell to be an annotation if the col, which
    #  contains the annotation identifier, also contains Stops.
    if cell_col_contains_type(cell, T.EntryAnnotIdent):
        mod += (cell_row_contains_type(cell, T.Time)
                - cell_col_contains_type(cell, T.Stop))
    elif cell_row_contains_type(cell, T.EntryAnnotIdent):
        mod += (cell_col_contains_type(cell, T.Time)
                - cell_row_contains_type(cell, T.Stop))

    return mod * 2


def get_time_aligned_letter_ratio(starter: C, o: Orientation) -> float:
    """ Calculate the ratio between letters and symbols in the Cell's row/col.

    Only considers those Cells that are in a TimeCell's row or col.
    Symbols refers here to all characters that are not letters.

    :param starter: This Cell's row/col will be used to calculate the ratio.
    :param o: Whether to check the row or col of the Cell.
    :return: The ratio between letters and non-letters in all of the starter's
        row/col. 0 if no letters, 1 if no non-letters.
    """
    from pdf2gtfs.datastructures.table.cell import EmptyCell

    # Get all cells of the Cell's row/col.
    cells = starter.iter(o=o)
    letter_count = 0
    text_len = 0
    for cell in cells:
        if o == V and not cell_row_contains_type(cell, T.Time):
            continue
        if o == H and not cell_col_contains_type(cell, T.Time):
            continue
        if isinstance(cell, EmptyCell):
            continue
        letter_count += sum(c.isalpha() or c == " " for c in cell.text)
        text_len += len(cell.text)
    # Overall text length can not be 0 because starter is not an EmptyCell.
    return letter_count / text_len


def get_time_aligned_avg_text_length(starter: C, o: Orientation) -> float:
    """ Calculate the average text length of starter's row/col.

    Only considers those Cells that are in a TimeCell's row or col.

    :param starter: This Cell's row/col will be used to get the text length.
    :param o: Whether to check the row or col of the Cell.
    """
    from pdf2gtfs.datastructures.table.cell import EmptyCell

    cells = starter.iter(o=o)
    text_lens = []
    for cell in cells:
        if o == V and not cell_row_contains_type(cell, T.Time):
            continue
        if o == H and not cell_col_contains_type(cell, T.Time):
            continue
        if isinstance(cell, EmptyCell):
            continue
        text_lens.append(len(cell.text))
    return mean(text_lens)


def rel_indicator_route_annot_value(cell: C) -> float:
    """ The relative indicator for EntryAnnotValue.

    :param cell: The Cell that has its Type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    time_col = cell_col_contains_type(cell, T.Time)
    time_row = cell_row_contains_type(cell, T.Time)
    # Route annotations exist outside, but aligned to the TimeCells.
    if (time_col + time_row) % 2 == 0:
        return 0
    if time_col and not cell_row_contains_type(cell, T.RouteAnnotIdent):
        return 0
    if time_row and not cell_col_contains_type(cell, T.RouteAnnotIdent):
        return 0
    o = H if time_col else V
    # letter_ratio = get_time_aligned_letter_ratio(cell, o)
    mean_length = get_time_aligned_avg_text_length(cell, o)
    # Normalize the length.
    norm_length = floor(log2(mean_length))
    return norm_length < 3


def rel_indicator_days(cell: Cell) -> float:
    """ Relative indicator for Days.

    :returns: 10 if the given Cell contains a complete Days string,
    or if we can use the Cells' neighbors to construct a Days string.
    0 otherwise.
    """
    def part_of_days_indexes(days_: str, text_: str
                             ) -> tuple[str, int, int] | None:
        """ Get the days and indices, this cell may be a part of. """
        # Split at any whitespace character.
        days_list = days.split()
        days_substrings = substrings_indexes(days_list)
        # Reverse, because we only want the longest substring match.
        for substring, s_start, s_end in reversed(list(days_substrings)):
            if text_ != " ".join(substring):
                continue
            # Need to convert between substring list index and string index.
            return (days_,
                    sum([len(s) + 1 for i, s in enumerate(days_list)
                         if i < s_start]),
                    sum([len(s) + 1 for i, s in enumerate(days_list)
                         if i < s_end]) - 1)
        return None

    def next_neighbor(c: Cell, d: Direction) -> Cell | None:
        """ Get the next non-empty neighbor of c in Direction d or None. """
        neighbors = c.get_neighbors(directions=[d], allow_empty=False)
        if not neighbors:
            return None
        return neighbors[0]

    def check_left_neighbors(neighbor: Cell, start_: int) -> bool:
        """ Check if the neighbors left of the cell complete a days text. """
        while start_ > 0:
            neighbor = next_neighbor(neighbor, W)
            if not neighbor or not neighbor.has_type(T.Days):
                return False
            neighbor_indexes = part_of_days_indexes(
                days[:start_], neighbor.text.lower())
            # No index or the new end is not 'adjacent' to the current start.
            if not neighbor_indexes or neighbor_indexes[2] != start_ - 1:
                return False
            start_ = neighbor_indexes[1]
        return True

    def check_right_neighbors(neighbor: Cell, /, end_: int) -> bool:
        """ Check if the neighbors right of the cell complete a days text. """
        while end_ < len(days) - 1:
            neighbor = next_neighbor(neighbor, E)
            if not neighbor or not neighbor.has_type(T.Days):
                return False
            neighbor_indexes = part_of_days_indexes(
                days[end_:], neighbor.text.lower())
            # No index or the new start is not 'adjacent' to the current end.
            if not neighbor_indexes or neighbor_indexes[1] != end_ + 1:
                return False
            end_ = neighbor_indexes[2]
        return True

    text = cell.text.lower()
    if text in Config.negative_header_values:
        return 0
    # If this Cells' text is a header value,
    # we can be almost certain that it is a day.
    if text in Config.header_values:
        return 10
    # Otherwise, the days info might be split into multiple Cells.
    # Try to merge this cell with neighbors, if all cells together form a day
    possible_days: list[tuple[str, int, int]] = []
    for days in Config.header_values:
        indexes = part_of_days_indexes(days, text)
        if not indexes:
            continue
        possible_days.append(indexes)

    # This Cells' text is not a word of any days value.
    if not possible_days:
        return 0
    for days, start, end in possible_days:
        valid = check_left_neighbors(cell, start)
        if not valid:
            continue
        valid = check_right_neighbors(cell, end)
        if not valid:
            continue
        # Days match was found using the neighbors.
        return 10
    return 0


# The relative Type-indicator functions.
REL_INDICATORS: dict[T: RelIndicatorFunc] = {
    T.Time: cell_neighbor_has_type_wrapper(T.Time),
    T.Days: rel_indicator_days,
    T.Stop: rel_indicator_stop,
    T.StopAnnot: rel_indicator_stop_annot,
    T.TimeAnnot: rel_indicator_time_annot,
    T.EntryAnnotValue: rel_indicator_entry_annot_value,
    T.RouteAnnotValue: rel_indicator_route_annot_value,
    T.RepeatIdent: rel_indicator_repeat_ident,
    T.RepeatValue: rel_indicator_repeat_value,
    T.Other: lambda *_: 0.1,
    }
