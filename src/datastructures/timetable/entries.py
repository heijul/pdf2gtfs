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
        start = False
        for value in self.values.values():
            value = value.lower().strip()
            if value in Config.repeat_identifier:
                start = True
                continue
            value = value.replace(" ", "")
            if not start or not value:
                continue

            int_list = self._to_int_list(value)
            if not int_list:
                continue
            return int_list
        return []

    @staticmethod
    def _to_int_list(value_str: str) -> list[int]:
        """ Turn the value_str to a list of ints, depending its format.
        If it is of the form:
            - "x,y,..." it returns [x, y, ...]
            - "x-y" it returns [x, x1, ..., xn, y] where x1 = x + 1 if
              x + 1 < y. E.g. "7-9" returns [7, 8, 9]
            - Otherwise it returns a single element list of int(value_str)
        """
        values: dict[str: list[int]] = {}
        split_chars = [",", "-"]
        try:
            for char in split_chars:
                values[char] = []
                values[char] = list(map(int, value_str.split(char)))
        except ValueError:
            pass
        if values[","]:
            return values[","]
        if values["-"]:
            if len(values["-"]) == 2:
                return list(range(values["-"][0], values["-"][1] + 1))
            return values["-"]
        try:
            return [int(value_str)]
        except ValueError:
            pass
        return []
