from __future__ import annotations

import logging
from dataclasses import dataclass

from datetime import datetime as dt
from itertools import cycle
from typing import Callable

from config import Config
from datastructures.gtfs_output.base import BaseDataClass, BaseContainer
from datastructures.gtfs_output.stop import Stops
from datastructures.timetable.stops import Stop
from datastructures.gtfs_output.trips import TripEntry


logger = logging.getLogger(__name__)


@dataclass
class Time:
    hours: int = None
    minutes: int = None

    @staticmethod
    def from_string(time_string: str) -> Time:
        try:
            time = dt.strptime(time_string, Config.time_format)
        except ValueError:
            logger.warning(f"Value '{time_string}' does not seem to have the "
                           f"necessary format '{Config.time_format}'.")
            return Time()
        return Time(time.hour, time.minute)

    def to_output(self):
        return f"{self.hours:02}:{self.minutes:02}"

    def copy(self):
        return Time(self.hours, self.minutes)

    def __radd__(self, other):
        return self.__add__(other)

    def __add__(self, other):
        minutes = self.minutes + other.minutes
        hour_delta = minutes // 60
        hours = self.hours + other.hours + hour_delta
        return Time(hours, minutes - hour_delta * 60)

    def __lt__(self, other):
        return (self.hours < other.hours or
                self.hours == other.hours and self.minutes < other.minutes)

    def __gt__(self, other):
        return not self.__lt__(other)


@dataclass(init=False)
class StopTimesEntry(BaseDataClass):
    trip_id: int
    arrival_time: Time
    departure_time: Time
    stop_id: int
    stop_sequence: int

    def __init__(self, trip_id: int, stop_id: int, stop_sequence: int,
                 arrival_time: Time, departure_time: Time = None):
        super().__init__()
        self.trip_id = trip_id
        self.stop_id = stop_id
        self.stop_sequence = stop_sequence
        self.arrival_time = arrival_time
        self.departure_time = departure_time or arrival_time.copy()

    def duplicate(self, trip_id: int) -> StopTimesEntry:
        """ Return a new instance of this entry with the given trip_id. """
        return StopTimesEntry(trip_id, self.stop_id, self.stop_sequence,
                              self.arrival_time, self.departure_time)


class StopTimes(BaseContainer):
    entries: dict[int, StopTimesEntry]

    def __init__(self):
        super().__init__("stop_times.txt", StopTimesEntry)

    def add(self, trip_id: int, stop_id: int, sequence: int,
            arrival: Time, departure: Time = None) -> StopTimesEntry:
        entry = StopTimesEntry(trip_id, stop_id, sequence, arrival, departure)
        self._add(entry)
        return entry

    def add_multiple(
            self, trip_id: int, stops: Stops, time_strings: dict[Stop: str]
            ) -> list[StopTimesEntry]:
        """ Creates a new entry for each time_string. """

        entries = []
        last_stop_name = ""
        last_entry = None

        for seq, (stop, time_string) in enumerate(time_strings.items()):
            time = Time.from_string(time_string)

            # Consecutive stops with the same name indicate arrival/departure
            if stop.name == last_stop_name:
                last_entry.departure_time = time
                continue

            last_stop_name = stop.name
            stop_id = stops.get(stop.name).stop_id
            last_entry = self.add(trip_id, stop_id, seq, time)
            entries.append(last_entry)

        return entries

    def merge(self, other: StopTimes):
        self.entries.update(other.entries)

    def duplicate(self, trip_id) -> StopTimes:
        """ Creates a new instance with updated copies of the entries. """
        new = StopTimes()

        for entry in self.entries.values():
            new._add(entry.duplicate(trip_id))
        return new

    def shift(self, amount: Time):
        """ Shift all entries by the given amount. """
        for entry in self.entries.values():
            entry.arrival_time += amount
            entry.departure_time += amount

    @staticmethod
    def add_repeat(previous: StopTimes, next_: StopTimes,
                   deltas: list[int], trip_factory: Callable[[], TripEntry]):
        """ Create new stop_times for all times between previous and next. """
        assert previous < next_
        delta_cycle = cycle([Time(0, delta) for delta in deltas])
        new_stop_times = []

        while True:
            new = previous.duplicate(trip_factory().trip_id)
            new.shift(next(delta_cycle))
            if new > next_:
                break
            new_stop_times.append(new)
            previous = new

        return new_stop_times

    def __lt__(self, other):
        a = list(self.entries.values())[0].arrival_time
        b = list(other.entries.values())[0].arrival_time
        return a < b

    def __gt__(self, other):
        return not self.__lt__(other)
