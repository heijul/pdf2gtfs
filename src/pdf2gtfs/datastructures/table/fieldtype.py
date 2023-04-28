""" Contains the field types, as well as the functions used to infer them. """

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
    from pdf2gtfs.datastructures.table.fields import Field


F: TypeAlias = "Field"
Fs: TypeAlias = list[F]

A = TypeVar("A")


def get_max_key(dict_: dict[A, Any]) -> A:
    """ Given the dictionary, return the key for the maximal value.

    :param dict_: The dictionary.
    :return: The key for the maximal value.
    """
    return max(dict_.items(), key=lambda item: item[1])[0]


class FieldType:
    """ Can be used to guess/infer the type of a field. """
    def __init__(self, field: F) -> None:
        self.field = field
        # Probabilities for the different types.
        self.possible_types: dict[T: float] = {}
        self.inferred_type: T | None = None
        self.inferred_types: dict[T: float] = {}

    def guess_type(self) -> T:
        """ Guesses the type of the field solely on its text contents.

        Also stores all possible types, as these are necessary for the
        type inference.

        :return: The type that is most likely based on the fields contents.
        """
        possible_types = {}

        for t, ind in ABS_INDICATORS.items():
            value = int(ind(self.field))
            if not value:
                continue
            possible_types[t] = int(value)
        # It may always happen that a field is not of any proper type.
        possible_types[T.Other] = 1

        # If the field contains no identifiers, it could still be one of these.
        if len(possible_types) == 1:
            possible_types = {t: 1 for t in ABS_FALLBACK}
            # However, the chance that it is not, is higher.
            possible_types[T.Other] = 2

        self.possible_types = {key: round(value / (len(possible_types) + 1), 3)
                               for key, value in possible_types.items()}

        return get_max_key(self.possible_types)

    def infer_type_from_neighbors(self) -> T:
        """ Infer the type of the field based on other fields.

        Other fields, in general, are the direct neighbors or the row/col.

        :return: The type that has the highest probability of being the
            "true" type, when considering both the content and other fields.
        """
        if not self.possible_types:
            self.guess_type()
        inferred_types = {}
        for t, possibility in self.possible_types.items():
            ind = REL_INDICATORS.get(t, lambda *_: possibility)
            value = ind(self.field)
            if not value:
                continue
            inferred_types[t] = value * possibility

        self.inferred_types = inferred_types
        self.inferred_type = get_max_key(self.inferred_types)
        return self.inferred_type


class EmptyFieldType(FieldType):
    """ Used to "calculate" the type. Always returns the T.Empty type. """
    def __init__(self, field: F) -> None:
        super().__init__(field)
        self.possible_types = {T.Empty: 1}
        self.inferred_types = {T.Empty: 1}
        self.inferred_type = T.Empty

    def guess_type(self) -> T:
        """ The type of empty fields is always the same.

        :return: T.Empty
        """
        return T.Empty

    def infer_type_from_neighbors(self) -> T:
        """ The type of empty fields is always the same.

        :return: T.Empty
        """
        return T.Empty


class T(Enum):
    """ The different possible types for a field. """
    Data = "data"
    Stop = "stop"
    Days = "days"
    RepeatIdent = "repeat.ident"
    RepeatValue = "repeat.value"
    StopAnnot = "stop.annot.ident"
    RouteAnnotIdent = "route.annot.ident"
    RouteAnnotValue = "route.annot.value"
    EntryAnnotIdent = "entry.annot.ident"
    EntryAnnotValue = "entry.annot.value"
    DataAnnot = "data.annot"
    LegendIdent = "legend.ident"
    LegendValue = "legend.value"
    Other = "other"
    Empty = "empty"


AbsIndicator: TypeAlias = Callable[[F], bool]


def is_time_data(field: F) -> bool:
    """  Check if the field contains text that can be converted to a time.

    :param field: The field in question.
    :return: True if the field's text can be parsed using strptime,
        using Config.time_format.
    """
    try:
        fieldtext = field.text
        strptime(fieldtext, Config.time_format)
    except ValueError:
        return False
    return True


def is_wrapper(*args) -> AbsIndicator:
    """ Simple wrapper around is_any.

    :param args: Contains lists of strings or strings, used in is_any.
    :return: Function, that takes only a field and returns if the
        field's text is equal to any of the (collapsed) args.
    """
    def is_any(field: F) -> bool:
        """ Checks if the field's text is equal to any of the values.

        Also lowers both field text and each value.

        :param field:  The field the text content is checked.
        :return: True, if the field's text contains any of the values,
            False otherwise.
        """
        return field.text.lower() in [v.lower() for v in values]

    values = list(collapse(args))
    return is_any


def is_repeat_value(field: F) -> bool:
    """ Check if the field contains text that could be a repeat value.

    :param field: The field in question.
    :return: True, if the text is either a number, two numbers
        seperated by a hypen or two numbers seperated by a comma.
        False, otherwise.
    """
    # Match numbers, numbers seperated by hyphen and numbers seperated by comma
    return bool(re.match(r"^\d+$|^\d+\s?-\s?\d+$|\d+\s?,\s?\d+$", field.text))


def is_legend(field: F) -> bool:
    """ Checks if the field's text could be (part of) a legend.

    :param field:  The field in question.
    :return: True, if the field contains a non-empty string, followed by a
        colon or equals, followed by another non-empty string.
    """
    return bool(re.match(r"^\S+\s?[:=]\s?\S+$", field.text))


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


RelIndicator: TypeAlias = Callable[[F], float]


def field_has_type(field: F, typ: T, strict: bool = True) -> bool:
    """ Check if the field has the given type.

    :param field: The field in question.
    :param typ: The type the fields' type is checked against.
    :param strict: If true, check only the most probable type.
        Otherwise, all possible types are checked against.
    :return:
    """
    if strict:
        return field.get_type() == typ
    return typ in field.type.possible_types


def field_has_type_wrapper(typ: T, strict: bool = True
                           ) -> Callable[[F], bool]:
    """ Simple wrapper around has_type.

    :param typ: The type passed to field_has_type.
    :param strict: The strict argument passed to field_has_type.
    :return: A function that takes a field and returns, whether the
        field has the given type.
    """
    def _field_has_type(field: F) -> bool:
        return field_has_type(field, typ, strict)

    return _field_has_type


def field_row_contains_type(field: F, typ: T) -> bool:
    """ Check, if the field's row contains a field with the given typ.

    :param field: The field used to get the row.
    :param typ: The type the rows' fields are checked against.
    :return: True, if there is at least one field with the given type.
        False, otherwise.
    """
    func = field_has_type_wrapper(typ)
    return any(map(func, field.row))


def field_col_contains_type(field: F, typ: T) -> bool:
    """ Check, if the field's col contains a field with the given typ.

    :param field: The field used to get the col.
    :param typ: The type the cols' fields are checked against.
    :return: True, if there is at least one field with the given type.
        False, otherwise.
    """
    func = field_has_type_wrapper(typ)
    return any(map(func, field.col))


def field_neighbor_has_type(field: F, typ: T, direct_neighbor: bool = False,
                            directions: list[Direction] = D) -> bool:
    """ Check, if the field has a neighbor with the given type.

    :param field: The field in question.
    :param typ: The type we check the neighbors against.
    :param direct_neighbor: Whether, to only check direct neighbors, that is
        neighbors that may be empty. If False, get the first neighbor in each
        direction, that is not empty.
    :param directions: If given, only the neighbors in these directions
        will be checked.
    :return: True, if any of the fields neighbors is of the given type.
        False, otherwise.
    """
    func = field_has_type_wrapper(typ)
    return any(map(func, field.get_neighbors(allow_empty=direct_neighbor,
                                             directions=directions)))


def field_neighbor_has_type_wrapper(typ: T, direct_neighbor: bool = False
                                    ) -> Callable[[F], float]:
    """ Simple wrapper around field_neighbor_has_type.

    :param typ: The type passed to field_neighbor_has_type.
    :param direct_neighbor: Passed to field_neighbor_has_type.
    :return: A function that, when called with a field, returns if the
        field has any (direct) neighbor of the given type.
    """
    def _field_neighbor_has_type(field: F) -> float:
        return float(field_neighbor_has_type(field, typ, direct_neighbor))

    return _field_neighbor_has_type


def field_is_between_type(field: F, typ: T) -> bool:
    """ Check if the field is 'sandwiched' between fields of the given type.

    :param field: The field in question
    :param typ: The type the two opposite, direct neighbors should both have.
    :return: True, if any two opposite, direct neighbors are of the
        given type. False, otherwise.
    """
    func = field_has_type_wrapper(typ)
    for o in (V, H):
        lower = field.get_neighbor(o.lower)
        upper = field.get_neighbor(o.upper)
        if lower and func(lower) and upper and func(upper):
            return True
    return False


def field_is_between_type_wrapper(typ: T) -> Callable[[F], bool]:
    """ Simple wrapper around field_is_between_type.

    :param typ: The type passed to field_is_between_type.
    :return: A function that, when passed a field, returns if the field
        is 'sandwiched' between two fields of the given type.
    """
    def _field_is_between_type(field: F) -> bool:
        return field_is_between_type(field, typ)

    return _field_is_between_type


def rel_multiple_function_wrapper(funcs: tuple[RelIndicator, ...]
                                  ) -> RelIndicator:
    """ A simple wrapper, running all the given indicator functions.

    :param funcs: The functions that should be run.
    :return: A function that, when passed a field, returns the average return
        value of the given functions, when run with that field as argument.
    """
    def _run(field: F) -> float:
        return sum(func(field) for func in funcs) / len(funcs)

    return _run


def series_contains_type(field: F, o: Orientation, typ: T) -> bool:
    if o == V:
        return field_col_contains_type(field, typ)
    return field_row_contains_type(field, typ)


def data_aligned_fields_are_non_empty(starter: F, o: Orientation,
                                      field_type: T, neighbor_type: T | None
                                      ) -> bool:
    """ Checks if the row/col of starter, contains empty fields
    in the cols/rows where the data fields are.

    :param starter: The row/col of this field will be checked.
    :param o: The orientation of the series of starter. The normal
        orientation to o will be used to check neighbors of each empty field.
    :param field_type: The type the aligned fields should have.
    :param neighbor_type: The type (other than T.Data) the neighbors of any
        encountered EmptyFields should have. If this is None, at least one
        neighbor must be of type `Data`. In either case, neighbors must exist.
    :return: True, if all fields of the starter's col/row, that are within
        a row/col that contains datafields are either non-empty fields with
        `Stop` as possible type or are empty and either are missing a
        neighbor in the normal orientation or such a neighbor has a different
        type than T.Stop or T.Data. False, otherwise.
    """
    from pdf2gtfs.datastructures.table.fields import EmptyField

    n = o.normal
    neighbor_types = [T.Data]
    if neighbor_type is not None:
        neighbor_types.append(neighbor_type)
    for field in starter.qll.get_series(o, starter):
        if not series_contains_type(field, n, T.Data):
            continue
        if not isinstance(field, EmptyField):
            if not field.has_type(field_type):
                return False
            continue
        # The current field may be part of an incomplete row/col, which will
        # be merged to a proper Stop field.
        neighbors = field.get_neighbors(allow_none=True,
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


def series_is_aligned(starter: F, o: Orientation,
                      max_displacement: float = 0.5) -> bool:
    """ Checks if the fields in starter's row/col are aligned.

    :param starter: This fields row/col will be checked.
    :param o: Whether to check row (H) or col (V) of starter.
    :param max_displacement: The maximum displacement between a field's
        lower x-/y-coordinate (based on o) and the smallest x-/y-coordinate
        of all checked fields.
    :return: True, if the lower x-/y-coordinate of all checked fields
        differ at most by max_displacement. False, otherwise.
    """
    bbox_attr = "x0" if o == V else "y0"
    lower_coords: list[float] = []
    for field in starter.qll.get_series(o, starter):
        # Only check data fields.
        if not series_contains_type(field, o.normal, T.Data):
            continue
        lower_coords.append(getattr(field.bbox, bbox_attr))
    lower_coords.sort()
    # Only the largest difference needs to be checked.
    return max_displacement >= (lower_coords[-1] - lower_coords[0])


def rel_indicator_stop(field: F) -> float:
    """ The relative indicator for T.Stop.

    :param field: The field that has its type evaluated.
    :return: A value between 0 and 2.5, representing change in probability,
        based on the funcs called.
    """
    # Stops are never between the table's data-fields.
    if field_is_between_type(field, T.Data):
        return 0
    col_contains_data = field_col_contains_type(field, T.Data)
    row_contains_data = field_row_contains_type(field, T.Data)
    # We need exactly one of col/row to contain data. Otherwise, field is
    # either diagonal or inside the grid spanned by the table's data-fields.
    if (col_contains_data + row_contains_data) % 2 == 0:
        return 0
    score = 1
    if col_contains_data:
        # Every row that contains data must contain a stop.
        if not data_aligned_fields_are_non_empty(field, H, T.Stop, T.Stop):
            return 0
        # Stop columns are (generally) left aligned.
        score += series_is_aligned(field, H)
        # If the column contains data, the row should contain stops.
        score += field_row_contains_type(field, T.Stop)
        score += field_neighbor_has_type(
            field, T.StopAnnot, directions=[N, S])
    elif row_contains_data:
        # Every col that contains data must contain a stop.
        if not data_aligned_fields_are_non_empty(field, V, T.Stop, T.Stop):
            return 0
        score += series_is_aligned(field, V)
        score += field_col_contains_type(field, T.Stop)
        score += field_neighbor_has_type(
            field, T.StopAnnot, directions=[W, E])

    return score


def rel_indicator_stop_annot(field: F) -> float:
    """ The relative indicator for T.StopAnnot.

    :param field: The field that has its type evaluated.
    :return: A value between 0 and 1, representing change in probability,
        based on the results of the functions called.
    """
    col_contains_data = field_col_contains_type(field, T.Data)
    row_contains_data = field_row_contains_type(field, T.Data)
    # Either the row or col has to contain data, but never both.
    if (col_contains_data + row_contains_data) % 2 == 0:
        return 0
    score = 1
    if col_contains_data:
        if not data_aligned_fields_are_non_empty(field, H, T.StopAnnot, None):
            return 0
        score += field_neighbor_has_type(field, T.Stop, directions=[N, S])
        score += field_neighbor_has_type(field, T.StopAnnot, directions=[W, E])
    elif row_contains_data:
        if not data_aligned_fields_are_non_empty(field, V, T.StopAnnot, None):
            return 0
        score += field_neighbor_has_type(field, T.Stop, directions=[W, E])
        score += field_neighbor_has_type(field, T.StopAnnot, directions=[N, S])

    return score


def rel_indicator_data_annot(field: F) -> float:
    """ The relative indicator for T.DataAnnot.

    :param field: The field that has its type evaluated.
    :return: 0, if the field either has no direct neighbor of type Data or if
        the field's fontsize is greater or equal to the data fields' fontsize.
        1, otherwise.
    """
    neighbor_of_data = field_neighbor_has_type(field, T.Data, True)
    if not neighbor_of_data:
        return 0

    data_neighbors = [n for n in field.get_neighbors(
        allow_none=False, allow_empty=False) if n.get_type() == T.Data]
    mean_data_fontsize = mean(map(attrgetter("fontsize"), data_neighbors))
    return field.fontsize < mean_data_fontsize


def rel_indicator_repeat_ident(field: F) -> float:
    """ The relative indicator for T.RepeatIdent.

    :param field: The field that has its type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    # TODO: Check if we should be checking non-direct neighbors here as well.
    required = field_is_between_type_wrapper(T.Data)

    if not required(field):
        return 0.
    return 1. + field_neighbor_has_type(field, T.RepeatValue, True)


def rel_indicator_repeat_value(field: F) -> float:
    """ The relative indicator for T.RepeatValue.

    :param field: The field that has its type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    funcs = (field_is_between_type_wrapper(T.Data),
             field_is_between_type_wrapper(T.RepeatIdent))
    # Both are strictly required.
    return (rel_multiple_function_wrapper(funcs)(field) == 1.0) * 2


def rel_indicator_entry_annot_value(field: F) -> float:
    """ The relative indicator for T.EntryAnnotValue.

    :param field: The field that has its type evaluated.
    :return: A value between 0 and 2, representing change in probability,
        based on the results of the functions called.
    """
    mod = 0
    # It is less likely for a field to be an annotation, if the col that
    # contains the annotation identifier also contains Stops.
    if field_col_contains_type(field, T.EntryAnnotIdent):
        mod += (field_row_contains_type(field, T.Data)
                - field_col_contains_type(field, T.Stop))
    elif field_row_contains_type(field, T.EntryAnnotIdent):
        mod += (field_col_contains_type(field, T.Data)
                - field_row_contains_type(field, T.Stop))

    return mod * 2


REL_INDICATORS: dict[T: RelIndicator] = {
    T.Data: field_neighbor_has_type_wrapper(T.Data),
    T.Stop: rel_indicator_stop,
    T.StopAnnot: rel_indicator_stop_annot,
    T.DataAnnot: rel_indicator_data_annot,
    T.EntryAnnotValue: rel_indicator_entry_annot_value,
    T.RepeatIdent: rel_indicator_repeat_ident,
    T.RepeatValue: rel_indicator_repeat_value,
    T.Other: lambda *_: 0.1,
    }
