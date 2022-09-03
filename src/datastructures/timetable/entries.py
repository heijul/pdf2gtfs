from config import Config
from datastructures.timetable.stops import Stop


class Weekdays:
    days: list[str]

    def __init__(self, raw_header_text: str):
        self.days = Config.header_values.get(
            raw_header_text.lower().strip(), [])

    def __repr__(self) -> str:
        return str(self.days)


class TimeTableEntry:
    def __init__(self, raw_header_text: str = "") -> None:
        self._values: dict[Stop, str] = {}
        self._annotations: set[str] = set()
        self.route_name: str = ""
        self.days: Weekdays = Weekdays(raw_header_text)

    @property
    def annotations(self) -> set[str]:
        return self._annotations

    @annotations.setter
    def annotations(self, value: set[str]) -> None:
        self._annotations = value

    @property
    def values(self) -> dict[Stop, str]:
        return self._values

    def set_value(self, stop: Stop, value: str) -> None:
        self._values[stop] = value

    def get_value(self, stop: Stop) -> str | None:
        return self._values.get(stop)


class TimeTableRepeatEntry(TimeTableEntry):
    def __init__(self, raw_header_text: str = "") -> None:
        super().__init__(raw_header_text)

    @property
    def deltas(self) -> list[int]:
        def to_int_list(_value_str: str) -> list[int]:
            try:
                _values = list(map(int, _value_str.split("-")))
            except ValueError:
                return []
            if len(_values) == 2:
                # TODO: Does range make sense here?
                #  Should probably be done in gtfs_output
                return list(range(_values[0], _values[1] + 1))

            return [_values[0]] if len(_values) else []

        start = False
        for value_str in self.values.values():
            value_str = value_str.lower().strip()
            if value_str in Config.repeat_identifier:
                start = True
                continue
            value_str = value_str.replace(" ", "")
            if not start or not value_str:
                continue

            value = to_int_list(value_str)
            if not value:
                continue
            return value
        return []
