from config import Config
from datastructures.timetable.stops import Stop


class Weekdays:
    days: list[str]

    def __init__(self, raw_header_text: str):
        self.days = Config.header_values.get(
            raw_header_text.lower().strip(), [])

    def __repr__(self):
        return str(self.days)


class TimeTableEntry:
    def __init__(self, raw_header_text: str = "") -> None:
        self._values: dict[Stop, str] = {}
        self._annotations: list[str] = []
        self.days: Weekdays = Weekdays(raw_header_text)

    @property
    def values(self) -> dict[Stop, str]:
        return self._values

    def set_value(self, stop: Stop, value: str) -> None:
        self._values[stop] = value

    def get_value(self, stop: Stop) -> str | None:
        return self._values.get(stop)

    def add_annotation(self, annotation: str) -> None:
        self._annotations.append(annotation)


class TimeTableRepeatEntry(TimeTableEntry):
    def __init__(self, raw_header_text: str = "") -> None:
        super().__init__(raw_header_text)
        self.deltas: list[int] = [5]
