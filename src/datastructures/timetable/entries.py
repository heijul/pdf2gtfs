# TODO: Rename.
from datastructures.timetable.datatypes import TimeData
from datastructures.timetable.stops import Stop


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
