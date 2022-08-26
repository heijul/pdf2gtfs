from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from holidays.utils import country_holidays

from config import Config
from datastructures.gtfs_output.agency import Agency
from datastructures.gtfs_output.calendar import Calendar, CalendarEntry
from datastructures.gtfs_output.calendar_dates import CalendarDates
from datastructures.gtfs_output.gtfsstop import GTFSStops
from datastructures.gtfs_output.route import Routes
from datastructures.gtfs_output.stop_times import StopTimes, Time
from datastructures.gtfs_output.trips import Trips
from datastructures.timetable.entries import TimeTableEntry, TimeTableRepeatEntry
from finder import Route3
from finder.osm_node import DummyOSMNode
from user_input.cli import handle_annotations


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


def create_output_dir() -> bool:
    path = Path(Config.output_dir).resolve()
    try:
        path.mkdir(exist_ok=True)
    except OSError as e:
        msg = ("An error occurred, while trying "
               "to create the output directory:\n")
        if isinstance(e, PermissionError):
            msg += "You are missing the permissions, to create it."
        elif isinstance(e, FileExistsError):
            msg += "There already exists a file with the same name."
        else:
            msg += str(e)
        if Config.non_interactive:
            return False
        # TODO: Wait for user input to move files/fix permissions
    return True


class GTFSHandler:
    def __init__(self) -> None:
        self._agency = Agency()
        self._stops = GTFSStops()
        self._routes = Routes(self.agency.get_default().agency_id)
        self._calendar = Calendar()
        self._trips = Trips()
        self._stop_times = StopTimes()
        self._calendar_dates = CalendarDates()

    def timetable_to_gtfs(self, timetable: TimeTable):
        timetable.clean_values()
        if not timetable.stops.stops:
            return
        for stop in timetable.stops.stops:
            self.stops.add(stop.name)
        self.generate_routes(timetable)

        stop_times = self.generate_stop_times(timetable.entries)
        # Add generated stoptimes to ours.
        for times in stop_times:
            self.stop_times.merge(times)
        self.trips.remove_unused(self.stop_times)
        self.generate_calendar_dates()

    def generate_routes(self, timetable: TimeTable) -> None:
        for entry in timetable.entries:
            self.routes.add_from_entry(entry)

    def generate_stop_times(self, entries: list[TimeTableEntry]
                            ) -> list[StopTimes]:
        """ Generate the full stoptimes of the given entries.

        Will remember the previous stoptimes created and use the previous and
        current (i.e. stoptimes before and after the repeat column) to
        generate the stoptimes for the repeat column.
        """

        def create_calendar_entry() -> CalendarEntry:
            return self.calendar.add(entry.days.days, entry.annotations)

        def new_entry_is_on_new_service_day() -> bool:
            if not prev_calendar_entry:
                return False
            return not calendar_entry.same_days(prev_calendar_entry)

        def create_stop_times() -> StopTimes:
            trip = trip_factory()
            _stop_times = StopTimes()
            _stop_times.add_multiple(
                trip.trip_id, self.stops, service_day_offset, entry.values)
            return _stop_times

        def end_of_day() -> bool:
            return prev and prev > times

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

            calendar_entry = create_calendar_entry()
            if new_entry_is_on_new_service_day():
                service_day_offset = 0
                prev = None

            trip_factory = self.trips.get_factory(
                calendar_entry.service_id, route_id)
            times = create_stop_times()

            if end_of_day():
                times.shift(Time(24))
                service_day_offset += 1

            stop_times.append(times)
            prev_calendar_entry = calendar_entry

            if not repeat:
                prev = times
                continue

            if prev is None:
                logger.error("Encountered a repeat column, before a normal "
                             "column was added. Skipping repeat column...")
                repeat = None
                continue

            # Create stoptimes between prev and times.
            stop_times += StopTimes.add_repeat(
                prev, times, repeat.deltas, trip_factory)
            repeat = None

        return stop_times

    def generate_calendar_dates(self) -> None:
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

    def add_annotation_dates(self) -> None:
        def get_annots() -> list[str]:
            annot_set = set()
            raw_annots = [e.annotations for e in self.calendar.entries]
            for _annot in raw_annots:
                annot_set |= _annot
            return list(annot_set)

        def get_services_with_annot(_annot) -> list[CalendarEntry]:
            return [e for e in self.calendar.entries
                    if _annot in e.annotations]

        if Config.non_interactive:
            return

        annots = get_annots()
        if not annots:
            return

        # TODO: If multiple annotations which are active on the same service
        #  have different defaults, default=off will take precedence.
        annot_exceptions = handle_annotations(annots)
        for annot, (default, dates) in annot_exceptions.items():
            services = get_services_with_annot(annot)
            for service in services:
                if not default:
                    service.disable()
                self.calendar_dates.add_multiple(
                    service.service_id, dates, not default)

    def _remove_unused_routes(self) -> None:
        used_route_ids = set([trip.route_id for trip in self.trips.entries])
        for route in list(self.routes.entries):
            if route.route_id in used_route_ids:
                continue
            self.routes.entries.remove(route)

    def write_files(self) -> bool:
        if not create_output_dir():
            return False
        self._remove_unused_routes()
        self.add_annotation_dates()
        self.agency.write()
        self.stops.write()
        self.routes.write()
        self.calendar.write()
        self.trips.write()
        self.stop_times.write()
        self.calendar_dates.write()
        return True

    def add_coordinates(self, route: Route3) -> None:
        if not route:
            logger.warning("No route was found. "
                           "Can not add coordinates to stops.")
            return
        logger.info("Adding coordinates to stops.")
        for node in route.nodes:
            stop = self.stops.get(node.stop)
            # No need to add the location to existing stops, as these will
            #  not be updated anyway
            if stop.valid:
                continue
            if isinstance(node, DummyOSMNode):
                logger.warning(
                    f"Could not find location for '{stop.stop_name}'. "
                    f"You will have to manually add the coordinates.")
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
