from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from holidays.utils import country_holidays

from cli.cli import AnnotationInputHandler
from config import Config
from datastructures.gtfs_output.calendar import Calendar
from datastructures.gtfs_output.calendar_dates import CalendarDates
from datastructures.gtfs_output.route import Routes, Route
from datastructures.gtfs_output.gtfsstop import GTFSStops
from datastructures.gtfs_output.stop_times import StopTimes, Time
from datastructures.gtfs_output.trips import Trips
from datastructures.gtfs_output.agency import Agency
from datastructures.timetable.entries import TimeTableRepeatEntry, TimeTableEntry
from finder.cluster import DummyNode
from finder.types import Route


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
        self.generate_routes(timetable)

        stop_times = self.generate_stop_times(timetable.entries)
        # Add generated stop_times to ours.
        for times in stop_times:
            self.stop_times.merge(times)
        self.trips.remove_unused(self.stop_times)
        self.generate_calendar_dates()

    def generate_routes(self, timetable: TimeTable) -> None:
        for entry in timetable.entries:
            self.routes.add_from_entry(entry)

    def generate_stop_times(self, entries: list[TimeTableEntry]
                            ) -> list[StopTimes]:
        """ Generate the full stop_times of the given entries.

        Will remember the previous stop_times created and use the previous and
        current (i.e. stop_times before and after the repeat column) to
        generate the stop_times for the repeat column.
        """

        # TODO: Cleanup; Split into multiple
        stop_times = []
        prev = None
        prev_calendar_entry = None
        repeat = None
        service_day_offset = 0
        for entry in entries:
            if isinstance(entry, TimeTableRepeatEntry):
                repeat = entry
                continue
            route_id = self.routes.get_from_entry(entry).route_id

            calendar_entry = self.calendar.try_add(
                entry.days.days, entry.annotations)
            service_id = calendar_entry.service_id
            if (prev_calendar_entry and
                    not calendar_entry.same_days(prev_calendar_entry)):
                service_day_offset = 0
                prev = None
            prev_calendar_entry = calendar_entry
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
                logger.error("Encountered a repeat column, before a normal "
                             "column was added. Skipping repeat column...")
                repeat = None
                continue
            # Create stop_times between prev and times.
            trip_factory = self.trips.get_factory(service_id, route_id)
            stop_times += StopTimes.add_repeat(
                prev, times, repeat.deltas, trip_factory)
            repeat = None

        return stop_times

    def generate_calendar_dates(self):
        # CHECK: Should not disable service for sundays on holidays which
        #  fall on sundays... Will only make a difference if there are
        #  different timetables for sundays/holidays... right?

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

    def _remove_unused_routes(self):
        used_route_ids = set([trip.route_id for trip in self.trips.entries])
        for route in list(self.routes.entries):
            if route.route_id in used_route_ids:
                continue
            self.routes.entries.remove(route)

    def write_files(self):
        self._remove_unused_routes()
        self.add_annotation_dates()
        # TODO: Error handling
        path = Path(Config.output_dir).resolve()
        path.mkdir(exist_ok=True)
        self.agency.write()
        self.stops.write()
        self.routes.write()
        self.calendar.write()
        self.trips.write()
        self.stop_times.write()
        self.calendar_dates.write()

    def add_coordinates(self, route: Route):
        logger.info("Adding coordinates to stops.")
        for node in route:
            stop = self.stops.get(node.cluster.stop)
            if isinstance(node, DummyNode):
                name = node.cluster.stop
                logger.warning(f"Could not find location for '{name}'. You "
                               f"will need to manually add the coordinates.")
            # TODO: Rethink this. As it is now, this will never be called.
            if stop is None:
                dist, stop = self.stops.get_closest(node.name)
                msg = f"No precise match for '{node.name}'."
                if stop is None:
                    logger.info(msg)
                    continue
                if dist != 0:
                    logger.info(
                        f"{msg} Found partial match '{stop.stop_name}' "
                        f"with edit distance {dist}.")
                if stop.stop_lat > 0:
                    continue
            stop.set_location(*node.loc)
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
