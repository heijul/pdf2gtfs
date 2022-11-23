""" Used to obtain unique stops, even if their names do not differ. """
from __future__ import annotations

from utils import normalize_name


class Stop:
    """ The stop of a TimeTableEntry. """

    def __init__(self, name: str, raw_row_id: int):
        self.name = name
        self.normalized_name = normalize_name(name)
        self.raw_row_id = raw_row_id
        self.annotation = ""
        self.is_connection = False

    def clean(self) -> None:
        """ Removes surrounding whitespace. """
        # TODO NOW: Remove all parentheses and double spaces,
        #  and all chars except ',.-+/&'
        self.name = self.name.strip()

    def __eq__(self, other) -> bool:
        return self.name == other.name and self.annotation == other.annotation

    def __hash__(self) -> int:
        return hash(self.name + " " + self.annotation)

    def __str__(self) -> str:
        # Add a/d for arrival/departure, depending on annotation.
        annots = {"an": " [a]", "ab": " [d]"}
        return self.name.strip() + annots.get(self.annotation.strip(), "")

    def __repr__(self) -> str:
        return f"'{str(self)}'"


class StopList:
    """ TimeTable stops, used to select which stops are actual stops
    and which are only connections from the previous stop. """

    def __init__(self) -> None:
        self._stops: list[Stop] = []

    @property
    def all_stops(self) -> list[Stop]:
        """ Returns both connections as well as normal stops. """
        return self._stops

    @property
    def stops(self) -> list[Stop]:
        """ Only return stops that are not connections. """
        return [stop for stop in self._stops if not stop.is_connection]

    def add_stop(self, stop: Stop) -> None:
        """ Add the given stop. """
        self._stops.append(stop)

    def get_from_id(self, row_id: int) -> Stop:
        """ Return the stop with the given row_id. """
        for stop in self.stops:
            if stop.raw_row_id == row_id:
                return stop

    def add_annotation(self, text: str,
                       *, stop: Stop = None, stop_id: int = None) -> None:
        """ Add the text to the stop with the given stop_id, or stop. """
        if stop_id is not None:
            stop = self.get_from_id(stop_id)
        stop.annotation = text

    def clean(self) -> None:
        """ Clean all stops. """
        for stop in self._stops:
            stop.clean()
