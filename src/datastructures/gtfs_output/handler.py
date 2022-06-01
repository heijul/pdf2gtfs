from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from datastructures.gtfs_output.calendar import Calendar
from datastructures.gtfs_output.route import Routes
from datastructures.gtfs_output.stop import Stops
from datastructures.gtfs_output.stop_times import StopTimes
from datastructures.gtfs_output.trips import Trips
from datastructures.gtfs_output.agency import Agency
from datastructures.timetable.entries import TimeTableEntry


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable


class GTFSHandler:
    def __init__(self):
        self._agency = Agency()
        self._stops = Stops()
        self._routes = Routes()
        self._calendar = Calendar()
        self._trips = Trips()
        self._stop_times = StopTimes()
        self._setup()

    def _setup(self):
        self.agency.add()

    def timetable_to_gtfs(self, timetable: TimeTable):
        print(self)
        print(timetable)
        timetable.clean_values()
        for stop in timetable.stops.stops:
            self.stops.add(stop.name)
        stop_entries = list(self.stops.entries.values())
        route_name = (f"{stop_entries[0].stop_name}"
                      f"-{stop_entries[-1].stop_name}")
        route_id = self.routes.add(route_name).route_id

        for entry in timetable.entries:
            self.add_entry(route_id, entry)

    def add_entry(self, route_id: int, entry: TimeTableEntry):
        service_id = self.calendar.add(entry.days.days).service_id
        trip = self.trips.add(route_id, service_id)
        skip_next = False
        for i, (stop, value) in enumerate(entry.values.items()):
            if skip_next:
                skip_next = False
                continue
            arrival = value
            departure = value
            stop_id = self.stops.get(stop.name).stop_id
            if i + 1 < len(entry.values):
                next_stop, next_value = list(entry.values.items())[i + 1]
                if self.stops.get(next_stop.name).stop_id == stop_id:
                    departure = next_value
                    skip_next = True
            self.stop_times.add(trip.trip_id, stop_id, i, arrival, departure)

    def write_files(self):
        print(self)
        path = Path("../out/").resolve()
        path.mkdir(exist_ok=True)
        self.agency.write(path)
        self.stops.write(path)
        self.routes.write(path)
        self.calendar.write(path)
        self.trips.write(path)
        self.stop_times.write(path)

    @property
    def agency(self):
        return self._agency

    @property
    def routes(self):
        return self._routes

    @property
    def stops(self):
        return self._stops

    @property
    def calendar(self):
        return self._calendar

    @property
    def trips(self):
        return self._trips

    @property
    def stop_times(self):
        return self._stop_times
