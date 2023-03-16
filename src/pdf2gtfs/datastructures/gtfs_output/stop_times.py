""" Used by the handler to create the file 'stop_times.txt'. """

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from datetime import datetime as dt
from itertools import cycle
from pathlib import Path
from statistics import mean

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output import BaseContainer, BaseDataClass
from pdf2gtfs.datastructures.gtfs_output.stop import GTFSStops
from pdf2gtfs.datastructures.gtfs_output.trips import Trip_Factory
from pdf2gtfs.datastructures.timetable.stops import Stop


logger = logging.getLogger(__name__)


@dataclass
class Time:
    """ Dataclass used to compare and convert times. """
    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    @staticmethod
    def from_string(time_string: str, fmt: str = None) -> Time:
        """ Return a new Time, by trying to transform it into a dt.time. """
        time_string = time_string.replace(" ", "")
        try:
            time = dt.strptime(time_string, fmt or Config.time_format)
        except ValueError:
            logger.warning(f"Value '{time_string}' does not seem to have the "
                           f"necessary format '{Config.time_format}'.")
            return Time()
        return Time(time.hour, time.minute, time.second)

    @staticmethod
    def from_gtfs(gtfs_time_string: str) -> Time:
        """ Return a new Time from the given gtfs string (HH:MM:SS). """
        try:
            hours, minutes, seconds = gtfs_time_string.split(":")
            return Time(int(hours), int(minutes), int(seconds))
        except ValueError:
            return Time()

    def to_output(self) -> str:
        """ Returns the time in ISO-8601 format. """
        return f"{self.hours:02}:{self.minutes:02}:{self.seconds:02}"

    def copy(self) -> Time:
        """ Returns a new Time object with the same values. """
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
            minutes += seconds // 60
            seconds = seconds % 60
        if minutes < 0:
            hours += minutes // 60
            minutes = minutes % 60
        time = Time(hours, minutes, seconds)
        if time < Time():
            return Time()
        return time

    def to_hours(self) -> float:
        """ Returns a float describing the time in hours. """
        return self.hours + self.minutes / 60 + self.seconds / 3600

    @staticmethod
    def from_hours(hours: float) -> Time:
        """ Creates a new Time using hours. """
        return Time.from_minutes(60 * hours)

    @staticmethod
    def from_minutes(float_minutes: float) -> Time:
        """ Creates a new time using minutes. """
        hours = int(float_minutes) // 60
        minutes = float_minutes % 60
        seconds = int(round((minutes - int(minutes)) * 60, 0))
        return Time(hours, int(minutes), seconds)


@dataclass(init=False)
class GTFSStopTimesEntry(BaseDataClass):
    """ A single 'stop_times.txt' entry. """
    trip_id: str
    arrival_time: Time
    departure_time: Time
    stop_id: str
    stop_sequence: int

    def __init__(self, trip_id: str, stop_id: str, stop_sequence: int,
                 arrival_time: Time, departure_time: Time = None) -> None:
        super().__init__()
        self.trip_id = trip_id
        self.stop_id = stop_id
        self.stop_sequence = stop_sequence
        self.arrival_time = arrival_time
        self.departure_time = departure_time or arrival_time.copy()

    def duplicate(self, trip_id: str) -> GTFSStopTimesEntry:
        """ Return a new instance of this entry with the given trip_id. """
        return GTFSStopTimesEntry(trip_id, self.stop_id, self.stop_sequence,
                                  self.arrival_time, self.departure_time)

    @staticmethod
    def from_series(s: pd.Series) -> GTFSStopTimesEntry:
        """ Creates a new GTFSTrip from the given series. """
        arr_time = Time.from_gtfs(s["arrival_time"])
        dep_time = Time.from_gtfs(s["departure_time"])
        return GTFSStopTimesEntry(s["trip_id"], s["stop_id"],
                                  int(s["stop_sequence"]), arr_time, dep_time)

    def __eq__(self, other: GTFSStopTimesEntry):
        for field in fields(self):
            if self.get_field_value(field) != other.get_field_value(field):
                return False
        return True


def get_repeat_deltas(deltas: list[int]) -> cycle[Time]:
    """ Return a cycle of the repeat deltas, depending on the strategy. """
    if Config.repeat_strategy == "mean":
        return cycle([Time.from_minutes(mean(deltas))])
    return cycle([Time.from_minutes(delta) for delta in deltas])


class GTFSStopTimes(BaseContainer):
    """ Used to create the 'stop_times.txt.'. """
    entries: list[GTFSStopTimesEntry]

    def __init__(self, path: Path) -> None:
        super().__init__("stop_times.txt", GTFSStopTimesEntry, path)

    def add(self, trip_id: str, stop_id: str, sequence: int,
            arrival: Time, departure: Time = None) -> GTFSStopTimesEntry:
        """ Add a new StopTimeEntry with the given values.
        If departure is None, it will be set to arrival. """
        entry = GTFSStopTimesEntry(
            trip_id, stop_id, sequence, arrival, departure)
        return self._add(entry)

    def add_multiple(self, trip_id: str, gtfs_stops: GTFSStops,
                     offset: int, time_strings: dict[Stop: str]
                     ) -> list[GTFSStopTimesEntry]:
        """ Creates a new entry for each time_string. """

        entries = []
        last_entry = None
        last_gtfs_stop = None
        service_day_delta = Time(offset)
        prev_time = Time()

        for seq, (stop, time_string) in enumerate(time_strings.items()):
            if stop.is_connection:
                continue
            gtfs_stop = gtfs_stops.get(stop.name)
            time = Time.from_string(time_string)
            if time < prev_time:
                service_day_delta += Time(24)
            prev_time = time.copy()
            time += service_day_delta

            # Consecutive stops with the same name indicate arrival/departure
            if last_gtfs_stop and last_gtfs_stop == gtfs_stop:
                last_entry.departure_time = time
                continue

            last_gtfs_stop = gtfs_stop
            stop_id = gtfs_stops.get(stop.normalized_name).stop_id
            last_entry = self.add(trip_id, stop_id, seq, time)
            entries.append(last_entry)

        return entries

    def merge(self, other: GTFSStopTimes):
        """ Merge two stop_times files.

        No actual merging happens.
        """
        self.entries += other.entries

    def _duplicate_with_trip_id(self, trip_id) -> GTFSStopTimes:
        """ Creates a new instance with updated copies of the entries. """
        new = GTFSStopTimes(self.fp.parent)

        for entry in self.entries:
            new._add(entry.duplicate(trip_id))
        return new

    def shift(self, amount: Time):
        """ Shift all entries by the given amount. """
        for entry in self.entries:
            entry.arrival_time += amount
            entry.departure_time += amount

    @staticmethod
    def add_repeat(previous: GTFSStopTimes, next_: GTFSStopTimes,
                   deltas: list[int], trip_factory: Trip_Factory):
        """ Create new stop_times for all times between previous and next. """
        assert previous < next_
        delta_cycle = get_repeat_deltas(deltas)
        new_stop_times = []

        while True:
            trip = trip_factory()
            new = previous._duplicate_with_trip_id(trip.trip_id)
            new.shift(next(delta_cycle))
            if new > next_:
                break
            new_stop_times.append(new)
            previous = new

        return new_stop_times

    def _get_entry_from_stop_id(self, stop_id: str
                                ) -> GTFSStopTimesEntry | None:
        for i, entry in enumerate(self.entries):
            if entry.stop_id == stop_id:
                return entry
        return None

    def __lt__(self, other: GTFSStopTimes):
        for entry in self.entries:
            other_entry = other._get_entry_from_stop_id(entry.stop_id)
            if not other_entry:
                continue
            return entry.arrival_time < other_entry.arrival_time

        return False

    def __le__(self, other: GTFSStopTimes):
        return self == other or self < other

    def __gt__(self, other: GTFSStopTimes):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other: GTFSStopTimes):
        return self == other or self > other

    def get_with_stop_id(self, trip_ids: list[str], stop_id: str
                         ) -> list[GTFSStopTimesEntry]:
        """ Return all StopTimesEntries using the given stop_id. """
        entries = []
        for entry in self.entries:
            if entry.stop_id == stop_id and entry.trip_id in trip_ids:
                entries.append(entry)
        return entries

    def get_with_trip_id(self, trip_id: str) -> list[GTFSStopTimesEntry]:
        """ Return all StopTimesEntries using the given trip_id. """
        stop_times = []
        for stop_time in self.entries:
            if stop_time.trip_id == trip_id:
                stop_times.append(stop_time)
        return stop_times
