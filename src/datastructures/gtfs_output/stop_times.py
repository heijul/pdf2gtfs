from dataclasses import dataclass

from datetime import datetime as dt

from config import Config
from datastructures.gtfs_output.base import BaseDataClass, BaseContainer


@dataclass
class Time:
    hours: int = None
    minutes: int = None

    def to_output(self):
        return f"{self.hours:02}:{self.minutes:02}"


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
        self.departure_time = departure_time or arrival_time


class StopTimes(BaseContainer):
    def __init__(self):
        super().__init__("stop_times.txt", StopTimesEntry)

    def add(self, trip_id: int, stop_id: int, stop_sequence: int, *time_str
            ) -> StopTimesEntry:
        # Convert to proper time

        times = []
        for time in time_str:
            try:
                dt_time = dt.strptime(time, Config.time_format)
            except ValueError:
                return
            times.append(Time(dt_time.hour, dt_time.minute))
        entry = StopTimesEntry(trip_id, stop_id, stop_sequence, *times)
        self._add(entry)
        return entry
