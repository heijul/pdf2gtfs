from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from datastructures.gtfs_output.calendar import Calendar
from datastructures.gtfs_output.route import Routes
from datastructures.gtfs_output.stop import Stops
from datastructures.gtfs_output.stop_times import StopTimes
from datastructures.gtfs_output.trips import Trips
from datastructures.gtfs_output.agency import Agency
from datastructures.timetable.entries import TimeTableRepeatEntry


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


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
        print(timetable)
        timetable.clean_values()
        for stop in timetable.stops.stops:
            self.stops.add(stop.name)
        stop_entries = list(self.stops.entries.values())
        route_name = (f"{stop_entries[0].stop_name}"
                      f"-{stop_entries[-1].stop_name}")
        route_id = self.routes.add(route_name).route_id

        stop_times = self.generate_stop_times(route_id, timetable.entries)
        # Add generated stop_times to ours.
        for times in stop_times:
            self.stop_times.merge(times)

    def generate_stop_times(self, route_id, entries) -> list[StopTimes]:
        """ Generate the full stop_times of the given entries.

        Will remember the previous stop_times created and use the previous and
        current (i.e. stop_times before and after the repeat column) to
        generate the stop_times for the repeat column.
        """

        stop_times = []
        prev = None
        repeat = None
        for entry in entries:
            if isinstance(entry, TimeTableRepeatEntry):
                repeat = entry
                continue

            # Create new stop_times for current entry.
            service_id = self.calendar.add(entry.days.days).service_id
            trip = self.trips.add(route_id, service_id)
            times = StopTimes()
            times.add_multiple(trip.trip_id, self.stops, entry.values)
            stop_times.append(times)

            if not repeat:
                prev = times
                continue

            if not prev:
                # TODO: Not very informative.
                logger.error("No previous column to repeat")
                repeat = None
                continue
            # Create stop_times between prev and times.
            trip_factory = self.trips.get_factory(service_id, route_id)
            stop_times += StopTimes.add_repeat(
                prev, times, repeat.deltas, trip_factory)
            repeat = None

        return stop_times

    def write_files(self):
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
