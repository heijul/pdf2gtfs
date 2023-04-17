from __future__ import annotations

import re
from enum import Enum
from time import strptime
from typing import Any, Callable, TYPE_CHECKING, TypeAlias, TypeVar

from more_itertools import collapse

from pdf2gtfs.config import Config


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

    def infer_type_from_neighbors(self, ref_fields: Fs) -> T:
        if not self.possible_types:
            self.guess_type()
        inferred_types = {}
        for t, possibility in self.possible_types.items():
            ind = REL_INDICATORS.get(t, lambda *_: possibility)
            value = ind(self.field, ref_fields)
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

    def infer_type_from_neighbors(self, _: Fs) -> T:
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


def is_wrapper(*args) -> Callable[[F], bool]:
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
RelIndicator: TypeAlias = Callable[[F, Fs], float]


def ref_field_has_type(_: F, ref_fields: Fs, typ: T) -> float:
    return any(map(lambda f: f.has_type(typ), ref_fields))


def ref_field_has_type_wrapper(typ: T) -> RelIndicator:
    def _ref_field_has_type(f: F, ref_fields: Fs) -> float:
        return ref_field_has_type(f, ref_fields, typ)

    return _ref_field_has_type


def multi_func_rel_wrapper(funcs) -> RelIndicator:
    def _run(field: F, ref_fields: Fs) -> float:
        return sum(func(field, ref_fields) for func in funcs) / len(funcs)

    return _run


def rel_indicator_stop(field: F, ref_fields: Fs) -> float:
    funcs = (ref_field_has_type_wrapper(T.StopAnnot),
             ref_field_has_type_wrapper(T.Stop),
             true  # TODO NOW: BBox is roughly aligned if stop column
             )
    return multi_func_rel_wrapper(funcs)(field, ref_fields)


def rel_indicator_stop_annot(field: F, ref_fields: Fs) -> float:
    funcs = (ref_field_has_type_wrapper(T.StopAnnot),
             ref_field_has_type_wrapper(T.Stop))
    return multi_func_rel_wrapper(funcs)(field, ref_fields)


def field_is_wrapped_between_wrapper(typ: T) -> RelIndicator:
    def field_is_between(field: F, _: Fs) -> float:
        from pdf2gtfs.datastructures.table.direction import E, N, S, W

        w_neighbor = field.get_neighbor(W)
        e_neighbor = field.get_neighbor(E)
        n_neighbor = field.get_neighbor(N)
        s_neighbor = field.get_neighbor(S)
        return ((e_neighbor is not None and e_neighbor.has_type(typ)
                 and w_neighbor is not None and w_neighbor.has_type(typ))
                or
                (n_neighbor is not None and n_neighbor.has_type(typ)
                 and s_neighbor is not None and s_neighbor.has_type(typ)))

    return field_is_between


def rel_indicator_repeat_ident(field: F, ref_fields: Fs) -> float:
    required = field_is_wrapped_between_wrapper(T.Data)

    if not required(field, ref_fields):
        return 0
    return ref_field_has_type(field, ref_fields, T.RepeatValue)


def rel_indicator_repeat_value(field: F, ref_fields: Fs) -> float:
    required = (field_is_wrapped_between_wrapper(T.Data),
                field_is_wrapped_between_wrapper(T.RepeatIdent))

    return (multi_func_rel_wrapper(required)(field, ref_fields) == 1.0) * 2


REL_INDICATORS: dict[T: RelIndicator] = {
    T.Data: ref_field_has_type_wrapper(T.Data),
    T.Stop: rel_indicator_stop,
    T.StopAnnot: rel_indicator_stop_annot,
    T.DataAnnot: ref_field_has_type_wrapper(T.Data),
    T.RepeatIdent: rel_indicator_repeat_ident,
    T.RepeatValue: rel_indicator_repeat_value,
    T.Other: lambda *_: 0.1,
    }
