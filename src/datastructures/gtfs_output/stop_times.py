from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime as dt
from itertools import cycle
from statistics import mean

from config import Config
from datastructures.gtfs_output import BaseContainer, BaseDataClass
from datastructures.gtfs_output.gtfsstop import GTFSStops
from datastructures.gtfs_output.trips import Trip_Factory
from datastructures.timetable.stops import Stop


logger = logging.getLogger(__name__)


@dataclass
class Time:
    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    @staticmethod
    def from_string(time_string: str) -> Time:
        time_string = time_string.strip()
        try:
            time_string = time_string.replace(" ", "")
            time = dt.strptime(time_string, Config.time_format)
        except ValueError:
            logger.warning(f"Value '{time_string}' does not seem to have the "
                           f"necessary format '{Config.time_format}'.")
            return Time()
        return Time(time.hour, time.minute, 0)

    def to_output(self) -> str:
        return f"{self.hours:02}:{self.minutes:02}:{self.seconds:02}"

    def copy(self) -> Time:
        return Time(self.hours, self.minutes, self.seconds)

    def __repr__(self) -> str:
        return f"'{self.to_output()}'"

    def __bool__(self) -> bool:
        return bool(self.hours or self.minutes or self.seconds)

    def __radd__(self, other) -> Time:
        return self.__add__(other)

    def __add__(self, other: Time) -> Time:
        seconds = self.seconds + other.seconds
        minute_delta = seconds // 60
        minutes = self.minutes + other.minutes + minute_delta
        hour_delta = minutes // 60
        hours = self.hours + other.hours + hour_delta
        return Time(hours,
                    minutes - hour_delta * 60,
                    seconds - minute_delta * 60)

    def __eq__(self, other: Time) -> bool:
        return (self.hours == other.hours and
                self.minutes == other.minutes and
                self.seconds == other.seconds)

    def __lt__(self, other: Time) -> bool:
        if self.hours != other.hours:
            return self.hours < other.hours
        if self.minutes != other.minutes:
            return self.minutes < other.minutes
        return self.seconds < other.seconds

    def __le__(self, other: Time) -> bool:
        return self == other or self < other

    def __gt__(self, other: Time) -> bool:
        return not self <= other

    def __sub__(self, other: Time) -> Time:
        if not isinstance(other, Time):
            raise TypeError(f"Can only substract Time from "
                            f"Time, not '{type(other)}'.")
        hours = self.hours - other.hours
        minutes = self.minutes - other.minutes
        seconds = self.seconds - other.seconds
        if seconds < 0:
            minutes -= seconds // 60
        if minutes < 0:
            hours -= minutes // 60
        return Time(hours, minutes, seconds)

    def to_hours(self) -> float:
        return self.hours + self.minutes / 60 + self.seconds / 3600

    @staticmethod
    def from_hours(hours: float) -> Time:
        return Time.from_minutes(60 * hours)

    @staticmethod
    def from_minutes(float_minutes: float) -> Time:
        hours = int(float_minutes) // 60
        minutes = int(float_minutes % 60)
        seconds = int(round((minutes - int(minutes)) * 60, 0))
        return Time(hours, minutes, seconds)


@dataclass(init=False)
class StopTimesEntry(BaseDataClass):
    trip_id: str
    arrival_time: Time
    departure_time: Time
    stop_id: str
    stop_sequence: int

    def __init__(self, trip_id: str, stop_id: str, stop_sequence: int,
                 arrival_time: Time, departure_time: Time = None):
        super().__init__()
        self.trip_id = trip_id
        self.stop_id = stop_id
        self.stop_sequence = stop_sequence
        self.arrival_time = arrival_time
        self.departure_time = departure_time or arrival_time.copy()

    def duplicate(self, trip_id: str) -> StopTimesEntry:
        """ Return a new instance of this entry with the given trip_id. """
        return StopTimesEntry(trip_id, self.stop_id, self.stop_sequence,
                              self.arrival_time, self.departure_time)


def _get_repeat_deltas(deltas: list[int]) -> cycle[Time]:
    if Config.repeat_strategy == "mean":
        return cycle([Time.from_minutes(mean(deltas))])
    return cycle([Time.from_minutes(delta) for delta in deltas])


class StopTimes(BaseContainer):
    entries: list[StopTimesEntry]

    def __init__(self) -> None:
        super().__init__("stop_times.txt", StopTimesEntry)

    def add(self, trip_id: str, stop_id: str, sequence: int,
            arrival: Time, departure: Time = None) -> StopTimesEntry:
        entry = StopTimesEntry(trip_id, stop_id, sequence, arrival, departure)
        return self._add(entry)

    def add_multiple(self, trip_id: str, stops: GTFSStops,
                     offset: int, time_strings: dict[Stop: str]
                     ) -> list[StopTimesEntry]:
        """ Creates a new entry for each time_string. """

        entries = []
        last_stop_name = ""
        last_entry = None
        service_day_delta = Time(offset)
        prev_time = Time()

        for seq, (stop, time_string) in enumerate(time_strings.items()):
            if stop.is_connection:
                continue
            time = Time.from_string(time_string)
            if time < prev_time:
                service_day_delta += Time(24)
            prev_time = time.copy()
            time += service_day_delta

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
        self.entries += other.entries

    def duplicate(self, trip_id) -> StopTimes:
        """ Creates a new instance with updated copies of the entries. """
        new = StopTimes()

        for entry in self.entries:
            new._add(entry.duplicate(trip_id))
        return new

    def shift(self, amount: Time):
        """ Shift all entries by the given amount. """
        for entry in self.entries:
            entry.arrival_time += amount
            entry.departure_time += amount

    @staticmethod
    def add_repeat(previous: StopTimes, next_: StopTimes,
                   deltas: list[int], trip_factory: Trip_Factory):
        """ Create new stop_times for all times between previous and next. """
        assert previous < next_
        delta_cycle = _get_repeat_deltas(deltas)
        new_stop_times = []

        while True:
            trip = trip_factory()
            new = previous.duplicate(trip.trip_id)
            new.shift(next(delta_cycle))
            if new > next_:
                break
            new_stop_times.append(new)
            previous = new

        return new_stop_times

    def __get_entry_from_stop_id(self, stop_id: str) -> StopTimesEntry | None:
        for i, entry in enumerate(self.entries):
            if entry.stop_id == stop_id:
                return entry
        return None

    def __lt__(self, other: StopTimes):
        for entry in self.entries:
            other_entry = other.__get_entry_from_stop_id(entry.stop_id)
            if not other_entry:
                continue
            return entry.arrival_time < other_entry.arrival_time

        return False

    def __gt__(self, other: StopTimes):
        return not self.__lt__(other)

    def get_with_stop_id(self, stop_id: str) -> list[StopTimesEntry]:
        entries = []
        for entry in self.entries:
            if entry.stop_id == stop_id:
                entries.append(entry)
        return entries

    def get_with_trip_id(self, trip_id: str) -> list[StopTimesEntry]:
        stop_times = []
        for stop_time in self.entries:
            if stop_time.trip_id == trip_id:
                stop_times.append(stop_time)
        return stop_times
