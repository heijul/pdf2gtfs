""" Provide entries for the TimeTable. """

import logging

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.timetable.stops import Stop


logger = logging.getLogger(__name__)


class Weekdays:
    """ The days, where a TimeTableEntry is active. """
    days: list[str]

    def __init__(self, header_text: str):
        self.days = Config.header_values.get(
            header_text.lower().strip(), [])

    def __repr__(self) -> str:
        return str(self.days)


class TimeTableEntry:
    """ A single entry (i.e. column containing timedata) in a TimeTable. """

    def __init__(self, raw_header_text: str = "") -> None:
        self._values: dict[Stop, str] = {}
        self._annotations: set[str] = set()
        self.route_name: str = ""
        self.days: Weekdays = Weekdays(raw_header_text)

    @property
    def annotations(self) -> set[str]:
        """ The annotations of the entry. """
        return self._annotations

    @annotations.setter
    def annotations(self, value: set[str]) -> None:
        self._annotations = value

    @property
    def values(self) -> dict[Stop, str]:
        """ The stops and their respective values. """
        return self._values

    def set_value(self, stop: Stop, value: str) -> None:
        """ Set the value for a stop. """
        self._values[stop] = value

    def get_value(self, stop: Stop) -> str | None:
        """ Return the value for stop. """
        return self._values.get(stop)


class TimeTableRepeatEntry(TimeTableEntry):
    """ A repeating entry in a TimeTable. Does not contain time data. """

    def __init__(self, header_text: str, intervals: list[str]) -> None:
        super().__init__(header_text)
        self.intervals = None
        intervals = list(set(intervals))
        if len(intervals) > 1:
            logger.warning("Multiple different repeat intervals found for a "
                           "single column. Cannot discern which interval is "
                           "active between which stops. "
                           "Repeat column will be skipped.")
            return

        self.intervals = self.interval_str_to_int_list(intervals[0])

    @staticmethod
    def interval_str_to_int_list(value_str: str) -> list[int]:
        """ Turn the value_str to a list of ints, depending on its format.
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

        # value_str is a list, e.g. '3, 5, 7'
        value_list = values[","]
        if value_list:
            return value_list
        # value_str is a range, e.g. '5-7'
        value_list = values["-"]
        if value_list:
            if len(value_list) == 2:
                return list(range(value_list[0], value_list[1] + 1))
            return value_list
        # value_str is a single number, e.g. '30'
        try:
            return [int(value_str)]
        except ValueError:
            pass
        logger.error(f"Could not turn repeat string '{value_str}' "
                     f"into interval. Repeat column will be skipped.")
        return []
