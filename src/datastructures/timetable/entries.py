# TODO: Rename.
from config import Config
from datastructures.timetable.datatypes import TimeData
from datastructures.timetable.stops import Stop


class Weekdays:
    days: list[int]

    def __init__(self, raw_header_text: str):
        self.days = Config.header_values.get(raw_header_text.strip(), [])


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
