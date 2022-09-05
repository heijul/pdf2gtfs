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
            # TODO: Use regex.
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
        values: dict[str: list[int]] = {",": [], "-": []}
        for char in values:
            values[char] = []
            try:
                values[char] = list(map(int, value_str.split(char)))
            except ValueError:
                pass

        value_list = values[","]
        if value_list:
            return value_list

        value_list = values["-"]
        if value_list:
            if len(value_list) == 2:
                return list(range(value_list[0], value_list[1] + 1))
            return value_list
        # TODO: Convert 'Alle 25 min.' to 25
        try:
            return [int(value_str)]
        except ValueError:
            pass
        return []
