""" Contains the classes necessary to create the gtfs files. """

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from statistics import mean
from time import sleep
from typing import TYPE_CHECKING
from zipfile import ZipFile

from holidays.utils import country_holidays

from config import Config
from datastructures.gtfs_output.agency import GTFSAgency
from datastructures.gtfs_output.calendar import GTFSCalendar, GTFSCalendarEntry
from datastructures.gtfs_output.calendar_dates import GTFSCalendarDates
from datastructures.gtfs_output.routes import GTFSRoutes
from datastructures.gtfs_output.stop import GTFSStopEntry, GTFSStops
from datastructures.gtfs_output.stop_times import (
    GTFSStopTimes, GTFSStopTimesEntry, Time)
from datastructures.gtfs_output.trips import GTFSTrips
from datastructures.timetable.entries import (
    TimeTableEntry, TimeTableRepeatEntry)
from locate import Node
from locate.finder.loc_nodes import MNode
from user_input.cli import handle_annotations


if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable

logger = logging.getLogger(__name__)


def get_gtfs_archive_path() -> Path:
    """ Returns the absolute path to the output archive. """
    date_and_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    in_filename = Path(Config.filename).stem
    outname = f"pdf2gtfs_{in_filename}_{date_and_time}.zip"
    return Config.output_dir.joinpath(outname)


def get_gtfs_filepaths() -> list[Path]:
    """ Return all gtfs files. """
    filenames = ["agency.txt", "calendar.txt", "calendar_dates.txt",
                 "routes.txt", "stop_times.txt", "stops.txt", "trips.txt"]
    paths = [Config.output_dir.joinpath(name) for name in filenames]
    return paths


class GTFSHandler:
    """ Handles the creation of all gtfs files and provides
    an interface to query them. """

    def __init__(self) -> None:
        self._agency = GTFSAgency()
        self._stops = GTFSStops()
        self._routes = GTFSRoutes(self.agency.get_default().agency_id)
        self._calendar = GTFSCalendar()
        self._trips = GTFSTrips()
        self._stop_times = GTFSStopTimes()
        self._calendar_dates = GTFSCalendarDates()

    @property
    def agency(self) -> GTFSAgency:
        """ The agency. """
        return self._agency

    @property
    def routes(self) -> GTFSRoutes:
        """ The routes. """
        return self._routes

    @property
    def stops(self) -> GTFSStops:
        """ The stops. """
        return self._stops

    @property
    def calendar(self) -> GTFSCalendar:
        """ The calendar. """
        return self._calendar

    @property
    def trips(self) -> GTFSTrips:
        """ The trips. """
        return self._trips

    @property
    def stop_times(self) -> GTFSStopTimes:
        """ The stop times. """
        return self._stop_times

    @property
    def calendar_dates(self) -> GTFSCalendarDates:
        """ The calendar dates. """
        return self._calendar_dates

    def timetable_to_gtfs(self, timetable: TimeTable):
        """ Add the entries of the timetable. """
        # TODO: Add timetable.is_valid property.
        if not timetable.stops.stops:
            return
        self.add_timetable_stops(timetable)
        self.generate_routes(timetable)

        stop_times = self.generate_stop_times(timetable.entries)
        # Add generated stoptimes to ours.
        for times in stop_times:
            self.stop_times.merge(times)
        self.trips.remove_unused(self.stop_times)
        self.generate_calendar_dates()

    def add_timetable_stops(self, timetable: TimeTable) -> None:
        """ Create the stops for the given timetables. """
        for stop in timetable.stops.stops:
            self.stops.add(stop.normalized_name)

    def generate_routes(self, timetable: TimeTable) -> None:
        """ Generate the routes for the given timetable. """
        for entry in timetable.entries:
            if isinstance(entry, TimeTableRepeatEntry):
                continue
            self.routes.add_from_entry(entry)

    def generate_stop_times(self, entries: list[TimeTableEntry]
                            ) -> list[GTFSStopTimes]:
        """ Generate the full stoptimes of the given entries.

        Will remember the previous stoptimes created and use the previous and
        current (i.e. stoptimes before and after the repeat column) to
        generate the stoptimes for the repeat column.
        """

        def create_calendar_entry() -> GTFSCalendarEntry:
            """ Create a new CalendarEntry for the current TimeTableEntry. """
            return self.calendar.add(entry.days.days, entry.annotations)

        def new_entry_is_on_new_service_day() -> bool:
            """ Checks if the new entry is on the next service day. """
            if not prev_calendar_entry:
                return False
            return not calendar_entry.same_days(prev_calendar_entry)

        def create_stop_times() -> GTFSStopTimes:
            """ Creates the StopTimes for the current entry. """
            trip = trip_factory()
            _stop_times = GTFSStopTimes()
            _stop_times.add_multiple(
                trip.trip_id, self.stops, service_day_offset, entry.values)
            return _stop_times

        def end_of_day() -> bool:
            """ Check if the current entry occurs before the previous one. """
            return prev and prev > times

        stop_times = []
        prev = None
        prev_calendar_entry = None
        repeat = None
        service_day_offset = 0
        for entry in entries:
            if isinstance(entry, TimeTableRepeatEntry):
                repeat = entry if entry.intervals else None
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
            stop_times += GTFSStopTimes.add_repeat(
                prev, times, repeat.intervals, trip_factory)
            repeat = None

        return stop_times

    def generate_calendar_dates(self) -> None:
        """ Create a new CalendarDateEntry for each holiday. """
        # CHECK: Should not disable service for sundays on holidays which
        #  fall on sundays... Will only make a difference if there are
        #  different timetables for sundays/holidays... right?

        if Config.holiday_code[0] is None:
            return

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
        """ Add a new CalendarDateEntry for every annotation,
        based on the users input. """

        if Config.non_interactive:
            return

        annots = self.calendar.get_annotations()
        if not annots:
            return

        # TODO: If multiple annotations which are active on the same service
        #  have different defaults, default=off will take precedence.
        annot_exceptions = handle_annotations(annots)
        for annot, (default, dates) in annot_exceptions.items():
            services = self.calendar.get_with_annot(annot)
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

    def write_files(self) -> None:
        """ Write all gtfs files to the output directory. """
        self._remove_unused_routes()
        self.add_annotation_dates()
        self.agency.write()
        self.stops.write()
        self.routes.write()
        self.calendar.write()
        self.trips.write()
        self.stop_times.write()
        self.calendar_dates.write()
        self.create_zip_archive()

    def create_zip_archive(self) -> None:
        """ Creates the final gtfs zip archive. """
        archive_path = get_gtfs_archive_path()
        # TODO: Needs check, once output_archive_path is added as cli arg.
        # If the output archive already exist, simply try to create it again.
        if archive_path.exists():
            # This will ensure a different filepath.
            sleep(1)
            return self.create_zip_archive()

        with ZipFile(archive_path, mode="w") as zip_file:
            for path in get_gtfs_filepaths():
                zip_file.write(path, arcname=path.name)

    def add_coordinates(self, nodes: dict[str: Node]) -> None:
        """ Add locations to the stops using the given nodes. """
        if not nodes:
            logger.warning("Could not found any locations for the given "
                           "stops. Cannot add coordinates to stops.")
            return
        logger.info("Adding coordinates to stops.")
        for stop_id, node in nodes.items():
            stop = self.stops.get_by_stop_id(stop_id)
            # No need to add the location to existing stops, as these will
            #  not be updated anyway
            if stop.valid:
                continue
            if isinstance(node, MNode):
                msg = f"Could not find location for '{stop.stop_name}'."
                if Config.interpolate_missing_locations and node.loc.is_valid:
                    logger.info(msg + " Using the interpolated coordinates.")
                else:
                    msg += "You will have to manually add the coordinates."
                    logger.warning(msg)
                    continue
            stop.set_location(*node.loc, isinstance(node, MNode))
        logger.info("Done.")

    def get_stops_of_route(self, route_id: str) -> list[GTFSStopEntry]:
        """ Returns all stops of the given route. """
        trips = self.trips.get_with_route_id(route_id)
        trip_stop_times = [self.stop_times.get_with_trip_id(trip.trip_id)
                           for trip in trips]
        # Only need a single trip, trips of the same route use the same stops.
        stop_ids = [stop_time.stop_id for stop_time in trip_stop_times[0]]
        return [self.stops.get_by_stop_id(stop_id) for stop_id in stop_ids]

    def get_avg_time_between_stops(self, route_id: str,
                                   stop_id1: str, stop_id2: str) -> Time:
        """ Calculate the average travel time between the two stops. """

        def _aligned_stop_times(times1: list[GTFSStopTimesEntry],
                                times2: list[GTFSStopTimesEntry]) -> bool:
            if len(times1) != len(times2):
                return False
            for time1, time2 in zip(times1, times2):
                in_sequence = time1.stop_sequence < time2.stop_sequence
                same_trip = time1.trip_id == time2.trip_id
                if not in_sequence or not same_trip:
                    return False
            return True

        trip_ids = [t.trip_id for t in self.trips.get_with_route_id(route_id)]
        stop_times1 = self.stop_times.get_with_stop_id(trip_ids, stop_id1)
        stop_times2 = self.stop_times.get_with_stop_id(trip_ids, stop_id2)
        assert _aligned_stop_times(stop_times1, stop_times2)

        times = []
        for s1, s2 in zip(stop_times1, stop_times2):
            t_diff = s2.arrival_time - s1.departure_time
            if not t_diff:
                continue
            times.append(abs(t_diff.to_hours()))
        if not times:
            return Time()
        return Time.from_hours(mean(times))

    def get_used_stops(self) -> list[GTFSStopEntry]:
        """ Return a list of GTFSStopEntries, which are used in the PDF. """
        return [stop for stop in self.stops.entries if stop.used_in_timetable]

    def get_sorted_route_ids(self) -> list[str]:
        """ Return all route_ids, sorted desc. by the number of stops. """
        route_ids: list[str] = [r.route_id for r in self.routes.entries]
        return sorted(route_ids, reverse=True,
                      key=lambda r: len(self.get_stops_of_route(r)))
