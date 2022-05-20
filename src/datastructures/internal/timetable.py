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


class TFieldContainer(BaseContainer[TField, TimeTableT]):
    ...


class TColumn(TFieldContainer):
    def __init__(self):
        super().__init__()
        self.field_attr = "column"

    @property
    def id(self):
        return self.table.columns.index(self)


class TRepeatColumn(TColumn):
    ...


class TRow(TFieldContainer):
    def __init__(self):
        super().__init__()
        self.field_attr = "row"

    @property
    def id(self):
        return self.table.rows.index(self)


class TContainerList(Generic[TimeTableT, TFieldContainerT],
                     BaseContainerList[TimeTableT, TFieldContainer]):
    pass


class TRowList(TContainerList[TimeTableT, TColumnT]):
    pass


class TColumnList(TContainerList[TimeTableT, TRowT]):
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


class TimeTable:
    def __init__(self):
        self.rows: TRowList = TRowList(self)
        self.columns: TColumnList = TColumnList(self)

    @staticmethod
    def from_raw_table(raw_table: raw.Table) -> TimeTable:
        def _get_or_create_row(_raw_row: raw.Row) -> TRow:
            _row = rows.get(_raw_row)
            if not _row:
                _row = TRow()
                table.rows.add(_row)
                rows[_raw_row] = _row
            return _row

        table = TimeTable()
        rows: dict[raw.Row, TRow] = {}

        for raw_column in raw_table.columns:
            column = TColumn()
            table.columns.add(column)

            for raw_field in raw_column:
                field = _get_field_type(raw_field
                                        ).from_raw_field(table, raw_field)
                row = _get_or_create_row(raw_field.row)
                column.add_field(field)
                row.add_field(field)
        print(table.rows)
        return table

    def __repr__(self):
        name = self.__class__.__name__
        field_count = (
            len(set([field for row in self.rows for field in row])),
            len(set([field for col in self.columns for field in col])))

        return (f"{name}(row_count={len(self.rows)}, "
                f"column_count={len(self.columns)}, "
                f"field_count={field_count})")
