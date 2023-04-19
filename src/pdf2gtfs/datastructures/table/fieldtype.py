from __future__ import annotations

import re
from enum import Enum
from time import strptime
from typing import Any, Callable, TYPE_CHECKING, TypeAlias, TypeVar

from more_itertools import collapse

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.table.direction import H, V


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.fields import Field


F: TypeAlias = "Field"
Fs: TypeAlias = list[F]

A = TypeVar("A")


def get_max_key(dict_: dict[A, Any]) -> A:
    return max(dict_.items(), key=lambda item: item[1])[0]


class FieldType:
    def __init__(self, field: F) -> None:
        self.field = field
        # Probabilities for the different types.
        self.possible_types: dict[T: float] = {}
        self.inferred_type: T | None = None
        self.inferred_types: dict[T: float] = {}

    def guess_type(self) -> T:
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
    def __init__(self, field: F) -> None:
        super().__init__(field)
        self.possible_types = {T.Empty: 1}
        self.inferred_types = {T.Empty: 1}
        self.inferred_type = T.Empty

    def guess_type(self) -> T:
        return T.Empty

    def infer_type_from_neighbors(self) -> T:
        return T.Empty


class T(Enum):
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


def is_any(field: F, values: list[str]) -> bool:
    return field.text.lower() in [v.lower() for v in values]


def is_time_data(field: F) -> bool:
    try:
        fieldtext = field.text
        strptime(fieldtext, Config.time_format)
    except ValueError:
        return False
    return True


def is_wrapper(*args) -> AbsIndicator:
    def _is_any_wrapper(field: F) -> bool:
        return is_any(field, values)

    values = list(collapse(args))
    return _is_any_wrapper


def is_repeat_value(field: F) -> bool:
    # Match numbers, numbers seperated by hyphen and numbers seperated by comma
    return bool(re.match(r"^\d+$|^\d+\s?-\s?\d+$|\d+\s?,\s?\d+$", field.text))


def is_legend(field: F) -> bool:
    return bool(re.match(r"^.+\s?[:=].+$", field.text))


def true(*_) -> bool:
    return True


def false(*_) -> bool:
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


def field_has_type_wrapper(typ: T) -> Callable[[F], bool]:
    def field_has_type(field: F) -> bool:
        return field.get_type() == typ

    return field_has_type


def field_row_contains_type(field: F, typ: T) -> bool:
    func = field_has_type_wrapper(typ)
    return any(map(func, field.row))


def field_col_contains_type(field: F, typ: T) -> bool:
    func = field_has_type_wrapper(typ)
    return any(map(func, field.col))


def field_neighbor_has_type(field: F, typ: T, direct_neighbor: bool = False
                            ) -> bool:
    func = field_has_type_wrapper(typ)
    return any(map(func, field.get_neighbors(allow_empty=not direct_neighbor)))


def field_neighbor_has_type_wrapper(typ: T, direct_neighbor: bool = False
                                    ) -> Callable[[F], float]:
    def _field_neighbor_has_type(field: F) -> float:
        return float(field_neighbor_has_type(field, typ, direct_neighbor))

    return _field_neighbor_has_type


def field_is_between_type(field: F, typ: T) -> bool:
    func = field_has_type_wrapper(typ)
    for o in (V, H):
        lower = field.get_neighbor(o.lower)
        upper = field.get_neighbor(o.upper)
        if lower and func(lower) and upper and func(upper):
            return True
    return False


def field_is_between_type_wrapper(typ: T) -> Callable[[F], bool]:
    def _field_is_between_type(field: F) -> bool:
        return field_is_between_type(field, typ)

    return _field_is_between_type


def rel_multiple_function_wrapper(funcs: tuple[Callable[[F], bool], ...]
                                  ) -> RelIndicator:
    def _run(field: F) -> float:
        return sum(func(field) for func in funcs) / len(funcs)

    return _run


def rel_indicator_stop(field: F) -> float:
    funcs = (field_neighbor_has_type_wrapper(T.StopAnnot),
             field_neighbor_has_type_wrapper(T.Stop),
             )
    return bool(rel_multiple_function_wrapper(funcs)(field)) * 2.5


def rel_indicator_stop_annot(field: F) -> float:
    funcs = (field_neighbor_has_type_wrapper(T.StopAnnot),
             field_neighbor_has_type_wrapper(T.Stop))
    return rel_multiple_function_wrapper(funcs)(field)


def rel_indicator_repeat_ident(field: F) -> float:
    required = field_is_between_type_wrapper(T.Data)

    if not required(field):
        return 0.
    return 1. + field_neighbor_has_type(field, T.RepeatValue, True)


def rel_indicator_repeat_value(field: F) -> float:
    funcs = (field_is_between_type_wrapper(T.Data),
             field_is_between_type_wrapper(T.RepeatIdent))
    # Both are strictly required.
    return (rel_multiple_function_wrapper(funcs)(field) == 1.0) * 2


def rel_indicator_entry_annot_value(field: F) -> float:
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
    T.DataAnnot: field_neighbor_has_type_wrapper(T.Data),
    T.EntryAnnotValue: rel_indicator_entry_annot_value,
    T.RepeatIdent: rel_indicator_repeat_ident,
    T.RepeatValue: rel_indicator_repeat_value,
    T.Other: lambda *_: 0.1,
    }
