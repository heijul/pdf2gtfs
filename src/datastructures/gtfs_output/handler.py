from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from holidays.utils import country_holidays
from datetime import datetime as dt

from cli.cli import AnnotationInputHandler
from config import Config
from datastructures.gtfs_output.calendar import Calendar
from datastructures.gtfs_output.calendar_dates import CalendarDates
from datastructures.gtfs_output.route import Routes
from datastructures.gtfs_output.gtfsstop import GTFSStops
from datastructures.gtfs_output.stop_times import StopTimes, Time
from datastructures.gtfs_output.trips import Trips
from datastructures.gtfs_output.agency import Agency
from datastructures.timetable.entries import TimeTableRepeatEntry, TimeTableEntry


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


class GTFSHandler:
    def __init__(self):
        self._agency = Agency()
        self._stops = GTFSStops()
        self._routes = Routes()
        self._calendar = Calendar()
        self._trips = Trips()
        self._stop_times = StopTimes()
        self._calendar_dates = CalendarDates()
        self._setup()

    def _setup(self):
        self.agency.add()

    def timetable_to_gtfs(self, timetable: TimeTable):
        timetable.clean_values()
        if not timetable.stops.stops:
            return
        for stop in timetable.stops.stops:
            self.stops.add(stop.name)
        stop_entries = list(self.stops.entries)
        route_name = (f"{stop_entries[0].stop_name}"
                      f"-{stop_entries[-1].stop_name}")
        route_id = self.routes.add(route_name).route_id

        stop_times = self.generate_stop_times(route_id, timetable.entries)
        # Add generated stop_times to ours.
        for times in stop_times:
            self.stop_times.merge(times)

        self.generate_calendar_dates()

    def generate_stop_times(self, route_id, entries: list[TimeTableEntry]
                            ) -> list[StopTimes]:
        """ Generate the full stop_times of the given entries.

        Will remember the previous stop_times created and use the previous and
        current (i.e. stop_times before and after the repeat column) to
        generate the stop_times for the repeat column.
        """

        stop_times = []
        prev = None
        repeat = None
        service_day_offset = 0
        for entry in entries:
            if isinstance(entry, TimeTableRepeatEntry):
                repeat = entry
                continue

            calendar_entry, newly_created = self.calendar.add(
                entry.days.days, entry.annotations)
            service_id = calendar_entry.service_id
            if newly_created:
                service_day_offset = 0
                prev = None
            trip = self.trips.add(route_id, service_id)
            times = StopTimes()
            times.add_multiple(trip.trip_id, self.stops,
                               service_day_offset, entry.values)

            if prev and prev > times:
                times.shift(Time(24))
                service_day_offset += 1

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

    def generate_calendar_dates(self):
        # TODO: Should not disable service for sundays on holidays which
        #  fall on sundays... Will only make a difference if there are
        #  different timetables for sundays/holidays...

        holiday_dates, non_holiday_dates = self.calendar.group_by_holiday()

        years = [date.year for date in Config.gtfs_date_bounds]
        years = list(range(years[0], years[1] + 1))
        holidays = country_holidays(Config.holiday_code[0],
                                    Config.holiday_code[1],
                                    years=years)

        for holiday in holidays:
            for date in holiday_dates:
                self.calendar_dates.add(date.service_id, holiday, True)
            for date in non_holiday_dates:
                self.calendar_dates.add(date.service_id, holiday, False)

    def add_annotation_dates(self):
        def get_services_with_annot(_annot):
            return [e for e in self.calendar.entries
                    if _annot in e.annotations]

        if Config.non_interactive:
            return

        annots = set()
        raw_annots = [e.annotations for e in self.calendar.entries]
        for annot in raw_annots:
            annots |= annot
        if not annots:
            return
        input_handler = AnnotationInputHandler(self, annots)
        input_handler.run()

        for annot, values in input_handler.get_values().items():
            services = get_services_with_annot(annot)
            for service in services:
                for value, active in values:
                    self.calendar_dates.add(
                        service.service_id, value, active)

    def write_files(self):
        self.add_annotation_dates()
        path = Path("../out/").resolve()
        path.mkdir(exist_ok=True)
        self.agency.write(path)
        self.stops.write(path)
        self.routes.write(path)
        self.calendar.write(path)
        self.trips.write(path)
        self.stop_times.write(path)
        self.calendar_dates.write(path)

    def add_coordinates(self, route):
        logger.info("Adding coordinates to stops.")
        for node in route:
            stop = self.stops.get(node.stop)
            if stop is None:
                dist, stop = self.stops.get_closest(node.stop)
                msg = f"No precise match for '{node.stop}'."
                if stop is None:
                    logger.info(msg)
                    continue
                logger.info(f"{msg} Found match with distance: "
                            f"({dist}, '{stop.stop_name}').")
                if stop.stop_lat > 0:
                    continue
            stop.set_location(node.lat, node.lon)
        logger.info("Done.")

    @property
    def agency(self) -> Agency:
        return self._agency

    @property
    def routes(self) -> Routes:
        return self._routes

    @property
    def stops(self) -> GTFSStops:
        return self._stops

    @property
    def calendar(self) -> Calendar:
        return self._calendar

    @property
    def trips(self) -> Trips:
        return self._trips

    @property
    def stop_times(self) -> StopTimes:
        return self._stop_times

    @property
    def calendar_dates(self) -> CalendarDates:
        return self._calendar_dates
