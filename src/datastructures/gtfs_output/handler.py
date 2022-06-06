from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from holidays.utils import country_holidays
from datetime import datetime as dt

from config import Config
from datastructures.gtfs_output.calendar import Calendar
from datastructures.gtfs_output.calendar_dates import CalendarDates
from datastructures.gtfs_output.route import Routes
from datastructures.gtfs_output.gtfsstop import GTFSStops
from datastructures.gtfs_output.stop_times import StopTimes
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
        print(timetable)
        timetable.clean_values()
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
        for entry in entries:
            if isinstance(entry, TimeTableRepeatEntry):
                repeat = entry
                continue

            # Create new stop_times for current entry.
            service_id = self.calendar.add(
                entry.days.days, entry.annotations).service_id
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

    def generate_calendar_dates(self):
        # TODO: Should not disable service for sundays on holidays which
        #  fall on sundays... However this should also not make a difference

        holiday_dates, non_holiday_dates = self.calendar.group_by_holiday()

        # TODO: Set years to Config.years, once it exists
        holidays = country_holidays(Config.holiday_code[0],
                                    Config.holiday_code[1],
                                    years=dt.now().year)

        for holiday in holidays:
            for date in holiday_dates:
                self.calendar_dates.add(date.service_id, holiday, True)
            for date in non_holiday_dates:
                self.calendar_dates.add(date.service_id, holiday, False)
        self.add_annotation_dates()

    def add_annotation_dates(self):
        msg = ""
        state = "start"
        # Get annotations.
        annots = set()
        raw_annots = [e.annotations for e in self.calendar.entries]
        for annot in raw_annots:
            annots = set.union(annots, annot)
        current = annots.pop()
        annot_values: dict[str, list[tuple[dt.date, bool]]] = {}

        while current:
            # Get input
            if state == "start":
                msg = (f"Found this annotation '{current}'. "
                       f"What action do you want "
                       f"to take (S)kip, (A)pply, (H)elp, (Q)uit?")
            elif state == "apply":
                msg = (f"Enter a date (YYYYMMDD) where service is different "
                       f"than usual, or 'd' if there are no other different "
                       f"dates for this annotation:")
            msg += "\n> "
            inp = input(msg).strip().lower()

            # Handle state.
            if state == "start":
                if inp == "a":
                    state = "apply"
                    continue
                if inp == "s":
                    if not annots:
                        break
                    current = annots.pop()
                    continue
                if inp == "q":
                    break
            elif state == "apply":
                try:
                    date = dt.strptime(inp, "%Y%m%d")
                except ValueError:
                    print("Invalid date.")
                    continue
                msg = (f"Should the services with this annotation be active "
                       f"[y,yes] on the given date or not [n]?\n> ")
                inp = input(msg).strip().lower()
                active = inp in ["y", "yes"]
                annot_values[current] = (annot_values.setdefault(current, [])
                                         + [(date, active)])

        def get_services_with_annot(_annot):
            return [e for e in self.calendar.entries
                    if _annot in e.annotations]
        """
        # Testing...
        annot_values = {'*': [(dt.strptime('20221224', "%Y%m%d"), False),
                              (dt.strptime('20221225', "%Y%m%d"), False),
                              (dt.strptime('20221231', "%Y%m%d"), False),
                              (dt.strptime('20220414', "%Y%m%d"), False),
                              (dt.strptime('20220417', "%Y%m%d"), False),
                              (dt.strptime('20220605', "%Y%m%d"), False)]}
        """
        for annot, values in annot_values.items():
            services = get_services_with_annot(annot)
            for service in services:
                for value, active in values:
                    self.calendar_dates.add(
                        service.service_id, value, active)

    def write_files(self):
        path = Path("../out/").resolve()
        path.mkdir(exist_ok=True)
        self.agency.write(path)
        self.stops.write(path)
        self.routes.write(path)
        self.calendar.write(path)
        self.trips.write(path)
        self.stop_times.write(path)
        self.calendar_dates.write(path)

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

    @property
    def calendar_dates(self):
        return self._calendar_dates
