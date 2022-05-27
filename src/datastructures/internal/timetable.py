from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Type, Generic, TypeVar

from config import Config
from datastructures.internal.base import (
    BaseContainer, BaseField, BaseContainerList)
import datastructures.internal.rawtable as raw


TFieldContainerT = TypeVar("TFieldContainerT", bound="TFieldContainer")
TimeTableT = TypeVar("TimeTableT", bound="TimeTable")
TColumnT = TypeVar("TColumnT", bound="TColumn")
TRowT = TypeVar("TRowT", bound="TRow")
TFieldValueT = TypeVar("TFieldValueT")
TFieldT = TypeVar("TFieldT", bound="TField")


class TField(BaseField, Generic[TFieldValueT]):
    def __init__(self, timetable: TimeTable):
        super().__init__()
        self.timetable = timetable
        self.value: TFieldValueT | None = None

    def _set_value(self, raw_field: raw.Field) -> None:
        self.value = raw_field.text

    @classmethod
    def from_raw_field(cls, timetable: TimeTable, raw_field: raw.Field
                       ) -> TField:
        field = cls(timetable)
        field._set_value(raw_field)
        return field

    def __str__(self):
        return f"{self.value}"

    def __repr__(self):
        name = self.__class__.__name__
        return (f"{name}(row_id: {self.row.id}, "
                f"col_id: {self.column.id}, value: '{self.value}')")


class TStopField(TField[str]):
    def _set_value(self, raw_field: raw.Field) -> None:
        self.value = raw_field.text.strip()


@dataclass
class TimeData:
    hours: int
    minutes: int

    def __add__(self, other) -> TimeData:
        return TimeData(self.hours + other.hours,
                        self.minutes + other.minutes)


class TDataField(TField[TimeData]):
    def _set_value(self, raw_field: raw.Field) -> None:
        text = raw_field.text.strip()
        try:
            dt = datetime.strptime(text, Config.time_format)
            value = TimeData(dt.hour, dt.minute)
        except ValueError:
            print(f"WARNING: Timedata {text} could not be parsed.")
            value = None
        self.value = value

    @property
    def valid(self):
        return self.data is not None

    def _set_data(self, data_str: str):
        try:
            data = datetime.strptime(data_str, Config.time_format)
        except ValueError:
            self.data = None
            return

        self.data = TimeData(data.hour, data.minute)


class TAnnotationField(TField[str]):
    def _set_value(self, raw_field: raw.Field) -> None:
        self.value = raw_field.text.strip()
        # TODO: Update self.annotates

    @property
    def annotates(self):
        return self._annotates

    @annotates.setter
    def annotates(self, value: TFieldContainer):
        self._annotates = value


class TStopAnnotationField(TAnnotationField):
    def _set_value(self, raw_field: raw.Field) -> None:
        super()._set_value(raw_field)
        # TODO: Set self.annotates


class TDataColumnAnnotationField(TAnnotationField):
    def _set_value(self, raw_field: raw.Field) -> None:
        super()._set_value(raw_field)
        # TODO: Set self.annotates
        # TODO: Update type of annotates -> add Generic to TAnnotationField


class TFieldContainer(Generic[TFieldT, TimeTableT],
                      BaseContainer[TFieldT, TimeTableT]):
    ...


class TColumn(TFieldContainer[TField, TimeTableT]):
    def __init__(self):
        super().__init__()
        self.field_attr = "column"

    @property
    def id(self):
        return self.table.columns.index(self)


class TRepeatColumn(TColumn):
    ...


class TRow(TFieldContainer[TField, TimeTableT]):
    def __init__(self):
        super().__init__()
        self.field_attr = "row"

    @property
    def id(self):
        return self.table.rows.index(self)


class TContainerList(BaseContainerList[TimeTableT, TFieldContainerT]):
    pass


class TRowList(TContainerList[TimeTableT, TRowT]):
    pass


class TColumnList(TContainerList[TimeTableT, TColumnT]):
    pass


def _get_field_type(raw_field: raw.Field) -> Type[TField]:
    if raw_field.column.type == raw.ColumnType.STOP:
        return TStopField
    if raw_field.column.type == raw.ColumnType.STOP_ANNOTATION:
        return TStopAnnotationField
    if raw_field.row.type == raw.RowType.ANNOTATION:
        return TDataColumnAnnotationField
    if raw_field.row.type == raw.RowType.DATA:
        return TDataField
    return TField[str]


class Stop:
    def __init__(self, name: str, annot: str = "", connection: bool = False):
        self.name = name
        self.annotation = annot
        self.is_connection = connection

    def __eq__(self, other):
        return self.name == other.name and self.annotation == other.annotation

    def __hash__(self):
        return hash(self.name + " " + self.annotation)

    def __str__(self):
        # Add a/d for arrival/departure, depending on annotation.
        annot = {"": "", "an": "[a]", "ab": "[d]"}[self.annotation.strip()]
        return self.name.strip() + " " + annot


class StopList:
    def __init__(self):
        self._stops: list[Stop] = []

    @property
    def all_stops(self):
        return self._stops

    @property
    def stops(self):
        return [stop for stop in self._stops if not stop.is_connection]

    def add_stop(self, stop: Stop) -> None:
        self._stops.append(stop)

    def add_annotation(self, text: str,
                       *, stop: Stop = None, stop_id: int = None) -> None:
        if stop_id is not None:
            stop = self.stops[stop_id]
        stop.annotation = text


# TODO: Rename.
class Weekdays:
    days: list[int]

    def __init__(self, raw_header_text: str):
        self._set_days(raw_header_text)

    def _set_days(self, raw_value: str) -> None:
        # TODO: Use config for this. header_identifier should then be updated
        #  to be a dict instead. Or add another config item...
        value = raw_value.replace(" ", "").lower()
        if value == "montag-freitag":
            self.days = list(range(0, 5))
        elif value == "samstag":
            self.days = [5]
        elif value in ["sonntag", "sonn-undfeiertag"]:
            self.days = [6]
        else:
            self.days = []


class TimeTableEntry:
    def __init__(self, raw_header_text: str = "") -> None:
        self._values: dict[Stop, TimeData] = {}
        self._annotations: list[str] = []
        self.days: Weekdays = Weekdays(raw_header_text)

    @property
    def values(self) -> dict[Stop, TimeData]:
        return self._values

    def set_value(self, stop: Stop, value: TimeData) -> None:
        self._values[stop] = value

    def get_value(self, stop: Stop) -> TimeData | None:
        return self._values.get(stop)

    def add_annotation(self, annotation: str) -> None:
        self._annotations.append(annotation)


def get_stop_annotation_index(raw_table: raw.Table, raw_field: raw.Field):
    """ Returns the index of the stop this annotation is for. """
    i = raw_table.rows.index(raw_field.row)

    for row in list(raw_table.rows):
        if row.type == raw.RowType.DATA:
            break
        i -= 1
    return i


class TimeTable:
    def __init__(self):
        self.rows: TRowList = TRowList(self)
        self.columns: TColumnList = TColumnList(self)
        self.stops = StopList()
        self.entries: list[TimeTableEntry()] = []

    def detect_connection(self):
        """ Detect stops which are actually connections.

        Will search for reoccurring stops and mark every stop within the
        cycle as a connection. Stops with different arrival/departure times
        will not be added as connections because of how range works.
        """

        cycles: dict[str, list[int]] = {}
        for i, stop in enumerate(self.stops.all_stops):
            cycle = cycles.setdefault(stop.name, [])
            cycle.append(i)

        indices = []
        for cycle in cycles.values():
            if len(cycle) == 1:
                continue
            start_idx = sorted(cycle)[0] + 1
            end_idx = sorted(cycle)[-1]

            # Prevent marking every stop as connection if it's a round trip.
            if start_idx == 0 and end_idx == len(self.stops.stops) - 1:
                continue
            indices += list(range(start_idx, end_idx))
            for stop in self.stops.all_stops[start_idx:end_idx]:
                stop.is_connection = True

    @staticmethod
    def from_raw_table(raw_table: raw.Table) -> TimeTable:
        table = TimeTable()

        for raw_column in list(raw_table.columns):
            raw_header_text = raw_table.get_header_from_column(raw_column)
            table.entries.append(TimeTableEntry(raw_header_text))

            for raw_field in raw_column:
                if raw_field.column.type == raw.ColumnType.STOP:
                    if raw_field.row.type == raw.RowType.DATA:
                        stop = Stop(raw_field.text)
                        table.stops.add_stop(stop)
                    continue
                if raw_field.column.type == raw.ColumnType.STOP_ANNOTATION:
                    index = get_stop_annotation_index(raw_table, raw_field)
                    table.stops.add_annotation(raw_field.text, stop_id=index)
                elif raw_field.row.type == raw.RowType.ANNOTATION:
                    table.entries[-1].add_annotation(raw_field.text)
                elif raw_field.row.type == raw.RowType.DATA:
                    index = get_stop_annotation_index(raw_table, raw_field)
                    stop = table.stops.stops[index]
                    table.entries[-1].set_value(stop, raw_field.text)
            # TODO: Check why this happens and fix it.
            if not table.entries[-1].values:
                del table.entries[-1]

        table.detect_connection()
        if table.stops.stops:
            print(table)
        return table

    def __str__(self):
        # Entry columns + stop column
        base_text = "{:30}" + "{:>6}" * len(self.entries)
        texts = []
        for stop in self.stops.stops:
            text = [str(stop)]
            for entry in self.entries:
                value = entry.get_value(stop)
                text.append(value if value else "-")
            texts.append(base_text.format(*text).strip())
        return "TimeTable:\n\t" + "\n\t".join(texts)

    def __repr__(self):
        name = self.__class__.__name__
        field_count = (
            len(set([field for row in self.rows for field in row])),
            len(set([field for col in self.columns for field in col])))

        return (f"{name}(row_count={len(self.rows)}, "
                f"column_count={len(self.columns)}, "
                f"field_count={field_count})")
