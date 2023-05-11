""" Contains the cell types, as well as the functions used to infer them. """

from __future__ import annotations

import re
from enum import Enum
from operator import attrgetter
from statistics import mean
from time import strptime
from typing import Any, Callable, TYPE_CHECKING, TypeAlias, TypeVar

from more_itertools import collapse

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.table.direction import (
    D, Direction, E, H, N, Orientation, S, V, W,
    )


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.cell import Cell


C: TypeAlias = "Cell"
Cs: TypeAlias = list[C]

A = TypeVar("A")


def get_max_key(dict_: dict[A, Any]) -> A:
    """ Given the dictionary, return the key for the maximal value.

    :param dict_: The dictionary.
    :return: The key for the maximal value.
    """
    return max(dict_.items(), key=lambda item: item[1])[0]


class CellType:
    """ Can be used to guess/infer the type of a cell. """
    def __init__(self, cell: C) -> None:
        self.cell = cell
        # Probabilities for the different types.
        self.possible_types: dict[T: float] = {}
        self.inferred_type: T | None = None
        self.inferred_types: dict[T: float] = {}

    def guess_type(self) -> T:
        """ Guesses the type of the cell solely on its text contents.

        Also stores all possible types, as these are necessary for the
        type inference.

        :return: The type that is most likely based on the cells contents.
        """

        if self.possible_types:
            return get_max_key(self.possible_types)

        possible_types = {}

        for t, ind in ABS_INDICATORS.items():
            value = int(ind(self.cell))
            if not value:
                continue
            possible_types[t] = int(value)
        # It may always happen that a cell is not of any proper type.
        possible_types[T.Other] = .5

        # If the cell contains no identifiers, it could still be one of these.
        if len(possible_types) == 1:
            possible_types = {t: 1 for t in ABS_FALLBACK}
            # However, the chance that it is not, is higher.
            possible_types[T.Other] = 2

        div = sum(possible_types.values())
        self.possible_types = {key: round(value / div, 3)
                               for key, value in possible_types.items()}

        return get_max_key(self.possible_types)

    def infer_type_from_neighbors(self) -> T:
        """ Infer the type of the cell based on other cells.

        Other cells, in general, are the direct neighbors or the row/col.

        :return: The type that has the highest probability of being the
            "true" type, when considering both the content and other cells.
        """
        if not self.possible_types:
            self.guess_type()
        inferred_types = {}
        for t, possibility in self.possible_types.items():
            ind = REL_INDICATORS.get(t, lambda *_: possibility)
            value = ind(self.cell)
            if not value:
                continue
            inferred_types[t] = value * possibility

        self.inferred_types = inferred_types
        self.inferred_type = get_max_key(self.inferred_types)
        return self.inferred_type


class EmptyCellType(CellType):
    """ Used to "calculate" the type. Always returns the T.Empty type. """
    def __init__(self, cell: C) -> None:
        super().__init__(cell)
        self.possible_types = {T.Empty: 1}
        self.inferred_types = {T.Empty: 1}
        self.inferred_type = T.Empty

    def guess_type(self) -> T:
        """ The type of empty cells is always the same.

        :return: T.Empty
        """
        return T.Empty

    def infer_type_from_neighbors(self) -> T:
        """ The type of empty cells is always the same.

        :return: T.Empty
        """
        return T.Empty


class T(Enum):
    """ The different possible types for a cell. """
    Data = 0.1
    DataAnnot = 0.2
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
                "Can only compare types with types, not '{type(other)}'.")
        return self.value > other.value

    def __lt__(self, other) -> bool:
        if not isinstance(other, T):
            raise TypeError(
                "Can only compare types with types, not '{type(other)}'.")
        return self.value < other.value

    def __eq__(self, other) -> bool:
        if not isinstance(other, T):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return id(self)


AbsIndicator: TypeAlias = Callable[[C], bool]


def is_time_data(cell: C) -> bool:
    """  Check if the cell contains text that can be converted to a time.

    :param cell: The cell in question.
    :return: True if the cell's text can be parsed using strptime,
        using Config.time_format.
    """
    try:
        celltext = cell.text
        strptime(celltext, Config.time_format)
    except ValueError:
        return False
    return True


def is_wrapper(*args) -> AbsIndicator:
    """ Simple wrapper around is_any.

    :param args: Contains lists of strings or strings, used in is_any.
    :return: Function, that takes only a cell and returns if the
        cell's text is equal to any of the (collapsed) args.
    """
    def is_any(cell: C) -> bool:
        """ Checks if the cell's text is equal to any of the values.

        Also lowers both cell text and each value.

        :param cell:  The cell the text content is checked.
        :return: True, if the cell's text contains any of the values,
            False otherwise.
        """
        return cell.text.lower() in [v.lower() for v in values]

    values = list(collapse(args))
    return is_any


def is_repeat_value(cell: C) -> bool:
    """ Check if the cell contains text that could be a repeat value.

    :param cell: The cell in question.
    :return: True, if the text is either a number, two numbers
        seperated by a hypen or two numbers seperated by a comma.
        False, otherwise.
    """
    # Match numbers, numbers seperated by hyphen and numbers seperated by comma
    # TODO: Should not only check for hyphen but things like emdash as well.
    #  See Nurminen's thesis
    return bool(re.match(r"^\d+$"
                         r"|^\d+\s?-\s?\d+$"
                         r"|\d+\s?,\s?\d+$",
                         cell.text))


def is_legend(cell: C) -> bool:
    """ Checks if the cell's text could be (part of) a legend.

    :param cell:  The cell in question.
    :return: True, if the cell contains a non-empty string, followed by a
        colon or equals, followed by another non-empty string.
    """
    return bool(re.match(r"^\S+\s?[:=]\s?\S+$", cell.text))


def true(*_) -> bool:
    """ Always true.

    :return: True, regardless of arguments.
    """
    return True


def false(*_) -> bool:
    """ Always False.

    :return: False, regardless of arguments.
    """
    return False


ABS_INDICATORS: dict[T: AbsIndicator] = {
    T.Data: is_time_data,
    T.Days: is_wrapper(Config.header_values),
    T.RepeatIdent: is_wrapper(Config.repeat_identifier),
    T.StopAnnot: is_wrapper(Config.arrival_identifier,
                            Config.departure_identifier),
    T.RouteAnnotIdent: is_wrapper(Config.route_identifier),
    T.EntryAnnotIdent: is_wrapper(Config.annot_identifier),
    T.LegendIdent: is_legend,
    }
ABS_FALLBACK: list[T] = [T.Stop, T.RouteAnnotValue, T.RepeatValue,
                         T.EntryAnnotValue, T.DataAnnot, T.LegendValue]


RelIndicator: TypeAlias = Callable[[C], float]


def cell_has_type(cell: C, typ: T, strict: bool = True) -> bool:
    """ Check if the cell has the given type.

    :param cell: The cell in question.
    :param typ: The type the cells' type is checked against.
    :param strict: If true, check only the most probable type.
        Otherwise, all possible types are checked against.
    :return:
    """
    if strict:
        return cell.get_type() == typ
    return typ in cell.type.possible_types


def cell_has_type_wrapper(typ: T, strict: bool = True
                          ) -> Callable[[C], bool]:
    """ Simple wrapper around has_type.

    :param typ: The type passed to cell_has_type.
    :param strict: The strict argument passed to cell_has_type.
    :return: A function that takes a cell and returns, whether the
        cell has the given type.
    """
    def _cell_has_type(cell: C) -> bool:
        return cell_has_type(cell, typ, strict)

    return _cell_has_type


def cell_row_contains_type(cell: C, typ: T) -> bool:
    """ Check, if the cell's row contains a cell with the given typ.

    :param cell: The cell used to get the row.
    :param typ: The type the rows' cells are checked against.
    :return: True, if there is at least one cell with the given type.
        False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    return any(map(func, cell.row))


def cell_col_contains_type(cell: C, typ: T) -> bool:
    """ Check, if the cell's col contains a cell with the given typ.

    :param cell: The cell used to get the col.
    :param typ: The type the cols' cells are checked against.
    :return: True, if there is at least one cell with the given type.
        False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    return any(map(func, cell.col))


def cell_neighbor_has_type(cell: C, typ: T, direct_neighbor: bool = False,
                           directions: list[Direction] = D) -> bool:
    """ Check, if the cell has a neighbor with the given type.

    :param cell: The cell in question.
    :param typ: The type we check the neighbors against.
    :param direct_neighbor: Whether, to only check direct neighbors, that is
        neighbors that may be empty. If False, get the first neighbor in each
        direction, that is not empty.
    :param directions: If given, only the neighbors in these directions
        will be checked.
    :return: True, if any of the cells neighbors is of the given type.
        False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    return any(map(func, cell.get_neighbors(allow_empty=direct_neighbor,
                                            directions=directions)))


def cell_neighbor_has_type_wrapper(typ: T, direct_neighbor: bool = False
                                   ) -> Callable[[C], float]:
    """ Simple wrapper around cell_neighbor_has_type.

    :param typ: The type passed to cell_neighbor_has_type.
    :param direct_neighbor: Passed to cell_neighbor_has_type.
    :return: A function that, when called with a cell, returns if the
        cell has any (direct) neighbor of the given type.
    """
    def _cell_neighbor_has_type(cell: C) -> float:
        return float(cell_neighbor_has_type(cell, typ, direct_neighbor))

    return _cell_neighbor_has_type


def cell_is_between_type(cell: C, typ: T) -> bool:
    """ Check if the cell is 'sandwiched' between cells of the given type.

    :param cell: The cell in question
    :param typ: The type the two opposite, direct neighbors should both have.
    :return: True, if any two opposite, direct neighbors are of the
        given type. False, otherwise.
    """
    func = cell_has_type_wrapper(typ)
    for o in (V, H):
        lower = cell.get_neighbor(o.lower)
        upper = cell.get_neighbor(o.upper)
        if lower and func(lower) and upper and func(upper):
            return True
    return False


def cell_is_between_type_wrapper(typ: T) -> Callable[[C], bool]:
    """ Simple wrapper around cell_is_between_type.

    :param typ: The type passed to cell_is_between_type.
    :return: A function that, when passed a cell, returns if the cell
        is 'sandwiched' between two cells of the given type.
    """
    def _cell_is_between_type(cell: C) -> bool:
        return cell_is_between_type(cell, typ)

    return _cell_is_between_type


def rel_multiple_function_wrapper(funcs: tuple[RelIndicator, ...]
                                  ) -> RelIndicator:
    """ A simple wrapper, running all the given indicator functions.

    :param funcs: The functions that should be run.
    :return: A function that, when passed a cell, returns the average return
        value of the given functions, when run with that cell as argument.
    """
    def _run(cell: C) -> float:
        return sum(func(cell) for func in funcs) / len(funcs)

    return _run


def series_contains_type(cell: C, o: Orientation, typ: T) -> bool:
    """ Check if any cell in the cells' row/col has the given type.

    :param cell: This cells' row/col is checked.
    :param o: Based on this, the row (H) or column (V) is checked.
    :param typ: The type each cell is checked against.
    :return: True, if there exists a cell with the given type in the
        cells row/col.
        False, otherwise.
    """
    if o == V:
        return cell_col_contains_type(cell, typ)
    return cell_row_contains_type(cell, typ)


def data_aligned_cells_are_non_empty(starter: C, o: Orientation,
                                     cell_type: T, neighbor_type: T | None
                                     ) -> bool:
    """ Checks if the row/col of starter, contains empty cells
    in the cols/rows where the data cells are.

    :param starter: The row/col of this cell will be checked.
    :param o: The orientation of the series of starter. The normal
        orientation to o will be used to check neighbors of each empty cell.
    :param cell_type: The type the aligned cells should have.
    :param neighbor_type: The type (other than T.Data) the neighbors of any
        encountered EmptyFields should have. If this is None, at least one
        neighbor must be of type `Data`. In either case, neighbors must exist.
    :return: True, if all cells of the starter's col/row, that are within
        a row/col that contains datacells are either non-empty cells with
        `Stop` as possible type or are empty and either are missing a
        neighbor in the normal orientation or such a neighbor has a different
        type than T.Stop or T.Data. False, otherwise.
    """
    from pdf2gtfs.datastructures.table.cell import EmptyCell

    n = o.normal
    neighbor_types = [T.Data]
    if neighbor_type is not None:
        neighbor_types.append(neighbor_type)
    for cell in starter.table.get_series(o, starter):
        if not series_contains_type(cell, n, T.Data):
            continue
        if not isinstance(cell, EmptyCell):
            if not cell.has_type(cell_type):
                return False
            continue
        # The current cell may be part of an incomplete row/col, which will
        # be merged to a proper Stop cell.
        neighbors = cell.get_neighbors(allow_none=True,
                                       allow_empty=False,
                                       directions=[n.lower, n.upper])
        # Check the type of the neighbors.
        correct_types = 0
        for neighbor in neighbors:
            if neighbor and neighbor.has_type(*neighbor_types):
                correct_types += 1
        if correct_types < len(neighbor_types):
            return False
    return True


def series_is_aligned(starter: C, o: Orientation,
                      max_displacement: float = 0.5) -> bool:
    """ Checks if the cells in starter's row/col are aligned.

    :param starter: This cells row/col will be checked.
    :param o: Whether to check row (H) or col (V) of starter.
    :param max_displacement: The maximum displacement between a cell's
        lower x-/y-coordinate (based on o) and the smallest x-/y-coordinate
        of all checked cells.
    :return: True, if the lower x-/y-coordinate of all checked cells
        differ at most by max_displacement. False, otherwise.
    """
    bbox_attr = "x0" if o == V else "y0"
    lower_coords: list[float] = []
    for cell in starter.table.get_series(o, starter):
        # Only check data cells.
        if not series_contains_type(cell, o.normal, T.Data):
            continue
        lower_coords.append(getattr(cell.bbox, bbox_attr))
    lower_coords.sort()
    # Only the largest difference needs to be checked.
    return max_displacement >= (lower_coords[-1] - lower_coords[0])


def rel_indicator_stop(cell: C) -> float:
    """ The relative indicator for T.Stop.

    :param cell: The cell that has its type evaluated.
    :return: A value between 0 and 2.5, representing change in probability,
        based on the funcs called.
    """
    # Stops are never between the table's data-cells.
    if cell_is_between_type(cell, T.Data):
        return 0
    col_contains_data = cell_col_contains_type(cell, T.Data)
    row_contains_data = cell_row_contains_type(cell, T.Data)
    # We need exactly one of col/row to contain data. Otherwise, cell is
    # either diagonal or inside the grid spanned by the table's data-cells.
    if (col_contains_data + row_contains_data) % 2 == 0:
        return 0
    score = 1
    if col_contains_data:
        # Every row that contains data must contain a stop.
        if not data_aligned_cells_are_non_empty(cell, H, T.Stop, T.Stop):
            return 0
        # Stop columns are (generally) left aligned.
        score += series_is_aligned(cell, H)
        # If the column contains data, the row should contain stops.
        score += cell_row_contains_type(cell, T.Stop)
        score += cell_neighbor_has_type(
            cell, T.StopAnnot, directions=[N, S])
    elif row_contains_data:
        # Every col that contains data must contain a stop.
        if not data_aligned_cells_are_non_empty(cell, V, T.Stop, T.Stop):
            return 0
        score += series_is_aligned(cell, V)
        score += cell_col_contains_type(cell, T.Stop)
        score += cell_neighbor_has_type(
            cell, T.StopAnnot, directions=[W, E])

    return score


def rel_indicator_stop_annot(cell: C) -> float:
    """ The relative indicator for T.StopAnnot.

    :param cell: The cell that has its type evaluated.
    :return: A value between 0 and 1, representing change in probability,
        based on the results of the functions called.
    """
    col_contains_data = cell_col_contains_type(cell, T.Data)
    row_contains_data = cell_row_contains_type(cell, T.Data)
    # Either the row or col has to contain data, but never both.
    if (col_contains_data + row_contains_data) % 2 == 0:
        return 0
    score = 1
    if col_contains_data:
        if not data_aligned_cells_are_non_empty(cell, H, T.StopAnnot, None):
            return 0
        score += cell_neighbor_has_type(cell, T.Stop, directions=[N, S])
        score += cell_neighbor_has_type(cell, T.StopAnnot, directions=[W, E])
    elif row_contains_data:
        if not data_aligned_cells_are_non_empty(cell, V, T.StopAnnot, None):
            return 0
        score += cell_neighbor_has_type(cell, T.Stop, directions=[W, E])
        score += cell_neighbor_has_type(cell, T.StopAnnot, directions=[N, S])

    return score


def rel_indicator_data_annot(cell: C) -> float:
    """ The relative indicator for T.DataAnnot.

    :param cell: The cell that has its type evaluated.
    :return: 0, if the cell either has no direct neighbor of type Data or if
        the cell's fontsize is greater or equal to the data cells' fontsize.
        1, otherwise.
    """
    neighbor_of_data = cell_neighbor_has_type(cell, T.Data, True)
    if not neighbor_of_data:
        return 0

    data_neighbors = [n for n in cell.get_neighbors(
        allow_none=False, allow_empty=False) if n.get_type() == T.Data]
    mean_data_fontsize = mean(map(attrgetter("fontsize"), data_neighbors))
    return cell.fontsize < mean_data_fontsize


def rel_indicator_repeat_ident(cell: C) -> float:
    """ The relative indicator for T.RepeatIdent.

    :param cell: The cell that has its type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    # TODO: Check if we should be checking non-direct neighbors here as well.
    required = cell_is_between_type_wrapper(T.Data)

    if not required(cell):
        return 0.
    return 1. + cell_neighbor_has_type(cell, T.RepeatValue, True)


def rel_indicator_repeat_value(cell: C) -> float:
    """ The relative indicator for T.RepeatValue.

    :param cell: The cell that has its type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    funcs = (cell_is_between_type_wrapper(T.Data),
             cell_is_between_type_wrapper(T.RepeatIdent))
    # Both are strictly required.
    return (rel_multiple_function_wrapper(funcs)(cell) == 1.0) * 2


def rel_indicator_entry_annot_value(cell: C) -> float:
    """ The relative indicator for T.EntryAnnotValue.

    :param cell: The cell that has its type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    mod = 0
    # It is less likely for a cell to be an annotation, if the col that
    # contains the annotation identifier also contains Stops.
    if cell_col_contains_type(cell, T.EntryAnnotIdent):
        mod += (cell_row_contains_type(cell, T.Data)
                - cell_col_contains_type(cell, T.Stop))
    elif cell_row_contains_type(cell, T.EntryAnnotIdent):
        mod += (cell_col_contains_type(cell, T.Data)
                - cell_row_contains_type(cell, T.Stop))

    return mod * 2


REL_INDICATORS: dict[T: RelIndicator] = {
    T.Data: cell_neighbor_has_type_wrapper(T.Data),
    T.Stop: rel_indicator_stop,
    T.StopAnnot: rel_indicator_stop_annot,
    T.DataAnnot: rel_indicator_data_annot,
    T.EntryAnnotValue: rel_indicator_entry_annot_value,
    T.RepeatIdent: rel_indicator_repeat_ident,
    T.RepeatValue: rel_indicator_repeat_value,
    T.Other: lambda *_: 0.1,
    }
