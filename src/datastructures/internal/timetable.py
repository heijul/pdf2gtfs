from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from config import Config
from datastructures.internal.base import BaseContainer, BaseField


class TField(BaseField):
    def __init__(self, timetable: TimeTable):
        super().__init__({"row": TRow, "column": TColumn})
        self.timetable = timetable


class TStopField(TField):
    def __init__(self, timetable: TimeTable, name: str):
        super().__init__(timetable)
        self.name = name


@dataclass
class TimeData:
    hours: int
    minutes: int


class TDataField(TField):
    data: TimeData | None

    def __init__(self, timetable: TimeTable, data_str: str):
        super().__init__(timetable)
        self._set_data(data_str)

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


class TAnnotationField(TField):
    def __init__(self, timetable: TimeTable,
                 text: str, annotates: TFieldContainer | None = None):
        super().__init__(timetable)
        self.text = text
        self._annotates = annotates

    @property
    def annotates(self):
        return self._annotates

    @annotates.setter
    def annotates(self, value: TFieldContainer):
        self._annotates = value


class TRowAnnotationField(TAnnotationField):
    ...


class TColumnAnnotationField(TAnnotationField):
    ...


class TFieldContainer(BaseContainer):
    ...


class TColumn(TFieldContainer):
    ...


class TRepeatColumn(TColumn):
    ...


class TRow(TFieldContainer):
    ...


class TimeTable:
    ...
